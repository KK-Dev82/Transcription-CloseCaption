#!/usr/bin/env python3
"""
Script สำหรับตรวจสอบ task ที่ค้างใน queue
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import asyncio
import json
from datetime import datetime
from app.services.rabbitmq_service import RabbitMQService
from app.utils.storage_factory import get_storage

async def check_stuck_task(task_id: str):
    """ตรวจสอบ task ที่ค้าง"""
    print("=" * 80)
    print(f"🔍 ตรวจสอบ Task: {task_id}")
    print("=" * 80)
    print()
    
    # 1. ตรวจสอบจาก Storage
    print("📦 1. ตรวจสอบจาก Storage...")
    storage = get_storage()
    task_data = storage.load_transcription(task_id)
    
    if task_data:
        print(f"   ✅ พบ task ใน storage")
        print(f"   Status: {task_data.get('status', 'unknown')}")
        print(f"   Progress: {task_data.get('progress', 0)}%")
        print(f"   Created: {task_data.get('created_at', 'N/A')}")
        print(f"   Updated: {task_data.get('updated_at', 'N/A')}")
        print(f"   Current Stage: {task_data.get('current_stage', 'N/A')}")
        print(f"   Stage Description: {task_data.get('current_stage_description', 'N/A')}")
        print(f"   File Path: {task_data.get('file_path', 'N/A')}")
        if task_data.get('error_message'):
            print(f"   ❌ Error: {task_data.get('error_message')}")
    else:
        print(f"   ⚠️ ไม่พบ task ใน storage")
    
    print()
    
    # 2. ตรวจสอบ Queue Status
    print("📋 2. ตรวจสอบ Queue Status...")
    rabbitmq = RabbitMQService()
    
    try:
        queue_info = rabbitmq.get_queue_info()
        
        # ตรวจสอบ audio_extraction_queue
        audio_extraction_queue = queue_info.get('audio_extraction_queue', {})
        print(f"   audio_extraction_queue:")
        print(f"     Messages Ready: {audio_extraction_queue.get('message_count', 0)}")
        print(f"     Consumers: {audio_extraction_queue.get('consumer_count', 0)}")
        print(f"     Unacked: {audio_extraction_queue.get('messages_unacknowledged', 0)}")
        
        if audio_extraction_queue.get('consumer_count', 0) == 0:
            print(f"     ⚠️ ไม่มี consumer - ต้อง restart Video Worker")
        
        # ตรวจสอบ transcription_request_queue
        transcription_request_queue = queue_info.get('transcription_request_queue', {})
        print(f"   transcription_request_queue:")
        print(f"     Messages Ready: {transcription_request_queue.get('message_count', 0)}")
        print(f"     Consumers: {transcription_request_queue.get('consumer_count', 0)}")
        print(f"     Unacked: {transcription_request_queue.get('messages_unacknowledged', 0)}")
        
        # ตรวจสอบ transcription_queue
        transcription_queue = queue_info.get('transcription_queue', {})
        print(f"   transcription_queue:")
        print(f"     Messages Ready: {transcription_queue.get('message_count', 0)}")
        print(f"     Consumers: {transcription_queue.get('consumer_count', 0)}")
        print(f"     Unacked: {transcription_queue.get('messages_unacknowledged', 0)}")
        
    except Exception as e:
        print(f"   ❌ Error checking queue: {e}")
    
    print()
    
    # 3. ตรวจสอบ Worker Status
    print("⚙️ 3. ตรวจสอบ Worker Status...")
    try:
        import subprocess
        result = subprocess.run(
            ["pgrep", "-f", "python.*video_worker"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"   ✅ Video Worker กำลังทำงาน (PIDs: {', '.join(pids)})")
        else:
            print(f"   ❌ Video Worker ไม่ทำงาน")
    except Exception as e:
        print(f"   ⚠️ ไม่สามารถตรวจสอบ worker: {e}")
    
    print()
    
    # 4. ตรวจสอบ File
    if task_data and task_data.get('file_path'):
        file_path = task_data.get('file_path')
        print(f"📁 4. ตรวจสอบ File: {file_path}")
        if Path(file_path).exists():
            size = Path(file_path).stat().st_size / (1024 * 1024)  # MB
            print(f"   ✅ ไฟล์มีอยู่ (Size: {size:.2f} MB)")
        else:
            print(f"   ❌ ไฟล์ไม่พบ!")
    
    print()
    print("=" * 80)
    print("💡 คำแนะนำ:")
    print("   1. ถ้า task ค้างใน queue แต่ไม่มี consumer → Restart Video Worker")
    print("   2. ถ้า task มี error_message → ตรวจสอบ error และ retry")
    print("   3. ถ้าไฟล์ไม่พบ → Task อาจจะ fail แล้ว")
    print("=" * 80)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_stuck_task.py <task_id>")
        sys.exit(1)
    
    task_id = sys.argv[1]
    asyncio.run(check_stuck_task(task_id))
