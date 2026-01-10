# Phase 2 — LLM Commentary Viewer (Codex Instructions)

## Goal
Implement a **separate process** that displays LLM-generated commentary in real time using a **local web page**.
This viewer runs independently from the C64 terminal renderer and reads Markdown files written by the main program.

The system must be **robust, simple, and installation-safe**.

---

## Global Constraints
- No Flask, FastAPI, or backend framework.
- Use **Python built-in static HTTP server** only.
- Use a **web browser (Firefox)** in fullscreen / kiosk mode.
- Communication between processes is done **only via the filesystem**.
- No Python threading.
- No shared memory.
- No IPC beyond files.

---

## Directory Layout (required)

```
project/
├── faketerm.py              # Main process (game + CRT + LLM)
├── llm_out/                 # Folder written by faketerm.py
│   ├── 20260104_172630.md
│   ├── 20260104_172645.md
│   └── ...
└── www/
    ├── index.html
    ├── main.js
    └── style.css
```

- `llm_out/` contains **timestamped Markdown files**.
- Files are **append-only** (never modified after creation).
- New files represent new LLM commentary events.

---

## HTTP Server

Use the built-in Python server:

```bash
python -m http.server 8000
```

Rules:
- The server **must be started from `project/`**, not from `www/`.
- This allows the browser to fetch both `www/` and `llm_out/`.

The page will be accessed at:
```
http://localhost:8000/www/index.html
```

---

## Browser Behavior

- Launch Firefox in fullscreen or kiosk mode.
- No browser UI visible.
- One page only.
- No navigation.

Example (Windows):
```bat
start "" python -m http.server 8000
timeout /t 2
start "" "C:\Program Files\Mozilla Firefox\firefox.exe" http://localhost:8000/www/index.html --kiosk
```

---

## JavaScript Logic (main.js)

### Core Principle
Use **polling**, not filesystem watching.

- Poll every 500–1000 ms.
- List files in `llm_out/`.
- Sort by filename (timestamps).
- Detect the newest file.
- If it is new → fetch and render it.
- If not → do nothing.

### Requirements
- No WebSocket.
- No EventSource.
- No Service Workers.
- No IndexedDB.

---

## Markdown Handling

- LLM output is **raw Markdown**.
- Markdown formatting is intentional and expressive.
- Do **not** sanitize aggressively.
- Do **not** normalize tone or structure.

Use a client-side Markdown renderer:
- `marked.js` (recommended)

Example:
```html
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
```

```js
container.innerHTML = marked.parse(markdownText);
```

---

## Rendering Rules

- One commentary visible at a time.
- When a new file appears:
  - Replace the previous text.
  - Use a short fade-in transition.
- No fast auto-scrolling.
- Text must be readable from several meters away.

---

## Visual Style Guidelines

- Strong contrast with the CRT screen.
- Neutral dark background.
- Light text.
- Comfortable line length.

Example CSS constraints:
```css
body {
  background: #111;
  color: #eee;
  font-size: 22px;
  line-height: 1.5;
}

#content {
  max-width: 720px;
  margin: 60px auto;
}
```

Typography:
- Serif or neutral grotesque.
- No retro styling.
- No terminal fonts.

The visual contrast with the C64 screen is intentional.

---

## Timing and Rhythm

- The viewer must feel **slow and deliberate**.
- Commentary should feel like a **voice reacting**, not a chat UI.
- Avoid visual noise.
- Avoid UI chrome.
- Avoid logs or timestamps on screen.

---

## Failure Tolerance

- If no Markdown file exists yet:
  - Display nothing or a neutral idle state.
- If a file is malformed:
  - Display raw text.
- If the server restarts:
  - The viewer must recover automatically.

---

## Summary

- Two processes.
- One writes Markdown.
- One reads and displays.
- Filesystem is the contract.
- Browser is the renderer.
- Python threads are avoided entirely.

This phase must prioritize **stability, legibility, and exhibition readiness** over technical sophistication.
