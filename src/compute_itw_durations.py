#!/usr/bin/env python3
"""Compute video durations from subtitle files and update embeddings JSON."""

import argparse
import json
import os
import re
import sys

TIMECODE_RE = re.compile(
    r"^\s*\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*,\s*\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*$"
)


def parse_timecode(raw):
    cleaned = raw.strip().replace(",", ".")
    parts = cleaned.split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    elif len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])
    else:
        return None
    return hours * 3600.0 + minutes * 60.0 + seconds


def compute_duration_from_subtitles(path):
    ends = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if not TIMECODE_RE.match(stripped):
                continue
            start_str, end_str = stripped.split(",", 1)
            start = parse_timecode(start_str)
            end = parse_timecode(end_str)
            if start is None or end is None:
                continue
            ends.append(end)
    if not ends:
        return None
    last_end = ends[-1]
    if len(ends) >= 2:
        prev_end = ends[-2]
        delta = last_end - prev_end
        if delta <= 0.0:
            delta = 1.0
        return round(last_end + delta, 3)
    return round(last_end + 1.0, 3)


def load_embeddings(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Embeddings JSON must be a list.")
    return data


def write_embeddings(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Add duration_sec to abriggs-itw-embeddings.json using subtitles."
    )
    parser.add_argument(
        "-i",
        "--input",
        default=os.path.join("assets", "abriggs-itw-embeddings.json"),
        help="Path to abriggs-itw-embeddings.json",
    )
    parser.add_argument(
        "-s",
        "--subtitles-dir",
        default=os.path.join("godot-viewer", "video"),
        help="Directory containing subtitle .txt files",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON path (defaults to overwrite input)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Embeddings file not found: {args.input}", file=sys.stderr)
        return 1
    if not os.path.isdir(args.subtitles_dir):
        print(f"Subtitles folder not found: {args.subtitles_dir}", file=sys.stderr)
        return 1

    data = load_embeddings(args.input)
    updated = 0
    missing = 0

    for entry in data:
        if not isinstance(entry, dict):
            continue
        filename = entry.get("filename")
        if not filename:
            continue
        base = os.path.splitext(filename)[0]
        subtitle_path = os.path.join(args.subtitles_dir, base + ".txt")
        if not os.path.exists(subtitle_path):
            missing += 1
            continue
        duration = compute_duration_from_subtitles(subtitle_path)
        if duration is None:
            missing += 1
            continue
        entry["duration_sec"] = duration
        updated += 1

    output_path = args.output or args.input
    write_embeddings(output_path, data)
    print(f"Updated {updated} entries. Missing {missing}. Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
