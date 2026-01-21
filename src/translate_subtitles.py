#!/usr/bin/env python3
"""Translate subtitle .txt files with context and keep timecodes."""

import argparse
import os
import re
import sys
import textwrap

import ollama

DEFAULT_MODEL = "ministral-3:14b"
DEFAULT_INPUT_DIR = os.path.join("godot-viewer", "video")
CONTEXT_WINDOW = 2

TIMECODE_RE = re.compile(
    r"^\s*\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*,\s*\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*$"
)
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text):
    return WHITESPACE_RE.sub(" ", text).strip()


def clean_line(line):
    line = line.strip()
    if not line:
        return ""
    line = line.replace("A\u00ff", "")
    line = line.replace("\u00ff", "")
    return line


def parse_subtitle_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    cues = []
    i = 0
    total = len(lines)
    while i < total:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if not TIMECODE_RE.match(stripped):
            i += 1
            continue
        timecode = stripped
        i += 1
        text_lines = []
        while i < total:
            line = lines[i].rstrip("\n")
            if not line.strip():
                i += 1
                break
            cleaned = clean_line(line)
            if cleaned:
                text_lines.append(cleaned)
            i += 1
        cues.append({"timecode": timecode, "text_lines": text_lines})
    return cues


def format_lines(text, line_count, reference_lines):
    if line_count <= 1:
        return [text]
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(raw_lines) == line_count:
        return raw_lines
    if len(raw_lines) > line_count:
        merged = raw_lines[: line_count - 1]
        merged.append(" ".join(raw_lines[line_count - 1 :]))
        return merged
    ref_len = sum(len(line) for line in reference_lines) if reference_lines else 0
    width = max(24, int(ref_len / line_count) if ref_len else 40)
    wrapped = textwrap.wrap(" ".join(text.split()), width=width)
    if len(wrapped) >= line_count:
        result = wrapped[: line_count - 1]
        result.append(" ".join(wrapped[line_count - 1 :]))
        return result
    while len(wrapped) < line_count:
        wrapped.append("")
    return wrapped


def build_prompt(context_before, target_text, context_after, line_count):
    lines = []
    for text in context_before:
        lines.append(text)
    lines.append(f"[CIBLE] {target_text}")
    for text in context_after:
        lines.append(text)
    context_block = "\n".join(f"- {line}" for line in lines if line)
    return (
        "Tu traduis des sous-titres en francais. Garde un ton oral et naturel. "
        "Traduis uniquement la phrase cible et assure la coherence avec le contexte. "
        f"Essaye de garder {line_count} ligne(s).\n\n"
        "Contexte (2 avant et 2 apres):\n"
        f"{context_block}\n\n"
        "Phrase a traduire (marquee [CIBLE]):\n"
        f"{target_text}\n\n"
        "Traduction:"
    )


def translate_text(model, context_before, target_text, context_after, line_count):
    prompt = build_prompt(context_before, target_text, context_after, line_count)
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    translation = (response.message.content or "").strip()
    return translation


def translate_cues(cues, model, window):
    total = len(cues)
    for idx, cue in enumerate(cues, start=1):
        target_text = normalize_text(" ".join(cue["text_lines"]))
        if not target_text:
            cue["translated_lines"] = cue["text_lines"]
            continue
        before = [
            normalize_text(" ".join(cues[i]["text_lines"]))
            for i in range(max(0, idx - 1 - window), idx - 1)
        ]
        after = [
            normalize_text(" ".join(cues[i]["text_lines"]))
            for i in range(idx, min(total, idx + window))
        ]
        line_count = max(1, len(cue["text_lines"]))
        translated = translate_text(model, before, target_text, after, line_count)
        if not translated:
            translated = target_text
        cue["translated_lines"] = format_lines(translated, line_count, cue["text_lines"])
        print(f"Translated {idx}/{total}")
    return cues


def write_translated(path, cues):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for cue in cues:
            handle.write(cue["timecode"] + "\n")
            for line in cue.get("translated_lines", []):
                handle.write(line + "\n")
            handle.write("\n")


def list_text_files(input_dir):
    if not os.path.isdir(input_dir):
        return []
    entries = [
        os.path.join(input_dir, name)
        for name in os.listdir(input_dir)
        if name.lower().endswith(".txt")
    ]
    return sorted(entries)


def main():
    parser = argparse.ArgumentParser(
        description="Translate subtitle .txt files using Ollama with context."
    )
    parser.add_argument(
        "-i",
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help="Directory containing subtitle .txt files",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=DEFAULT_MODEL,
        help="Ollama model for translation",
    )
    parser.add_argument(
        "-w",
        "--window",
        type=int,
        default=CONTEXT_WINDOW,
        help="Number of cues before/after for context",
    )
    args = parser.parse_args()

    files = list_text_files(args.input_dir)
    if not files:
        print(f"No .txt files found in {args.input_dir}", file=sys.stderr)
        return 1

    for path in files:
        cues = parse_subtitle_file(path)
        if not cues:
            print(f"Skipping (no cues): {path}")
            continue
        translated = translate_cues(cues, args.model, args.window)
        base, ext = os.path.splitext(os.path.basename(path))
        out_path = os.path.join(os.path.dirname(path), f"{base}_fr{ext}")
        write_translated(out_path, translated)
        print(f"Wrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
