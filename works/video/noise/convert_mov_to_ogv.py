from __future__ import annotations

import subprocess
from pathlib import Path


def find_mov_files(folder: Path) -> list[Path]:
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".mov"]
    )


def build_output_path(input_path: Path) -> Path:
    return input_path.with_suffix(".ogv")


def convert_file(input_path: Path, output_path: Path) -> int:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libtheora",
        "-q:v",
        "8",
        "-c:a",
        "libvorbis",
        "-q:a",
        "5",
        str(output_path),
    ]
    result = subprocess.run(cmd)
    return result.returncode


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    mov_files = find_mov_files(script_dir)
    if not mov_files:
        print(f"No .MOV files found in: {script_dir}")
        return 0

    failures = 0
    for mov in mov_files:
        out = build_output_path(mov)
        print(f"Converting {mov.name} -> {out.name}")
        code = convert_file(mov, out)
        if code != 0:
            print(f"Failed: {mov.name}")
            failures += 1

    if failures:
        print(f"{failures} file(s) failed.")
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
