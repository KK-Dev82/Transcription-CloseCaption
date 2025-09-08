#!/usr/bin/env python3
"""
สคริปต์ทดสอบ Video Trim API
"""

import requests
import json
import time
import os

# API Configuration
API_BASE_URL = "http://localhost:8001"

def test_health():
    """ทดสอบ health check"""
    print("🔍 ทดสอบ Health Check...")
    response = requests.get(f"{API_BASE_URL}/health")
    if response.status_code == 200:
        print("✅ Health Check สำเร็จ")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ Health Check ล้มเหลว: {response.status_code}")
    print()

def test_queue_info():
    """ทดสอบ queue info"""
    print("🔍 ทดสอบ Queue Info...")
    response = requests.get(f"{API_BASE_URL}/queue/info")
    if response.status_code == 200:
        print("✅ Queue Info สำเร็จ")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ Queue Info ล้มเหลว: {response.status_code}")
    print()

def test_video_tasks():
    """ทดสอบ video tasks"""
    print("🔍 ทดสอบ Video Tasks...")
    response = requests.get(f"{API_BASE_URL}/video/tasks")
    if response.status_code == 200:
        print("✅ Video Tasks สำเร็จ")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ Video Tasks ล้มเหลว: {response.status_code}")
    print()

def test_video_trim():
    """ทดสอบ video trim"""
    print("🔍 ทดสอบ Video Trim...")
    
    # สร้างไฟล์วิดีโอตัวอย่าง (ถ้ายังไม่มี)
    test_video_path = "test_video.mp4"
    if not os.path.exists(test_video_path):
        print(f"⚠️  ไม่พบไฟล์ {test_video_path} กรุณาสร้างไฟล์วิดีโอตัวอย่าง")
        return
    
    # อัปโหลดไฟล์
    print("📤 อัปโหลดไฟล์วิดีโอ...")
    with open(test_video_path, 'rb') as f:
        files = {'file': (test_video_path, f, 'video/mp4')}
        response = requests.post(f"{API_BASE_URL}/video/upload", files=files)
    
    if response.status_code != 200:
        print(f"❌ อัปโหลดไฟล์ล้มเหลว: {response.status_code}")
        return
    
    upload_result = response.json()
    file_path = upload_result.get('file_path')
    print(f"✅ อัปโหลดสำเร็จ: {file_path}")
    
    # ส่งงาน trim
    print("✂️ ส่งงาน Video Trim...")
    trim_data = {
        "file_path": file_path,
        "start_time": 10.0,  # เริ่มที่ 10 วินาที
        "duration": 30.0,    # ความยาว 30 วินาที
        "output_format": "mp4"
    }
    
    response = requests.post(f"{API_BASE_URL}/video/trim", json=trim_data)
    if response.status_code == 200:
        print("✅ ส่งงาน Video Trim สำเร็จ")
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        task_id = result.get('task_id')
        if task_id:
            print(f"🔄 ติดตามสถานะงาน: {task_id}")
            
            # ติดตามสถานะ
            for i in range(10):
                time.sleep(2)
                status_response = requests.get(f"{API_BASE_URL}/video/status/{task_id}")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"📊 สถานะ: {status_data.get('status')} - {status_data.get('progress', 0)}%")
                    
                    if status_data.get('status') in ['completed', 'failed']:
                        print("✅ งานเสร็จสิ้น")
                        print(json.dumps(status_data, indent=2, ensure_ascii=False))
                        break
                else:
                    print(f"❌ ไม่สามารถตรวจสอบสถานะได้: {status_response.status_code}")
    else:
        print(f"❌ ส่งงาน Video Trim ล้มเหลว: {response.status_code}")
        print(response.text)
    print()

def main():
    """ฟังก์ชันหลัก"""
    print("🚀 เริ่มทดสอบ Video Trim Service")
    print("=" * 50)
    
    # ทดสอบ health
    test_health()
    
    # ทดสอบ queue info
    test_queue_info()
    
    # ทดสอบ video tasks
    test_video_tasks()
    
    # ทดสอบ video trim
    test_video_trim()
    
    print("🏁 เสร็จสิ้นการทดสอบ")

if __name__ == "__main__":
    main() 