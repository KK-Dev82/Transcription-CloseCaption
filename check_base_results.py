#!/usr/bin/env python3
"""
สคริปต์ตรวจสอบสถานะและคำนวณเวลาที่ใช้สำหรับ 25 requests (model base)
"""
import json
from pathlib import Path
from datetime import datetime
import time

# โหลด task IDs
task_ids_file = "/tmp/test_25_requests_base_task_ids.json"
with open(task_ids_file, 'r') as f:
    data = json.load(f)
    task_ids = data["task_ids"]
    request_timestamp = data.get("timestamp")

print("=" * 70)
print("⏱️  ตรวจสอบสถานะและคำนวณเวลาที่ใช้ (model base)")
print("=" * 70)
print()

# ตรวจสอบ tasks จาก storage
storage_dir = Path("storage/transcriptions")
completed_tasks = []

for task_id in task_ids:
    task_dir = storage_dir / task_id
    if task_dir.exists():
        metadata_file = task_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
                status = task_data.get("status", "unknown")
                created_at = task_data.get("created_at", "")
                completed_at = task_data.get("completed_at", "")
                
                if status == "completed" and created_at and completed_at:
                    try:
                        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        completed = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        elapsed = (completed - created).total_seconds() / 60
                        
                        completed_tasks.append({
                            "task_id": task_id,
                            "elapsed": elapsed,
                            "created": created,
                            "completed": completed
                        })
                    except:
                        pass

print(f"📊 สถานะ:")
print(f"   ✅ Completed: {len(completed_tasks)}/{len(task_ids)}")
print()

if completed_tasks:
    # เรียงตามเวลาที่สร้าง
    completed_tasks.sort(key=lambda t: t["created"])
    
    max_elapsed = max(t["elapsed"] for t in completed_tasks)
    min_elapsed = min(t["elapsed"] for t in completed_tasks)
    avg_elapsed = sum(t["elapsed"] for t in completed_tasks) / len(completed_tasks)
    
    # เวลารวม (จาก task แรกถึง task สุดท้าย)
    first_created = completed_tasks[0]["created"]
    last_completed = max(t["completed"] for t in completed_tasks)
    total_time = (last_completed - first_created).total_seconds() / 60
    
    print(f"⏱️  เวลาที่ใช้ต่อ Task:")
    print(f"   - Min: {min_elapsed:.1f} นาที")
    print(f"   - Max: {max_elapsed:.1f} นาที")
    print(f"   - Average: {avg_elapsed:.1f} นาที")
    print()
    print(f"⏱️  เวลารวม (Sequential - จาก task แรกถึง task สุดท้าย):")
    print(f"   - Total: {total_time:.1f} นาที")
    print()
    print(f"⏱️  เวลาที่ใช้จริง (Parallel Processing):")
    print(f"   - เวลาที่ใช้: ~{max_elapsed:.1f} นาที")
    print(f"   - (ใช้เวลาของ task ที่ช้าที่สุด เพราะ parallel processing)")
    print()
    
    # คำนวณ throughput
    total_audio_minutes = len(completed_tasks) * 30  # 30 นาทีต่อ video
    speedup = total_audio_minutes / max_elapsed if max_elapsed > 0 else 0
    
    print(f"📊 Throughput Analysis:")
    print(f"   - Total audio: {total_audio_minutes} นาทีเสียง ({len(completed_tasks)} videos × 30 นาที)")
    print(f"   - Time used: {max_elapsed:.1f} นาที")
    print(f"   - Speedup: {speedup:.1f}x realtime")
    print()
    
    # เปรียบเทียบกับเป้าหมาย
    target_time = 10
    print(f"🎯 เปรียบเทียบกับเป้าหมาย (10 นาที):")
    if max_elapsed <= target_time:
        print(f"   ✅ ผ่านเป้าหมาย ({max_elapsed:.1f} ≤ {target_time})")
    else:
        print(f"   ❌ ไม่ผ่านเป้าหมาย ({max_elapsed:.1f} > {target_time})")
        print(f"   - เกินเป้าหมาย: {max_elapsed - target_time:.1f} นาที")
        print(f"   - ต้องใช้: {max_elapsed / target_time:.1f}x เร็วกว่า")
    print()
    
    # เปรียบเทียบกับ tiny model
    print(f"📊 เปรียบเทียบกับ Tiny Model:")
    tiny_time = 12.7
    print(f"   - Tiny model: ~{tiny_time:.1f} นาที")
    print(f"   - Base model: ~{max_elapsed:.1f} นาที")
    if max_elapsed > tiny_time:
        slower_pct = ((max_elapsed / tiny_time - 1) * 100)
        slower_min = max_elapsed - tiny_time
        print(f"   - Base model ช้ากว่า: {slower_min:.1f} นาที ({slower_pct:.1f}% ช้ากว่า)")
    else:
        faster_pct = ((tiny_time / max_elapsed - 1) * 100)
        faster_min = tiny_time - max_elapsed
        print(f"   - Base model เร็วกว่า: {faster_min:.1f} นาที ({faster_pct:.1f}% เร็วกว่า)")
    print()
    
    print("=" * 70)
    print("💡 สรุป:")
    print("=" * 70)
    print()
    print(f"✅ 25 requests (video 30 นาที) ใช้เวลา: ~{max_elapsed:.1f} นาที")
    print(f"   - ใช้ model base")
    print(f"   - Parallel processing กับ 4 GPUs")
    print(f"   - Speedup: {speedup:.1f}x realtime")
else:
    print("⚠️  ยังไม่มี tasks ที่เสร็จแล้ว")
    print("   - Tasks กำลังประมวลผลอยู่")
    print("   - Base model ใช้เวลานานกว่า tiny model")
    print()
    print("💡 ตรวจสอบอีกครั้งในภายหลัง:")
    print("   python3 check_base_results.py")

