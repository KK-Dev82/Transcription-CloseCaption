#!/usr/bin/env python3
"""
ดาวน์โหลดไฟล์มีเดียจาก /api/video/list

ใช้:
  export MAIN_API_URL=https://your-pod.proxy.runpod.net  # หรือ API_BASE_URL
  python scripts/download_from_video_list.py [--base-url URL] [--ids 1,2,3] [--output-dir ./downloads]

Environment:
  MAIN_API_URL  - Base URL ของ API (ใช้ก่อน API_BASE_URL)
  API_BASE_URL  - Fallback base URL

ตัวอย่าง Download Endpoints:
  # 1. ดาวน์โหลดไฟล์เดียว (ใช้ file_path จาก /api/video/list)
  GET {BASE}/api/upload/download?file_path=uploads/xxx.mp4

  # 2. ดาวน์โหลดหลายไฟล์เป็น ZIP (selection)
  POST {BASE}/api/upload/selection/download
  Body: {"ids": [43, 42]} หรือ {"file_paths": ["uploads/a.mp4", "uploads/b.mp3"]}

รายละเอียดเพิ่มเติม: docs/DOWNLOAD_EXAMPLES.md
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request


def _get_base_url() -> str:
    """ดึง base URL จาก env (MAIN_API_URL > API_BASE_URL > localhost)"""
    url = (
        os.getenv("MAIN_API_URL", "").strip()
        or os.getenv("API_BASE_URL", "").strip()
    )
    if url:
        return url.rstrip("/")
    return "http://localhost:8010"


def fetch_list(base_url: str) -> dict:
    url = f"{base_url.rstrip('/')}/api/video/list"
    with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=30) as r:
        return json.loads(r.read().decode())


def download_file(base_url: str, file_path: str, output_path: Path) -> bool:
    url = f"{base_url.rstrip('/')}/api/upload/download?{urlencode({'file_path': file_path})}"
    try:
        req = Request(url, headers={"User-Agent": "download-script/1.0"})
        with urlopen(req, timeout=300) as r:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(r.read())
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}", file=sys.stderr)
        return False


def main():
    p = argparse.ArgumentParser(description="ดาวน์โหลดไฟล์จาก /api/video/list")
    p.add_argument(
        "--base-url",
        default=None,
        help="Base URL ของ API (default: MAIN_API_URL หรือ API_BASE_URL จาก env, fallback localhost:8010)",
    )
    p.add_argument("--ids", type=str, help="ID ที่ต้องการ (คั่นด้วย comma) เช่น 43,42,30")
    p.add_argument("--output-dir", default="./downloads", help="โฟลเดอร์เก็บไฟล์")
    p.add_argument("--list-only", action="store_true", help="แสดงรายการเท่านั้น ไม่ดาวน์โหลด")
    args = p.parse_args()

    base_url = (args.base_url or _get_base_url()).rstrip("/")
    data = fetch_list(base_url)
    videos = data.get("videos", [])
    audios = data.get("audios", [])
    all_files = videos + audios

    if not all_files:
        print("ไม่พบไฟล์ในรายการ")
        return 1

    # แสดงรายการ
    print(f"พบ {len(all_files)} ไฟล์ (videos: {len(videos)}, audios: {len(audios)})\n")
    for f in all_files:
        fid = f.get("id", "?")
        name = f.get("filename", f.get("file_path", "").split("/")[-1])
        ftype = f.get("file_type", "-")
        dur = f.get("duration_formatted", "-")
        size = f.get("file_size", 0)
        size_mb = f"{size / (1024*1024):.2f} MB" if size else "-"
        print(f"  ID {fid:3} | {ftype:5} | {dur:>6} | {size_mb:>10} | {name}")

    if args.list_only:
        return 0

    # เลือกไฟล์ที่จะดาวน์โหลด
    ids = []
    if args.ids:
        ids = [int(x.strip()) for x in args.ids.split(",") if x.strip()]
    else:
        print("\nใช้ --ids 43,42,30 เพื่อดาวน์โหลด (หรือกด Enter เพื่อยกเลิก)")
        inp = input("ใส่ IDs (คั่นด้วย comma): ").strip()
        if not inp:
            return 0
        ids = [int(x.strip()) for x in inp.split(",") if x.strip()]

    id_set = set(ids)
    to_download = [f for f in all_files if f.get("id") in id_set]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nดาวน์โหลด {len(to_download)} ไฟล์ไปที่ {out_dir}\n")
    for f in to_download:
        fid = f.get("id")
        file_path = f.get("file_path")
        filename = f.get("filename", file_path.split("/")[-1] if file_path else f"file_{fid}")
        out_path = out_dir / filename
        print(f"  [{fid}] {filename} ... ", end="", flush=True)
        if download_file(base_url, file_path, out_path):
            print("OK")
        else:
            print("FAILED")

    return 0


if __name__ == "__main__":
    sys.exit(main())
