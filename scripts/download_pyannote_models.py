#!/usr/bin/env python3
"""
Download pyannote Speaker Diarization models สำหรับ offline use

Usage:
  python scripts/download_pyannote_models.py [--output-dir PATH]

ต้อง:
  1. Accept conditions บน HuggingFace: pyannote/segmentation-3.0, pyannote/speaker-diarization-3.1
  2. ตั้ง PYANNOTE_HF_TOKEN หรือ HF_PYANNOTE_TOKEN ใน env
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Download pyannote diarization models for offline use")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="models/pyannote-speaker-diarization-3.1",
        help="Output directory for model files",
    )
    args = parser.parse_args()

    token = os.getenv("PYANNOTE_HF_TOKEN") or os.getenv("HF_PYANNOTE_TOKEN") or os.getenv("HF_TOKEN")
    if not token:
        print("ERROR: Set PYANNOTE_HF_TOKEN, HF_PYANNOTE_TOKEN หรือ HF_TOKEN")
        print("Get token from: https://hf.co/settings/tokens")
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    try:
        from huggingface_hub import snapshot_download

        print("Downloading pyannote/speaker-diarization-3.1...")
        path = snapshot_download(
            repo_id="pyannote/speaker-diarization-3.1",
            local_dir=str(output_dir),
            token=token,
            local_dir_use_symlinks=False,
        )
        print(f"Downloaded to {path}")
        print(f"\nSet in .env.runpod:")
        print(f"  PYANNOTE_MODEL_DIR={path}")
    except Exception as e:
        print(f"huggingface_hub failed: {e}")
        print("\nTrying git clone (requires git-lfs)...")
        repo_url = f"https://hf_user:{token}@hf.co/pyannote/speaker-diarization-3.1"
        result = subprocess.run(
            ["git", "clone", repo_url, str(output_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"git clone failed: {result.stderr}")
            sys.exit(1)
        print(f"Cloned to {output_dir}")
        print(f"\nSet in .env.runpod:")
        print(f"  PYANNOTE_MODEL_DIR={output_dir}")


if __name__ == "__main__":
    main()
