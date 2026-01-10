import json
import os
import random
import re
import sys
import time

import ollama
import pexpect

import pygame

from c64renderer import C64Renderer

# os.environ["OLLAMA_NO_CUDA"] = "1"

## FIXME "[Press RETURN or ENTER to continue.]"

LLM_MODEL = 'ministral-3:8b' # 'qwen2.5:7b' # 'ministral-3:14b'
ENABLE_LLM = True
ENABLE_READING_PAUSE = True
ENABLE_C64_RENDERER = True
ENABLE_KEYCLICK_BEEP = True
ENABLE_C64_FULLSCREEN = False
C64_DISPLAY_INDEX = None  # 1-based display number (1, 2, 3); None uses the primary monitor.

C64_FONT_PATH = None  # Using built-in fallback font; no external sprite sheet required.
KEY_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "audio")
LLM_OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "llm_out")

def llm_response_is_valid(llm_commentary):
    if llm_commentary is None:
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

    stop_strings = ["```json", "```", "\n"]
    for _stop in stop_strings:
        text = text.replace(_stop, '')

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

# Match ANSI escape sequences like ESC[31m or ESC[2J
ansi_escape = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
# Match cursor position commands like [24d (often without ESC, incomplete sequences)
cursor_directives = re.compile(r'\[\d{1,3}d')
# Match charset switch like ESC(A or ESC(B
charset_switch = re.compile(r'\x1b\([A-B]')
# Match title/score bar lines that contain score and moves.
status_bar_re = re.compile(r".*Score:\s*\d+.*Moves:\s*\d+", re.IGNORECASE)
LAST_STATUS_BAR = ""

# Escape sequences that usually correspond to "clear screen", "move cursor", etc.
line_breaking_escapes = re.compile(r'\x1b\[[0-9;]*([HJfABCD])')

def clean_output(text):
    global LAST_STATUS_BAR
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

    # Remove status/title bar and lines containing only a number (like score or parser noise)
    lines = text.strip().splitlines()
    filtered = []
    for line in lines:
        stripped = line.strip()
        if status_bar_re.search(stripped):
            LAST_STATUS_BAR = stripped
            if "Plundered Hearts" in LAST_STATUS_BAR:
                LAST_STATUS_BAR = LAST_STATUS_BAR.replace("Plundered Hearts", "PLLMDERED_HEARTS")
            continue
        if stripped.isdigit():
            continue
        filtered.append(line)
    # Remove repeated empty lines
    clean_lines = []
    for i, line in enumerate(filtered):
        if line.strip() == '' and (i == 0 or filtered[i - 1].strip() == ''):
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines).strip()

_KEY_SOUNDS = []
_MIXER_READY = False


def _ensure_key_sounds_loaded():
    """Lazy-load key click sounds from assets/audio/*.ogg."""
    global _KEY_SOUNDS, _MIXER_READY
    if _MIXER_READY:
        return
    if not pygame:
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=256)
        if not os.path.isdir(KEY_AUDIO_DIR):
            return
        oggs = [f for f in os.listdir(KEY_AUDIO_DIR) if f.lower().endswith(".ogg")]
        oggs.sort()
        for fname in oggs:
            try:
                sound = pygame.mixer.Sound(os.path.join(KEY_AUDIO_DIR, fname))
                _KEY_SOUNDS.append(sound)
            except Exception:
                continue
        _MIXER_READY = True
    except Exception:
        _MIXER_READY = False


def _play_key_beep(ch=" "):
    """Play a key click sound mapped from ASCII; fallback to terminal bell."""
    if not ENABLE_KEYCLICK_BEEP:
        return
    _ensure_key_sounds_loaded()
    if _KEY_SOUNDS:
        try:
            idx = ord(ch) % len(_KEY_SOUNDS)
            _KEY_SOUNDS[idx].play()
            return
        except Exception:
            pass
    # Fallback: terminal bell
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass


def type_to_renderer(
    renderer,
    text,
    base_delay=0.015,
    min_delay=0.075,
    max_delay=0.20,
    beep=True,
    word_mode=False,
):
    """
    Simulate typing to the renderer: emit characters one by one with a delay
    proportional to ASCII distance from the previous character.
    """
    if not renderer or text is None:
        return
    prev = " "
    chunks = re.findall(r"\n|\S+\s*|\s+", text) if word_mode else list(text)
    # Show cursor ahead of each chunk, and keep it after each chunk except the final one.
    total_chunks = len([c for c in chunks if c])
    typed = 0
    for chunk in chunks:
        if not chunk:
            continue
        if renderer:
            renderer.render_frame(show_cursor=True)
        renderer.write(chunk)
        typed += 1
        renderer.render_frame(show_cursor=typed < total_chunks)
        # Use the last non-newline character of the chunk to keep delays consistent.
        ch = next((c for c in reversed(chunk) if c not in "\r\n"), " ")
        if not ch.strip():
            ch = " "
        distance = abs(ord(ch) - ord(prev))
        delay = max(min_delay, min(max_delay, distance * base_delay))
        if beep and chunk not in ["\n", " ", ">"]:
            _play_key_beep(ch)
        if chunk not in ["\n", ">"]:
            time.sleep(delay)
        prev = ch


def write_llm_markdown(text):
    """Persist LLM commentary as a timestamped markdown file in llm_out/."""
    if text is None:
        return None
    try:
        os.makedirs(LLM_OUT_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        filename = f"{timestamp}.md"
        path = os.path.join(LLM_OUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path
    except Exception as exc:
        print(f"Failed to write LLM output: {exc}")
        return None


def build_prompt(prev_output, next_cmd):
    prompt = "You are playing Pludered Hearts, a text interactive fiction by Amy Briggs."
    prompt = prompt + "Here is what Wikipedia says about this game : "
    prompt = prompt + plundered_hearts_wiki
    prompt = prompt + plundered_hearts_fandom

    prompt = prompt + "Here is the latest output from the game : "
    prompt = prompt + (prev_output or "")

    prompt = prompt + "From the known solution of the game, you know the next good command will be : " + (next_cmd or "")
    prompt = prompt + "Please give a strong feminist point of view over the current situation, in a familiar or slang-ish way, without mentioning the feminism, IN FRENCH ARGOT, FIRST PERSON, then explain, IN FRENCH ARGOT, FIRST PERSON, what to do and why this is the best thing in this context."
    prompt = prompt + "When thinking out loud, you refer yourself (and yourself only) as 'meuf' or 'frere'."
    prompt = prompt + "250 words maximum."
    return prompt

# Official Amiga solution
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

# Wikipedia article about Plundered Hearts
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

plundered_hearts_fandom = """
You play Lady Dimsford, a young, aristocratic woman in the 17th century. She receives a letter from Jean Lafond, the governor of an island in the West Indies, informing her that her father is dying of a tropical disease. Lafond sends a ship to bring her to his island. The ship is then intercepted by notorious pirate Captain Jamison. However, it turns out that Lafond has kidnapped Lady Dimsford's father for his own purposes. The Lady and the pirate work together to defeat him.
The game can be played to completion with four potential endings. However, in only one ending do all of the Lady's loved ones survive. If another ending is arrived at, the user is informed that "There are other, perhaps more satisfying, conclusions."
There was a divide within Infocom regarding whether interactive fiction protagonists should be "audience stand-ins", or whether they should have defined characters. For instance, after negative reaction to the anti-hero protagonist of Infidel, implementor Michael Berlyn concluded that "People really don’t want to know who they are [in a game]." Plundered Hearts falls on the opposite side of the spectrum. Lady Dimsford's capable and spunky personality subverts the game's "damsel in distress" setup.
"""

# run frotz through a terminal emulator, using the ascii mode
# child = pexpect.spawn("frotz -p roms/PLUNDERE.z3", encoding='utf-8', timeout=5)
from pexpect.popen_spawn import PopenSpawn
child = PopenSpawn("frotz -p roms/PLUNDERE.z3", encoding='utf-8', timeout=5)

renderer = None
if ENABLE_C64_RENDERER:
    try:
        display_index = None
        if C64_DISPLAY_INDEX:
            try:
                display_index = max(0, int(C64_DISPLAY_INDEX) - 1)
            except (TypeError, ValueError):
                display_index = None
        renderer = C64Renderer(
            font_path=C64_FONT_PATH,
            fps=50,
            fullscreen=ENABLE_C64_FULLSCREEN,
            display_index=display_index,
        )
    except Exception as exc:
        print(f"Unable to start C64 renderer: {exc}")
        renderer = None

prev_output = ""
cmd_index = 0
prev_cmd = None
pending_intro_ack = True

# Unified loop for reading, displaying, and responding.
while True:  # for step, cmd in enumerate(plundered_hearts_commands):
    if renderer:
        renderer.process_events()

    raw_output = ""
    start_time = time.time()
    timeout_seconds = 4
    while time.time() - start_time < timeout_seconds:
        try:
            chunk = child.read_nonblocking(size=1024, timeout=0.3)
            if not chunk:
                break
            raw_output += chunk
            if "***MORE***" in raw_output or  "[Press RETURN or ENTER to continue.]" in raw_output:
                raw_output = raw_output.replace("***MORE***", "")
                child.sendline("")
                continue
            if ">" in raw_output:
                break
        except pexpect.exceptions.TIMEOUT:
            break

    if not raw_output and pending_intro_ack:
        try:
            child.expect("Press RETURN or ENTER to begin", timeout=1)
            raw_output = (child.before or "") + (child.after or "")
        except pexpect.exceptions.TIMEOUT:
            pass

    if raw_output:
        cleaned = clean_output(raw_output)
        if renderer and LAST_STATUS_BAR:
            renderer.set_status_bar(LAST_STATUS_BAR)
        if renderer:
            if cleaned:
                type_to_renderer(
                    renderer,
                    cleaned + "\n",
                    base_delay=1 / 60.0,
                    min_delay=1 / 240.0,
                    max_delay=1 / 30.0,
                    beep=False,
                    word_mode=True,
                )
            else:
                renderer.render_frame()
        print(cleaned)
        if cleaned:
            prev_output = cleaned

    if pending_intro_ack and ("Press RETURN or ENTER to begin" in raw_output or not raw_output):
        child.sendline("")
        pending_intro_ack = False
        continue

    # Only proceed if the game shows a prompt and we still have commands to send.
    if ">" in raw_output and cmd_index < len(plundered_hearts_commands):
        cmd = plundered_hearts_commands[cmd_index]

        if ENABLE_LLM:
            prompt = build_prompt(prev_output, cmd)
            llm_commentary = None
            retry = 0
            while llm_commentary is None:
                response = ollama.chat(
                    model=LLM_MODEL,
                    messages=[{
                        'role': 'user',
                        'content': prompt
                        }]
                )
                llm_commentary = response.message.content
                if retry > 0:
                    print("Retry #" + str(retry))
                retry = retry + 1
            ai_thinking = llm_commentary + "\n"
            print("<AI thinks : '" + ai_thinking + "'>\n")
            write_llm_markdown(llm_commentary)
            if ENABLE_READING_PAUSE:
                time.sleep(estimate_reading_time(ai_thinking))

        display_cmd = ">> " + cmd.strip()
        print(display_cmd + "\n")
        if renderer:
            type_to_renderer(renderer, "\n" + display_cmd + "\n", beep=True)
        child.sendline(" " + cmd)
        prev_cmd = cmd
        cmd_index += 1

    if ENABLE_READING_PAUSE:
        time.sleep(1.0)  # artificially wait to allow reading

    if cmd_index >= len(plundered_hearts_commands):
        break
