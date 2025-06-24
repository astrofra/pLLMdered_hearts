import os
os.environ["OLLAMA_NO_CUDA"] = "1"

import ollama
import pexpect
import time
import re
import json

def json_command_is_valid(json_command):
    if json_command is None:
        return False
    if not("comment" in json_command):
        return False
    if not("command" in json_command):
        return False
    if not isinstance(json_command["comment"], str):
        return False
    if not isinstance(json_command["command"], str):
        return False
    
    return True

def estimate_reading_time(text, wps=4.0, min_delay=0.3, max_delay=5.0):
    """Estimate a human-readable delay (in seconds) based on word count."""
    word_count = len(text.strip().split())
    delay = word_count / wps
    return max(min_delay, min(delay, max_delay))  # Clamp delay

def extract_and_parse_json(text):
    """
    Extracts the first JSON object found inside triple backticks or code-like blocks from the input text,
    and returns it as a Python dictionary.
    """

    # Try to find JSON inside ```json ... ``` blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        # If no fenced block, try raw { ... } block (useful for degraded format)
        match = re.search(r"(\{[\s\S]*?\})", text)
    
    if match:
        try:
            json_str = match.group(1)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print("JSON parsing failed:", e)
            return None
    else:
        print("No JSON block found.")
        return None

import re

# Match ANSI escape sequences like ESC[31m or ESC[2J
ansi_escape = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
# Match cursor position commands like [24d (often without ESC, incomplete sequences)
cursor_directives = re.compile(r'\[\d{1,3}d')
# Match charset switch like ESC(A or ESC(B
charset_switch = re.compile(r'\x1b\([A-B]')

# Escape sequences that usually correspond to "clear screen", "move cursor", etc.
line_breaking_escapes = re.compile(r'\x1b\[[0-9;]*([HJfABCD])')

def clean_output(text):
    # Replace certain ANSI codes with newlines (those likely to imply line moves)
    def replace_with_newline(match):
        command = match.group(1)
        if command in ['H', 'f', 'A', 'B', 'C', 'D']:
            return '\n'
        return ''

    text = line_breaking_escapes.sub(replace_with_newline, text)
    # Remove charset switch sequences
    text = charset_switch.sub('', text)
    # Remove cursor directives like [24d
    text = cursor_directives.sub('', text)
    # Remove remaining ANSI escape codes
    text = ansi_escape.sub('', text)

    # Remove lines containing only a number (like score or parser noise)
    lines = text.strip().splitlines()
    lines = [line for line in lines if not line.strip().isdigit()]
    # Remove repeated empty lines
    clean_lines = []
    for i, line in enumerate(lines):
        if line.strip() == '' and (i == 0 or lines[i - 1].strip() == ''):
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines).strip()

# official Amiga solution
plundered_hearts_commands = [
    "stand up", "inventory", "examine smelling salts", "read tag", "examine banknote",
    "examine coffer", "examine door", "open door", "z", "scream", "e", "examine falcon",
    "read missive", "falcon, yes", "examine davis", "examine ring", "examine falcon", "z", "z",
    "stand up", "look around", "look through window", "open curtain", "examine cupboard",
    "examine table", "examine bed", "z", "examine brooch", "open coffer", "take invitation",
    "read invitation", "n", "down", "n", "examine gate", "n", "take bottle", "take mirror",
    "examine bottle", "read label", "s", "s", "up", "open door", "enter", "take clothes",
    "remove dress", "wear breeches", "wear shirt", "z", "out", "s", "take coffer", "z",
    "throw coffer through window", "sit on ledge", "put all in reticule", "take ladder",
    "up", "up", "up", "up", "n", "n", "n", "examine winch", "read lever", "pull lever up",
    "s", "examine barrels", "tear dress", "put rag in water", "open hatch", "down",
    "throw rag over gate", "up", "s", "examine casks", "n", "n", "enter shack", "take dagger",
    "e", "s", "s", "look in cask", "enter cask", "take pork", "put all in reticule except dagger",
    "cut rope", "examine pork", "z", "z", "z", "leave cask", "examine skiff", "w", "n", "e",
    "pull slat", "z", "z", "falcon, yes", "z", "e", "n", "open window", "w", "examine portrait",
    "examine bookshelves", "examine globe", "take hat", "s", "w", "e", "examine lucy",
    "take garter", "w", "s", "ne", "climb vine", "remove clothes", "wear ball gown",
    "take invitation", "put garter in reticule", "n", "n", "take pistols", "s", "e", "e",
    "open door", "s", "n", "w", "down", "give invitation", "s", "dance", "dance", "dance",
    "dance", "w", "examine orchestra", "e", "dance", "examine lafond", "examine ring",
    "open door", "s", "n", "n", "e", "s", "e", "n", "n", "take treatise", "take hat",
    "press sinistra on globe", "n", "down", "e", "e", "take key and horn", "w", "s",
    "open door", "e", "w", "n", "w", "s", "squeeze bottle on pork", "throw pork at crocodile",
    "z", "z", "s", "w", "unlock door", "open door", "n", "give garter to papa", "z", "s",
    "e", "n", "n", "up", "s", "s", "n", "n", "s", "s", "s", "n", "n", "s", "up", "e",
    "knock on door", "open door", "n", "drink wine", "pour wine into green goblet",
    "squeeze bottle into green goblet", "pour wine into blue goblet", "z", "lafond, no",
    "drink wine", "take spice", "throw spice at lafond", "wave mirror at window", "s",
    "w", "down", "s", "z", "cookie, yes", "n", "e", "n", "take treatise", "take hat",
    "press sinistra", "n", "down", "s", "s", "take rapier", "kill crulley", "g",
    "close trapdoor", "pick lock", "wave smelling salts", "n", "n", "z", "up", "s",
    "s", "w", "up", "e", "s", "untie rope", "climb down rope", "take horn", "s", "s", "s",
    "look at nicholas", "push nicholas", "nicholas, yes", "take pistol", "load pistol",
    "fire pistol at crulley"
]

plundered_hearts_solution = "Start in the ship's cabin.\
STAND  UP  -  (you  get out of bed) - INVENTORY - (you find that you have a\
reticule  containing  smelling  salts  and  a bank note) - EXAMINE SMELLING\
SALTS - READ TAG - EXAMINE BANKNOTE - (the ship lurches and a coffer slides\
out  from  under the bed) - EXAMINE COFFER - EXAMINE DOOR - OPEN DOOR - Z -\
(Crulley  bursts  in!)  -  SCREAM  -  E - (Crulley stops you but the Falcon\
enters  and  clouts  him!)  -  EXAMINE  FALCON - (he eventually hands you a\
missive)  -  READ MISSIVE - (he offers you protection) - FALCON, YES - (you\
are now on the Deck).\
\
EXAMINE  DAVIS  - (you are taken to the Captain's Quarters.........two days\
pass by) - EXAMINE RING - EXAMINE FALCON - Z - Z - STAND UP - LOOK AROUND -\
LOOK  THROUGH  WINDOW  -  OPEN CURTAIN - EXAMINE CUPBOARD - EXAMINE TABLE -\
EXAMINE  BED  - Z - (Captain Jamison gives you a brooch) - EXAMINE BROOCH -\
OPEN  COFFER - TAKE INVITATION - READ INVITATION - N - (you squeeze through\
to the Landing) - DOWN - N - EXAMINE GATE - N - TAKE BOTTLE - TAKE MIRROR -\
EXAMINE BOTTLE - READ LABEL - S - S - UP - OPEN DOOR - ENTER - TAKE CLOTHES\
- REMOVE DRESS - WEAR BREECHES - WEAR SHIRT - Z - OUT.\
\
S  - TAKE COFFER - Z - THROW COFFER THROUGH WINDOW - SIT ON LEDGE - PUT ALL\
IN  RETICULE - TAKE LADDER - (you now hang on the ladder!) - UP - UP - UP -\
UP - (you land on the Poop Deck) - N - N - N - EXAMINE WINCH - READ LEVER -\
PULL LEVER UP - (you lower the anchor) - S - EXAMINE BARRELS - TEAR DRESS -\
PUT RAG IN WATER - OPEN HATCH - DOWN - THROW RAG OVER GATE - (you douse the\
burning  fuse) - UP - S - EXAMINE CASKS - N - N - ENTER SHACK - TAKE DAGGER\
-  E  - S - S - LOOK IN CASK - ENTER CASK - TAKE PORK - PUT ALL IN RETICULE\
EXCEPT  DAGGER  - CUT ROPE - (you release the cask into the sea!) - EXAMINE\
PORK - Z - Z - Z - (you eventually drift to some shallows near an Island).\
\
LEAVE CASK - EXAMINE SKIFF - W - N - E - PULL SLAT - (Captain Jamison finds\
you!)  - Z - Z - (he asks to kiss you) - FALCON, YES - (now, now.......it's\
only  a  game  fellas!!)  - Z - (he now leaves) - E - N - OPEN WINDOW - W -\
EXAMINE  PORTRAIT  -  EXAMINE BOOKSHELVES - EXAMINE GLOBE - TAKE HAT - (you\
feel a vibration from the floor!.......ooer!!) - S - (the Butler now throws\
you out!!) - W - E - EXAMINE LUCY - TAKE GARTER - W - S - NE - CLIMB VINE -\
(to a Bedroom).\
\
REMOVE  CLOTHES - WEAR BALL GOWN - TAKE INVITATION - PUT GARTER IN RETICULE\
-  N  -  N  -  TAKE  PISTOLS  -  (out  of reach!) - S - E - E - OPEN DOOR -\
(locked!)  - S - N - W - DOWN - GIVE INVITATION - (to Butler) - S - DANCE -\
DANCE  - DANCE - DANCE - W - EXAMINE ORCHESTRA - E - DANCE - EXAMINE LAFOND\
-  EXAMINE RING - OPEN DOOR - S - N - N - E - (the Butler stops you!) - S -\
E  -  N - (under the table) - N - TAKE TREATISE - TAKE HAT - PRESS SINISTRA\
ON GLOBE - (the portrait opens!) - N - DOWN - E - E - TAKE KEY AND HORN.\
\
W  -  S  - OPEN DOOR - E - W - N - W - S - (you see a crocodile!) - SQUEEZE\
BOTTLE  ON  PORK - THROW PORK AT CROCODILE - Z - Z - (it sleeps!) - S - W -\
UNLOCK  DOOR - (with large key) - OPEN DOOR - N - GIVE GARTER TO PAPA - Z -\
S - E - N - N - UP - S - S - (Captain Jamison is being arrested!) - N - N -\
S - S - S - N - N - S - UP - E - KNOCK ON DOOR - OPEN DOOR - N - DRINK WINE\
-  POUR  WINE  INTO  GREEN GOBLET - SQUEEZE BOTTLE INTO GREEN GOBLET - POUR\
WINE  INTO BLUE GOBLET - Z - (Lafond asks you if the green goblet is his) -\
LAFOND, NO - (he takes the green goblet!) - DRINK WINE - TAKE SPICE - THROW\
SPICE AT LAFOND - WAVE MIRROR AT WINDOW - (to signal the Helena Louise).\
\
S  -  (the  Butler  is  sound  asleep!) - W - DOWN - S - Z - (Jamison's men\
enter!)  -  COOKIE,  YES  -  N  -  E - N - TAKE TREATISE - TAKE HAT - PRESS\
SINISTRA  -  N  -  DOWN - S - (Cookie deals with the crocodile!) - S - TAKE\
RAPIER  -  KILL CRULLEY - G - CLOSE TRAPDOOR - PICK LOCK - (with the brooch\
clasp)  -  WAVE  SMELLING SALTS - N - N - Z - UP - S - S - W - UP - E - S -\
UNTIE  ROPE - CLIMB DOWN ROPE - (you crash into Lafond!!) - (you eventually\
end  up  back in the Ballroom) - TAKE HORN - S - S - S - LOOK AT NICHOLAS -\
PUSH  NICHOLAS - NICHOLAS, YES - TAKE PISTOL - LOAD PISTOL - FIRE PISTOL AT\
CRULLEY............to complete the adventure!!!!!!!!"

# wikipedia article about Plundered Hearts
plundered_hearts_wiki = """Plundered Hearts is an interactive fiction video game created by Amy Briggs and published by Infocom in 1987. Infocom's only game in the romance genre, it was released simultaneously for the Apple II, Commodore 64, Atari 8-bit computers, Atari ST, Amiga, Mac, and MS-DOS. It is Infocom's 28th game.
Plundered Hearts casts the player in a well-defined role. The lead character is a young woman in the late 17th century who has received a letter. Jean Lafond, the governor of the small West Indies island of St. Sinistra, says that the player's father has contracted a wasting tropical disease. Lafond suggests that his recovery would be greatly helped by the loving presence of his daughter, and sends his ship (the Lafond Deux) to transport her.
As the game begins, the ship is attacked by pirates and the player's character is kidnapped. Eventually, the player's character finds that two men are striving for her affections: dashing pirate Nicholas Jamison, and the conniving Jean Lafond. As the intrigue plays out, the lady does not sit idly by and watch the men duel over her; she must help Jamison overcome the evil plans of Lafond so that they have a chance to live happily ever after.
As early as 1984, Infocom employees joked about the possibility of a romance text adventure. By 1987, the year of Plundered Hearts's release, Infocom no longer rated its games on difficulty level.
Although this was not the only Infocom game designed in an effort to attract female players (one example being Moonmist), it is the only game where the lead character is always female.
The Plundered Hearts package included an elegant velvet reticule (pouch) containing the following items:
- A 50 guinea banknote from St. Sinistra
- A letter from Jean Lafond reporting the illness of the player character's father
Game reviewers complimented Plundered Hearts for its gripping prose, challenging predicaments, and scenes of derring-do. Other publications said it was a good introduction to interactive fiction, with writing suitable for both men and women. Some noted that the genre might have alienated Infocom's typical audience, but praised its bold direction nonetheless.
"""

plundered_hearts_user_manual = """Communicating with Infocom's Interactive Fiction
In Plundered Hearts, you type your commands in plain English each time you see the prompt (>). Plundered
Hearts usually acts as if your commands begin with "I want to...," although you shouldn't actually type those
words. You can use words like THE if you want, and you can use capital letters if you want; Plundered Hearts
doesn't care either way.
When you have finished typing a command, press the RETURN (or ENTER) key. Plundered Hearts will then
respond, telling you whether your request is possible at this point in the story, and what happened as a result.
Plundered Hearts recognizes your words by their first six letters, and all subsequent letters are ignored.
Therefore, CANDLE, CANDLEs, and CANDLEstick would all be treated as the same word by Plundered Hearts.
To move around, just type the direction you want to go. Directions can be abbreviated: NORTH to N, SOUTH to
S, EAST to E, WEST to W, NORTHEAST to NE, NORTHWEST to NW, SOUTHEAST to SE, SOUTHWEST to
SW, UP to U, and DOWN to D. Remember that IN and OUT will also work in certain places. Aboard a ship, you
can use the directions FORE (or F), AFT, PORT (or P), and STARBOARD (or SB).
Plundered Hearts understands many different kinds of sentences. Here are several examples. (Note some of these
do not actually appear in Plundered Hearts.)
>WALK NORTH
>DOWN
>NE
>GO AFT
>TAKE THE RED CANDLE
>READ THE SIGN
>LOOK UNDER THE BED
>OPEN THE HATCH
>DANCE WITH WILLIAM
>CLIMB THE LADDER
>PRESS THE GREEN BUTTON
>EXAMINE THE RAPIER
>SWING ON THE ROPE
>PUT ON THE PETTICOAT
>WEAR THE TIARA
>KNOCK ON THE DOOR
>SHOOT THE PEBBLE WITH THE SLINGSHOT
>UNLOCK THE BOX WITH THE KEY
>CUT THE ROPE WITH THE SCISSORS
>PUT THE COLLAR ON THE DOG
>THROW THE GOBLET OUT THE WINDOW
You can use multiple objects with certain verbs if you separate them by the word AND or by a comma. Some
examples:
>TAKE BOOK AND KNIFE
>DROP THE HOOPS, THE BRACELET AND THE TRAY
>PUT THE PEARL AND THE SHELL IN THE BOX
You can include several sentences on one input line if you separate them by the word THEN or by a period.
(Note that each sentence will still count as a turn.) You don't need a period at the end of the input line. For example,
you could type all of the following at once, before pressing the RETURN (or ENTER) key:
>READ THE SIGN. GO NORTH THEN DROP THE STONE AND MAP"""

# run frotz through a terminal emulator, using the ascii mode
# child = pexpect.spawn("frotz -p roms/PLUNDERE.z3", encoding='utf-8', timeout=5)
from pexpect.popen_spawn import PopenSpawn
child = PopenSpawn("frotz -p roms/PLUNDERE.z3", encoding='utf-8', timeout=5)


# Catch the intro message
child.expect("Press RETURN or ENTER to begin")
print(child.before)

# Answer the intro message by pressing "enter"
child.sendline("")

time.sleep(0.5)

# Initial output
# child.expect("\r\x1b", timeout=5)
# print(repr(child.before))
buffer = ""
for _ in range(50):  # max itérations (sécurité)
    try:
        buffer += child.read_nonblocking(size=1024, timeout=0.2)
        if ">" in buffer[-10:]:
            break
    except pexpect.exceptions.TIMEOUT:
        break
# print(child.before)
print("\n")

prev_output = ""
cmd_index = 0
prev_cmd = None

# automated walkthrough
while True : # for step, cmd in enumerate(plundered_hearts_commands):
    cmd = plundered_hearts_commands[cmd_index]

    prompt = "You are playing Pludered Hearts, a text interactive fiction by Amy Briggs."
    prompt = prompt + "Here is what Wikipedia says about this game : "
    prompt = prompt + plundered_hearts_wiki
    prompt = prompt + """
You are an intelligent assistant who suggests the next action to take in the game.
Important: You are playing a classic text adventure with a strict command parser. Your commands must follow one of these patterns:
- VERB (e.g. LOOK AROUND, INVENTORY, NORTH, N, S, W, E)
- VERB + OBJECT (e.g. EXAMINE BED, TAKE PISTOL, OPEN DOOR)
- VERB + OBJECT + COMPLEMENT (e.g. UNLOCK DOOR WITH KEY, FIRE PISTOL AT CRULLEY)
- Optionally: two simple actions joined by AND or THEN (e.g. TAKE HORN AND BLOW IT)
"""
    prompt = prompt + "Here is the user manual regarding the parser commands : "
    prompt = prompt + plundered_hearts_user_manual
    prompt = prompt + "Here is the latest output from the game : "
    prompt = prompt + prev_output
    if prev_cmd is not None:
        prompt = prompt + "Your previous command was : '" + prev_cmd + "'."
    prompt = prompt + "From the known solution of the game, you know the next good command will be : " + cmd
    # prompt = prompt + "Here is the known solution for the game but please don't jump to the end directly : "
    # prompt = prompt + plundered_hearts_solution
    prompt = prompt + "Please provide a JSON with one key :"
    prompt = prompt + " - 'comment' key to give a detailled feminist point of view over the current situation, in a familiar or slang-ish way, without mentioning the feminism, IN FRENCH ARGOT, FIRST PERSON, then explain, IN FRENCH ARGOT, FIRST PERSON, what to do and why this is the best thing in this context."
    prompt = prompt + " - 'command' key that will describe out loud, in a familiar or slang-ish way, IN FRENCH ARGOT, FIRST PERSON, the command in itself, put in context."
    # prompt = prompt + " - 'prompt' key that will only contain the command that you suggest given all the context you have at hand."
    prompt = prompt + "When thinking out loud, you refer yourself (and yourself only) as 'meuf' or 'frère'"
    json_command = None

    retry = 0
    while not json_command_is_valid(json_command): # json_command is None or not("comment" in json_command) or not("command" in json_command):
        response = ollama.chat(
            model='llama3:8b',
            # model = 'deepseek-r1:7b',
            messages=[{
                'role': 'user',
                'content': prompt
                }]
        )
        # print(response.message.content)
        json_command = extract_and_parse_json(response.message.content)
        if retry > 0:
            print("Retry #" + str(retry))
        retry = retry + 1

    # print("\n")
    ai_thinking = json_command["comment"] + "\n" + json_command["command"]
    print("<AI thinks : '" + ai_thinking + "'>\n")
    time.sleep(estimate_reading_time(ai_thinking))
    # command = json_command["prompt"]
    # command = command.replace(">", "").strip().upper()
    command = cmd.strip().upper()
    print("> " + command.strip() + "\n")
    child.sendline(" " + command)
    prev_output = ""
    prev_cmd = command

    # Flush output after command
    buffer = ""
    start_time = time.time()
    timeout_seconds = 4  # lecture max après commande
    while time.time() - start_time < timeout_seconds:
        try:
            chunk = child.read_nonblocking(size=1024, timeout=0.3)
            buffer += chunk
        except pexpect.exceptions.TIMEOUT:
            break

    cleaned = clean_output(buffer)
    print(cleaned)
    prev_output = cleaned

    time.sleep(0.3)  # artificially wait to allow reading

    cmd_index = cmd_index + 1
