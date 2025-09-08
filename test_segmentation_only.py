#!/usr/bin/env python3
"""
สคริปต์ทดสอบการแบ่งตอนวิดีโออย่างเดียว
แบ่งวิดีโอเป็นตอนละ 600 วินาที (10 นาที) พร้อม overlap 5 วินาที
"""

import requests
import json
import time
import os
from datetime import datetime

API_BASE_URL = "http://localhost:8001"

def upload_video(video_path):
    """อัปโหลดไฟล์วิดีโอ"""
    print(f"📤 อัปโหลดไฟล์: {video_path}")
    
    with open(video_path, 'rb') as f:
        files = {'file': (os.path.basename(video_path), f, 'video/mp4')}
        response = requests.post(f"{API_BASE_URL}/video/upload", files=files)
    
    if response.status_code == 200:
        result = response.json()
        file_path = result.get('file_path')
        print(f"✅ อัปโหลดสำเร็จ: {file_path}")
        return file_path
    else:
        print(f"❌ อัปโหลดล้มเหลว: {response.status_code}")
        print(f"Error: {response.text}")
        return None

def start_segmentation(file_path):
    """เริ่มการแบ่งตอนวิดีโอ"""
    print(f"🚀 เริ่ม Video Segmentation")
    print(f"📹 ไฟล์: {file_path}")
    print(f"⏱️  ตอนละ: 600 วินาที (10 นาที)")
    print(f"🔄 Overlap: 5 วินาที")
    print(f"🎤 ทำ transcription ทันทีหลังตัดแต่ละตอน")
    
    data = {
        "file_path": file_path,
        "segment_duration": 600,
        "overlap": 5,
        "language": "th",
        "model_size": "base"
    }
    
    response = requests.post(f"{API_BASE_URL}/video/segment", json=data)
    if response.status_code == 200:
        result = response.json()
        task_id = result.get('task_id')
        print(f"✅ ส่งงาน segmentation: {task_id}")
        return task_id
    else:
        print(f"❌ ส่งงาน segmentation ล้มเหลว: {response.status_code}")
        print(f"Error: {response.text}")
        return None

def check_job_status(task_id):
    """ตรวจสอบสถานะงาน"""
    response = requests.get(f"{API_BASE_URL}/video/segment/{task_id}")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ ตรวจสอบสถานะล้มเหลว: {response.status_code}")
        return None

def wait_for_completion(task_id, timeout=1200):
    """รอให้งานเสร็จสิ้น"""
    print(f"⏳ รอ segmentation {task_id}...")
    
    for i in range(timeout // 5):  # ตรวจสอบทุก 5 วินาที
        time.sleep(5)
        
        status_data = check_job_status(task_id)
        if status_data:
            status = status_data.get('status')
            progress = status_data.get('progress', 0)
            current_segment = status_data.get('current_segment', 0)
            total_segments = status_data.get('total_segments', 0)
            
            if total_segments > 0:
                print(f"📊 Status: {status} - Progress: {progress}% - Segment: {current_segment}/{total_segments}")
            else:
                print(f"📊 Status: {status} - Progress: {progress}%")
            
            if status == 'completed':
                print(f"✅ Segmentation เสร็จสิ้น")
                return status_data
            elif status == 'failed':
                print(f"❌ Segmentation ล้มเหลว")
                return None
        
        if i % 12 == 0:  # แสดงสถานะทุก 1 นาที
            print(f"⏰ รอมาแล้ว {(i+1)*5} วินาที...")
    
    print(f"⏰ Segmentation หมดเวลา")
    return None

def show_results(results):
    """แสดงผลลัพธ์"""
    print("\n📊 สรุปผลลัพธ์")
    print("=" * 50)
    
    segments = results.get('segments', [])
    print(f"จำนวน segments: {len(segments)}")
    
    total_duration = 0
    total_text = ""
    
    for i, segment in enumerate(segments):
        start_time = segment.get('start_time', 0)
        end_time = segment.get('end_time', 0)
        duration = end_time - start_time
        total_duration += duration
        
        transcription = segment.get('transcription', {})
        text = transcription.get('text', '')
        total_text += f"[{start_time:.1f}s-{end_time:.1f}s] {text}\n"
        
        print(f"Segment {i+1}: {start_time:.1f}s-{end_time:.1f}s ({duration:.1f}s) - {len(text)} ตัวอักษร")
    
    print(f"\n⏱️  ความยาวรวม: {total_duration:.1f} วินาที ({total_duration/60:.1f} นาที)")
    print(f"📝 ข้อความรวม: {len(total_text)} ตัวอักษร")
    
    # บันทึกข้อความรวม
    with open("full_transcription.txt", 'w', encoding='utf-8') as f:
        f.write(total_text)
    
    print("📄 บันทึกข้อความรวม: full_transcription.txt")

def main():
    """ฟังก์ชันหลัก"""
    print("🎬 เริ่มทดสอบการแบ่งตอนวิดีโอ")
    print("=" * 60)
    
    # 1. อัปโหลดวิดีโอ
    video_path = "test_video.mp4"
    if not os.path.exists(video_path):
        print(f"❌ ไม่พบไฟล์: {video_path}")
        return
    
    file_path = upload_video(video_path)
    if not file_path:
        return
    
    # 2. เริ่มการแบ่งตอน
    task_id = start_segmentation(file_path)
    if not task_id:
        return
    
    # 3. รอให้เสร็จสิ้น
    results = wait_for_completion(task_id)
    if not results:
        print("❌ การแบ่งตอนล้มเหลว")
        return
    
    # 4. แสดงผลลัพธ์
    show_results(results)
    
    print("\n🎉 การทดสอบเสร็จสิ้น!")

if __name__ == "__main__":
    main() 