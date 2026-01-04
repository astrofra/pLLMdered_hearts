# pLLuMdered Hearts – Agent Notes

Guidelines for maintaining the automation that plays *Plundered Hearts* while narrating its thoughts. Keep everything simple, Pythonic (3.10 max), and light on dependencies.

## Scope
- Core logic lives in `src/faketerm.py`; avoid introducing new modules unless necessary.
- External programs: `frotz` (Z-Machine interpreter) and the ROM `roms/PLUNDERE.z3`.
- Optional LLM commentary uses `ollama`; do not add other AI clients unless required.

## Coding style (Python 3.10)
- Prefer stdlib (os, time, re, json); avoid extra libs unless unavoidable. If you must add one, document why.
- Keep functions small and single-purpose; lean on clear names over comments.
- No pattern matching or 3.11+ syntax; target 3.10 for compatibility.
- Handle text as plain ASCII/UTF-8; sanitize terminal escapes before passing to the model or logs.

## Runtime flow (`src/faketerm.py`)
- Spawns `frotz` via `pexpect` to drive the game; waits for the initial “Press RETURN...” prompt and sends an empty line to start.
- Walkthrough commands are stored in `plundered_hearts_commands` and sent one by one; adjust with care to preserve pacing.
- Output is cleaned with `clean_output()` to strip escape codes and noise; keep any new filters conservative to avoid losing story text.
- Two toggles gate the AI side:
  - `ENABLE_LLM`: when `True`, builds a prompt from Wikipedia/Fandom blurbs plus recent game output and the next walkthrough command.
  - `ENABLE_READING_PAUSE`: when `True`, pauses between steps using `estimate_reading_time()` to mimic reading speed.

## LLM usage
- Default model is `ministral-3:14b` via `ollama`; keep prompts short and deterministic. Avoid multi-turn chain unless needed.
- `extract_and_parse_json()` is available if a model returns structured data; it cleans common fences before parsing.
- Guard against missing/slow responses; keep timeouts modest to avoid blocking the game loop.

## Terminal hygiene
- `clean_output()` already strips ANSI cursor moves and charset switches; prefer extending its regexes over ad-hoc replacements in the loop.
- Keep delays small (`timeout_seconds` ~4s) so the loop remains responsive; log only what helps debugging.

## Testing and ops
- Quick check: run `python src/faketerm.py` with `frotz` and the ROM present; LLM stays disabled by default for offline runs.
- When enabling the LLM, ensure `ollama` is running locally and the model is pulled; avoid network-bound dependencies.

## Writing new features
- Favor configuration flags over hard-coding (e.g., toggling commentary, adjusting delays).
- If adding assets (audio, transcripts), keep paths relative and note them here.
- Document any deviation from the walkthrough or prompt design so the installation remains replayable.