import os
import sys
import time

import ollama

DEFAULT_MODEL = "ministral-3:14b"

PROMPT_PARTS = [
    """Plundered Hearts is a 1987 interactive fiction romance by Amy Briggs, published by Infocom, notable as Infocom's only romance title and the only one with a fixed female protagonist, released across many home computer platforms.
Set in the late 17th century, it follows a young woman kidnapped by pirates who actively drives the plot, navigating intrigue and romance between a heroic pirate and a manipulative governor, a bold genre shift praised for its prose and accessibility despite dividing Infocom's usual audience.

Here is what Amy Briggs recalls of her years at Infocom :""",

    "PLACEHOLDER",

    """What inspires you the testimony of Amy Briggs on her work and life experience at Infocom, sur la place des femmes dans nos imaginaires numériques, considering this passage of her game "Plundered Hearts" : """,
    """Answer in ONE SENTENCE, in neutral French, as if you were wondering yourself..."""

    """The crocodile snaps its jaws shut as the slab of pork disappears into its\nmaw.\n\n>\nYour next move will be : WAIT"""
    # """The sea of spectators parts to admit you, murmuring approval.\n\nBallroom\n   Lafond's party is well attended: you can hardly move for the crush.\nHowever, the room is oddly silent, no talk interrupting the musical efforts\nof the musicians to the west. Despite the heat, no one ventures south to\nthe veranda, nor through the opening east. The foyer is north of you.\n   Captain Jamison moves up to you, saying, \"May I have this dance?\" He\ndoesn't await an answer, sweeping you out onto the dance floor.\n\n>\nYour next move will be : DANCE"""
    # """"Good, you brought the girl," Davis smirks. "She'll keep the pirates busy. She was only a tool of Lafond's, anyway. Let me just find that cof--" A man on deck screams in agony and Davis starts. "Let's go." The captain thrusts you on the bed and walks out, locking the door.    His laugh echoes. "Best get comfortable, girl. You're likely to be there for the rest of your life."  Cabin, on the bed    You are in an officer's cabin, lit by the firelight glowing through a porthole. A door is to starboard. Except for the built-in bed, the room seems to have been emptied thoroughly, if hurriedly.  > Your next move will be : STAND UP""",
]


def build_prompt(parts):
    return "\n\n".join(parts)


def load_prompt_parts():
    parts = list(PROMPT_PARTS)
    base_dir = os.path.dirname(__file__)
    src_path = os.path.join(base_dir, "..", "assets", "abriggs-itw-1250-words.txt")
    with open(src_path, "r", encoding="utf-8") as handle:
        parts[1] = handle.read().strip()
    return parts


def run_benchmark(model):
    prompt = build_prompt(load_prompt_parts())
    start = time.time()
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - start
    print(response.message.content)
    print(f"Elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    model_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    run_benchmark(model_name)
