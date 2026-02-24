#!/usr/bin/env python3
"""
เปรียบเทียบ Chunk Group vs Flow ปกติ
- Chunk Group: ใช้ไฟล์ pre-chunked (ข้าม extract + create_chunks)
- Normal: ใช้ไฟล์ต้นฉบับ (extract + create_chunks + transcribe)

วิธีใช้:
  1. ต้องมี RQ workers รันอยู่
  2. python scripts/compare_chunk_group_vs_normal.py
  3. เปิด terminal อื่นรัน: vmstat 2 หรือ top เพื่อดู CPU
  4. รอจนทั้ง 2 tasks เสร็จ แล้วดูผลจาก Dashboard หรือ API
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.runpod", override=False)


def run_both():
    from app.api.transcribe import start_transcription, TranscriptionRequest

    base = "uploads/0e692d52-364e-424a-8f1a-4903c30cdaeb_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c"
    chunk_dir = Path(base)
    original_wav = f"{base}.wav"

    if not chunk_dir.exists() or not Path(original_wav).exists():
        print("ไม่พบไฟล์ - รัน split_wav_to_chunks.py ก่อน")
        return 1

    chunks = sorted(chunk_dir.glob("chunk_*.wav"))
    file_paths = [str(p).replace("\\", "/") for p in chunks]

    print("=" * 70)
    print("เปรียบเทียบ Chunk Group vs Normal Flow")
    print("=" * 70)
    print(f"ต้นฉบับ: {original_wav} (~33 นาที)")
    print(f"Chunks: {len(file_paths)} ไฟล์ (240s แต่ละไฟล์)")
    print()

    results = {}

    # 1. Chunk Group
    print("1. ส่ง Chunk Group request...")
    t0 = time.time()
    req_cg = TranscriptionRequest(file_paths=file_paths, chunk_group=True, language="th")
    r_cg = asyncio.run(start_transcription(req_cg))
    t_cg = time.time() - t0
    results["chunk_group"] = {"task_id": r_cg["task_id"], "enqueue_time": t_cg}
    print(f"   Task ID: {r_cg['task_id']}")
    print(f"   เวลา enqueue: {t_cg:.2f}s")
    print()

    # 2. Normal
    print("2. ส่ง Normal request (ไฟล์ต้นฉบับ)...")
    t0 = time.time()
    req_norm = TranscriptionRequest(file_path=original_wav, language="th")
    r_norm = asyncio.run(start_transcription(req_norm))
    t_norm = time.time() - t0
    results["normal"] = {"task_id": r_norm["task_id"], "enqueue_time": t_norm}
    print(f"   Task ID: {r_norm['task_id']}")
    print(f"   เวลา enqueue: {t_norm:.2f}s")
    print()

    print("=" * 70)
    print("สรุป")
    print("=" * 70)
    print(f"Chunk Group: {results['chunk_group']['task_id']}")
    print(f"Normal:      {results['normal']['task_id']}")
    print()
    print("ดูสถานะ: GET /api/v2/tasks/{task_id}")
    print("หรือ Dashboard: /status")
    print()
    print("คาดว่า Chunk Group จะ:")
    print("  - ใช้ CPU น้อยกว่า (ข้าม extract ~10-15s + create_chunks ~5-10s)")
    print("  - เริ่ม transcribe เร็วขึ้น (ไม่ต้องรอ preprocess)")
    return 0


if __name__ == "__main__":
    sys.exit(run_both())
