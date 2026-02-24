#!/usr/bin/env python3
"""
แบ่งไฟล์ .wav เป็น chunks ตาม duration (default 240 วินาที)
เก็บที่ uploads/{base_name}/chunk_0000.wav, chunk_0001.wav, ...
"""
import argparse
import subprocess
import sys
from pathlib import Path


def get_duration_seconds(file_path: str) -> float:
    """ใช้ ffprobe ดึง duration"""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip())


def split_wav_to_chunks(
    input_path: str,
    chunk_duration: int = 240,
    output_dir: str = None,
) -> list[str]:
    """
    แบ่ง wav เป็น chunks ด้วย ffmpeg -segment_time
    Returns: list of output chunk paths
    """
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์: {input_path}")

    base_name = input_path.stem
    if output_dir is None:
        output_dir = input_path.parent / base_name
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ใช้ -segment_time แทน -f segment เพื่อแบ่งตามเวลา
    # output pattern: chunk_0000.wav, chunk_0001.wav, ...
    output_pattern = str(output_dir / "chunk_%04d.wav")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-f", "segment",
        "-segment_time", str(chunk_duration),
        "-acodec", "copy",  # copy ไม่ต้อง re-encode (เร็ว)
        "-reset_timestamps", "1",
        output_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    # รายการ chunks ที่สร้าง (เรียงตามชื่อ)
    chunks = sorted(output_dir.glob("chunk_*.wav"))
    return [str(c) for c in chunks]


def main():
    parser = argparse.ArgumentParser(description="แบ่ง wav เป็น chunks 240s")
    parser.add_argument("input", help="Path to .wav file")
    parser.add_argument("-d", "--chunk-duration", type=int, default=240,
                        help="Duration per chunk (seconds), default 240")
    parser.add_argument("-o", "--output-dir", default=None,
                        help="Output directory (default: uploads/{basename}/)")
    args = parser.parse_args()

    try:
        duration = get_duration_seconds(args.input)
        print(f"Duration: {duration:.1f}s ({duration/60:.1f} min)")
        expected = int(duration / args.chunk_duration) + (1 if duration % args.chunk_duration else 0)
        print(f"Expected chunks: ~{expected} (at {args.chunk_duration}s each)")

        chunks = split_wav_to_chunks(
            args.input,
            chunk_duration=args.chunk_duration,
            output_dir=args.output_dir,
        )
        print(f"Created {len(chunks)} chunks:")
        for p in chunks:
            print(f"  {p}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
