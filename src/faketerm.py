import pexpect
import time
import re

ansi_escape = re.compile(r'''
    \x1b    # ESC
    \[      # CSI
    [0-9;]* # Parameters
    [A-Za-z] # Command letter
''', re.VERBOSE)

cursor_directives = re.compile(r'\[\d{1,3}d')
charset_switch = re.compile(r'\x1b\([A-B]')

def clean_output(text):
    # Cleanup ANSI (line feed, cursor, etc.)
    text = ansi_escape.sub('', text)
    # Cleanup "[24d" and alike
    text = charset_switch.sub('', text)
    text = cursor_directives.sub('', text)
    # Cleanup score (attempt to...)
    lines = text.strip().splitlines()
    lines = [line for line in lines if not line.strip().isdigit()]
    return '\n'.join(lines).strip()


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

# run frotz through a terminal emulator, using the ascii mode
child = pexpect.spawn("frotz -p PLUNDERE.z3", encoding='utf-8', timeout=5)

# Catch the intro message
child.expect("Press RETURN or ENTER to begin")
print(child.before)

# Answer the intro message by pressing "enter"
child.sendline("")

time.sleep(0.5)

# Initial output
child.expect("\r\x1b", timeout=5)
print(child.before)

# automated walkthrough
for step, cmd in enumerate(plundered_hearts_commands):
    try:
        # print(f"\n→ Étape {step+1}: {cmd}")
        # print(f"{cmd}")
        child.sendline(" " + cmd)

        # read several lines in a row
        while True:
            i = child.expect([r"\r\x1b", pexpect.EOF, pexpect.TIMEOUT], timeout=2)
            # print(child.before)
            print(clean_output(child.before))
            if i != 0:
                break

        time.sleep(0.3)  # artificially wait to allow reading

    except pexpect.EOF:
        print("Game ended.")
        break
    except KeyboardInterrupt:
        print("User stopped the game.")
        break
    except Exception as e:
        print(f"Error found at step {step+1}: {e}")
        break
