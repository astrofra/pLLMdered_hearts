import argparse
import subprocess
import sys
from pathlib import Path


def split_buzz(input_path, output_dir, count=6, duration=0.05, sample_rate=48000):
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    for idx in range(count):
        start = idx * duration
        out_path = output_dir / f"buzz_{idx}.ogg"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-af",
            "volume=0.25",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "libvorbis",
            "-y",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)


def main():
    default_input = Path(__file__).parent / (
        "719310__zazzsounddesign__dsgnsynth_digital-buzz-low-pitch-20_fc_sng.wav"
    )
    parser = argparse.ArgumentParser(description="Split buzz sample into 1s mono 48k OGG slices.")
    parser.add_argument("--input", default=str(default_input), help="Input WAV path.")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent), help="Output directory.")
    parser.add_argument("--count", type=int, default=6, help="Number of slices to write.")
    args = parser.parse_args()

    split_buzz(args.input, args.output_dir, count=args.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
