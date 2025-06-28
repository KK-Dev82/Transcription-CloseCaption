#!/usr/bin/env python3
"""
ตัวอย่างการใช้งาน Video Processing API
"""

import requests
import json
import time
import os
from pathlib import Path

# ตั้งค่า API URL
BASE_URL = "http://localhost:8000"
VIDEO_API_URL = f"{BASE_URL}/video"

def upload_video(file_path: str) -> dict:
    """อัปโหลดไฟล์วิดีโอ"""
    print(f"กำลังอัปโหลดไฟล์: {file_path}")
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'video/mp4')}
        response = requests.post(f"{VIDEO_API_URL}/upload", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"อัปโหลดสำเร็จ: {result['file_path']}")
        return result
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def trim_video(input_file: str, start_time: float, end_time: float) -> str:
    """ตัดวิดีโอ"""
    print(f"กำลังตัดวิดีโอ: {start_time}s - {end_time}s")
    
    data = {
        'input_file': input_file,
        'start_time': start_time,
        'end_time': end_time,
        'output_format': 'mp4',
        'quality': 'medium'
    }
    
    response = requests.post(f"{VIDEO_API_URL}/trim", data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"เริ่มการตัดวิดีโอ: {result['task_id']}")
        return result['task_id']
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def convert_format(input_file: str, output_format: str) -> str:
    """แปลงรูปแบบไฟล์"""
    print(f"กำลังแปลงรูปแบบเป็น: {output_format}")
    
    data = {
        'input_file': input_file,
        'output_format': output_format,
        'quality': 'medium'
    }
    
    response = requests.post(f"{VIDEO_API_URL}/convert", data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"เริ่มการแปลงรูปแบบ: {result['task_id']}")
        return result['task_id']
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def resize_video(input_file: str, width: int, height: int) -> str:
    """ปรับขนาดวิดีโอ"""
    print(f"กำลังปรับขนาดเป็น: {width}x{height}")
    
    data = {
        'input_file': input_file,
        'width': width,
        'height': height,
        'output_format': 'mp4',
        'quality': 'medium'
    }
    
    response = requests.post(f"{VIDEO_API_URL}/resize", data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"เริ่มการปรับขนาด: {result['task_id']}")
        return result['task_id']
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def merge_videos(input_files: list) -> str:
    """รวมวิดีโอหลายไฟล์"""
    print(f"กำลังรวมวิดีโอ {len(input_files)} ไฟล์")
    
    data = {
        'input_files': input_files,
        'output_format': 'mp4',
        'quality': 'medium'
    }
    
    response = requests.post(f"{VIDEO_API_URL}/merge", data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"เริ่มการรวมวิดีโอ: {result['task_id']}")
        return result['task_id']
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def batch_process(operations: list) -> str:
    """ประมวลผลแบบ batch"""
    print(f"กำลังประมวลผลแบบ batch: {len(operations)} operations")
    
    response = requests.post(f"{VIDEO_API_URL}/batch", json=operations)
    
    if response.status_code == 200:
        result = response.json()
        print(f"เริ่มการประมวลผลแบบ batch: {result['task_id']}")
        return result['task_id']
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def get_task_status(task_id: str) -> dict:
    """ดึงสถานะของ task"""
    response = requests.get(f"{VIDEO_API_URL}/status/{task_id}")
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def wait_for_completion(task_id: str, timeout: int = 300) -> bool:
    """รอให้ task เสร็จสิ้น"""
    print(f"รอให้ task {task_id} เสร็จสิ้น...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = get_task_status(task_id)
        
        if not status:
            return False
        
        print(f"สถานะ: {status['status']}")
        
        if status['status'] == 'completed':
            print("เสร็จสิ้น!")
            return True
        elif status['status'] == 'failed':
            print(f"ล้มเหลว: {status.get('error_message', 'Unknown error')}")
            return False
        
        time.sleep(5)
    
    print("หมดเวลา")
    return False

def download_result(task_id: str, output_path: str):
    """ดาวน์โหลดผลลัพธ์"""
    print(f"กำลังดาวน์โหลดผลลัพธ์: {output_path}")
    
    response = requests.get(f"{VIDEO_API_URL}/download/{task_id}")
    
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"ดาวน์โหลดสำเร็จ: {output_path}")
        return True
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return False

def get_video_info(file_path: str) -> dict:
    """ดึงข้อมูลวิดีโอ"""
    response = requests.get(f"{VIDEO_API_URL}/info/{file_path}")
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def main():
    """ตัวอย่างการใช้งานหลัก"""
    print("=== ตัวอย่างการใช้งาน Video Processing API ===\n")
    
    # 1. อัปโหลดไฟล์วิดีโอ
    video_file = "sample_video.mp4"  # เปลี่ยนเป็นไฟล์ที่มีอยู่จริง
    if not os.path.exists(video_file):
        print(f"ไม่พบไฟล์: {video_file}")
        print("กรุณาเตรียมไฟล์วิดีโอสำหรับทดสอบ")
        return
    
    upload_result = upload_video(video_file)
    if not upload_result:
        return
    
    input_file = upload_result['file_path']
    
    # 2. ดึงข้อมูลวิดีโอ
    print("\n--- ข้อมูลวิดีโอ ---")
    video_info = get_video_info(input_file)
    if video_info:
        print(json.dumps(video_info, indent=2, ensure_ascii=False))
    
    # 3. ตัดวิดีโอ
    print("\n--- ตัดวิดีโอ ---")
    trim_task_id = trim_video(input_file, 10.0, 30.0)  # ตัดช่วง 10-30 วินาที
    if trim_task_id:
        if wait_for_completion(trim_task_id):
            download_result(trim_task_id, "trimmed_video.mp4")
    
    # 4. แปลงรูปแบบ
    print("\n--- แปลงรูปแบบ ---")
    convert_task_id = convert_format(input_file, "avi")
    if convert_task_id:
        if wait_for_completion(convert_task_id):
            download_result(convert_task_id, "converted_video.avi")
    
    # 5. ปรับขนาด
    print("\n--- ปรับขนาด ---")
    resize_task_id = resize_video(input_file, 640, 480)
    if resize_task_id:
        if wait_for_completion(resize_task_id):
            download_result(resize_task_id, "resized_video.mp4")
    
    # 6. Batch processing
    print("\n--- Batch Processing ---")
    operations = [
        {
            "type": "trim",
            "input_file": input_file,
            "start_time": 0.0,
            "end_time": 15.0,
            "output_format": "mp4",
            "quality": "medium"
        },
        {
            "type": "convert",
            "input_file": input_file,
            "output_format": "mov",
            "quality": "medium"
        }
    ]
    
    batch_task_id = batch_process(operations)
    if batch_task_id:
        if wait_for_completion(batch_task_id):
            print("Batch processing เสร็จสิ้น")
    
    # 7. ดึงรายการ tasks ทั้งหมด
    print("\n--- รายการ Tasks ทั้งหมด ---")
    response = requests.get(f"{VIDEO_API_URL}/tasks")
    if response.status_code == 200:
        tasks = response.json()
        print(f"จำนวน tasks ทั้งหมด: {tasks['total']}")
        for task in tasks['tasks'][:5]:  # แสดง 5 tasks ล่าสุด
            print(f"- {task['task_id']}: {task['type']} ({task['status']})")

if __name__ == "__main__":
    main() 