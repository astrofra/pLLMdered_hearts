#!/usr/bin/env python3
"""Compute embeddings for WebVTT cues and write JSON."""

import argparse
import json
import os
import re
import sys

import ollama

DEFAULT_MODEL = "qwen3-embedding"
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def parse_timecode(line: str) -> str:
    left, right = line.split("-->", 1)
    start = left.strip().split()[0]
    end = right.strip().split()[0]
    return f"{start} --> {end}"


def parse_vtt(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    cues = []
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i].lstrip("\ufeff").rstrip("\n")
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("WEBVTT"):
            i += 1
            continue

        if "-->" not in stripped:
            j = i + 1
            while j < total and not lines[j].strip():
                j += 1
            if j < total and "-->" in lines[j]:
                i = j
                continue
            i += 1
            continue

        timecode = parse_timecode(stripped)
        i += 1
        text_lines = []
        while i < total:
            text_line = lines[i].rstrip("\n")
            if not text_line.strip():
                i += 1
                break
            text_lines.append(text_line.strip())
            i += 1

        text = normalize_text(" ".join(text_lines))
        if text:
            cues.append({"timecode": timecode, "text": text})

    return cues


def embed_cues(cues, model: str):
    results = []
    total = len(cues)
    for idx, cue in enumerate(cues, start=1):
        response = ollama.embeddings(model=model, prompt=cue["text"])
        results.append(
            {
                "timecode": cue["timecode"],
                # "text": cue["text"],
                "embedding": response["embedding"],
            }
        )
        print(f"Embedded {idx}/{total}")
    return results


def build_output_path(input_path: str) -> str:
    base, _ = os.path.splitext(input_path)
    return base + ".embeddings.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute embeddings for WebVTT cues and write JSON."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=os.path.join("www", "static", "video", "abriggs-itw.vtt"),
        help="Path to the .vtt file",
    )
    parser.add_argument("-o", "--output", help="Output .json path")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help="Ollama model")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 1

    cues = parse_vtt(args.input)
    if not cues:
        print("No cues found.", file=sys.stderr)
        return 1

    output_path = args.output or build_output_path(args.input)
    results = embed_cues(cues, args.model)

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=True)

    print(f"Wrote JSON: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
