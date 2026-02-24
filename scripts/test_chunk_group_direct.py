#!/usr/bin/env python3
"""
ทดสอบ Chunk Group โดยเรียก logic โดยตรง (ไม่ผ่าน HTTP)
ใช้เมื่อ API ไม่พร้อมหรือต้องการทดสอบแบบ standalone
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# เพิ่ม project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# โหลด env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.runpod", override=False)


def main():
    # Import หลังโหลด path
    from app.api.transcribe import start_transcription, TranscriptionRequest

    chunk_dir = Path("uploads/0e692d52-364e-424a-8f1a-4903c30cdaeb_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c")
    if not chunk_dir.exists():
        print(f"ไม่พบโฟลเดอร์: {chunk_dir}")
        return 1

    chunks = sorted(chunk_dir.glob("chunk_*.wav"))
    file_paths = [str(p).replace("\\", "/") for p in chunks]
    if not file_paths:
        print("ไม่พบ chunks")
        return 1

    print("=" * 60)
    print("ทดสอบ Chunk Group (Direct API call)")
    print("=" * 60)
    print(f"Chunks: {len(file_paths)} ไฟล์")
    for i, p in enumerate(file_paths[:3]):
        print(f"  {i}: {Path(p).name}")
    if len(file_paths) > 3:
        print(f"  ... และอีก {len(file_paths)-3} ไฟล์")
    print()

    req = TranscriptionRequest(
        file_paths=file_paths,
        chunk_group=True,
        language="th",
    )

    print("เรียก start_transcription (chunk_group)...")
    t0 = time.time()
    try:
        result = asyncio.run(start_transcription(req))
        elapsed = time.time() - t0
        print(f"Response ({elapsed:.2f}s):")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\nTask ID: {result.get('task_id')}")
        print("หมายเหตุ: ต้องมี RQ workers รันอยู่ job ถึงจะประมวลผล")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
