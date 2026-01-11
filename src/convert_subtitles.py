#!/usr/bin/env python3
"""Convert timestamped subtitles into WebVTT."""

import argparse
import os
import re
import sys

TIME_LINE_RE = re.compile(r"^\s*\d+:\d{2}:\d{2}\.\d{1,3}\s*,\s*\d+:\d{2}:\d{2}\.\d{1,3}\s*$")


def is_time_line(line: str) -> bool:
    return bool(TIME_LINE_RE.match(line))


def normalize_time(raw: str) -> str:
    raw = raw.strip()
    parts = raw.split(":")
    if len(parts) == 2:
        hours = 0
        minutes, seconds_ms = parts
    elif len(parts) == 3:
        hours, minutes, seconds_ms = parts
    else:
        raise ValueError(f"Unsupported time format: {raw}")

    if "." in seconds_ms:
        seconds, millis = seconds_ms.split(".", 1)
    else:
        seconds, millis = seconds_ms, "0"

    hours = int(hours)
    minutes = int(minutes)
    seconds = int(seconds)
    millis = (millis + "000")[:3]

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis}"


def parse_cues(lines):
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i].lstrip("\ufeff").rstrip("\n")
        if not line.strip():
            i += 1
            continue
        if not is_time_line(line):
            i += 1
            continue

        start_raw, end_raw = [part.strip() for part in line.split(",", 1)]
        start = normalize_time(start_raw)
        end = normalize_time(end_raw)

        i += 1
        text_lines = []
        while i < total:
            text_line = lines[i].rstrip("\n")
            if not text_line.strip():
                i += 1
                break
            if is_time_line(text_line):
                break
            text_lines.append(text_line.strip())
            i += 1

        if text_lines:
            yield start, end, "\n".join(text_lines)


def convert_file(input_path: str, output_path: str) -> None:
    with open(input_path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    cues = list(parse_cues(lines))

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("WEBVTT\n\n")
        for start, end, text in cues:
            handle.write(f"{start} --> {end}\n")
            handle.write(text)
            handle.write("\n\n")


def build_output_path(input_path: str) -> str:
    base, _ = os.path.splitext(input_path)
    return base + ".vtt"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert custom subtitle format to WebVTT."
    )
    parser.add_argument("input", help="Path to the subtitle .txt file")
    parser.add_argument("-o", "--output", help="Output .vtt path")
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or build_output_path(input_path)

    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    convert_file(input_path, output_path)
    print(f"Wrote WebVTT: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
