#!/usr/bin/env python3
"""
ตัวอย่างการใช้งาน Video Processing กับ RabbitMQ
"""

import asyncio
import time
import requests
import json
from pathlib import Path

# API Base URL
API_BASE_URL = "http://localhost:8001"

def upload_video(file_path: str) -> str:
    """อัปโหลดไฟล์วิดีโอ"""
    print(f"กำลังอัปโหลดไฟล์: {file_path}")
    
    with open(file_path, 'rb') as f:
        files = {'file': (Path(file_path).name, f, 'video/mp4')}
        response = requests.post(f"{API_BASE_URL}/upload", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"อัปโหลดสำเร็จ: {result['file_path']}")
        return result['file_path']
    else:
        print(f"เกิดข้อผิดพลาดในการอัปโหลด: {response.text}")
        return None

def trim_video(input_file: str, start_time: float, end_time: float) -> str:
    """ตัดวิดีโอ"""
    print(f"ส่งคำขอตัดวิดีโอ: {start_time}s - {end_time}s")
    
    data = {
        'input_file': input_file,
        'start_time': start_time,
        'end_time': end_time,
        'output_format': 'mp4',
        'quality': 'medium'
    }
    
    response = requests.post(f"{API_BASE_URL}/video/trim", data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"ส่งคำขอสำเร็จ: {result['task_id']}")
        return result['task_id']
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def merge_videos(input_files: list) -> str:
    """รวมวิดีโอ"""
    print(f"ส่งคำขอรวมวิดีโอ: {len(input_files)} ไฟล์")
    
    data = {
        'input_files': input_files,
        'output_format': 'mp4',
        'quality': 'high'
    }
    
    response = requests.post(f"{API_BASE_URL}/video/merge", data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"ส่งคำขอสำเร็จ: {result['task_id']}")
        return result['task_id']
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def convert_format(input_file: str, output_format: str) -> str:
    """แปลงรูปแบบไฟล์"""
    print(f"ส่งคำขอแปลงรูปแบบ: {output_format}")
    
    data = {
        'input_file': input_file,
        'output_format': output_format,
        'quality': 'medium'
    }
    
    response = requests.post(f"{API_BASE_URL}/video/convert", data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"ส่งคำขอสำเร็จ: {result['task_id']}")
        return result['task_id']
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def resize_video(input_file: str, width: int, height: int) -> str:
    """ปรับขนาดวิดีโอ"""
    print(f"ส่งคำขอปรับขนาด: {width}x{height}")
    
    data = {
        'input_file': input_file,
        'width': width,
        'height': height,
        'output_format': 'mp4',
        'quality': 'high'
    }
    
    response = requests.post(f"{API_BASE_URL}/video/resize", data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"ส่งคำขอสำเร็จ: {result['task_id']}")
        return result['task_id']
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def get_task_status(task_id: str) -> dict:
    """ตรวจสอบสถานะ task"""
    response = requests.get(f"{API_BASE_URL}/video/status/{task_id}")
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"เกิดข้อผิดพลาดในการตรวจสอบสถานะ: {response.text}")
        return None

def wait_for_task_completion(task_id: str, timeout: int = 300) -> dict:
    """รอให้ task เสร็จสิ้น"""
    print(f"รอให้ task เสร็จสิ้น: {task_id}")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = get_task_status(task_id)
        if status:
            task_status = status.get('status')
            print(f"สถานะ: {task_status}")
        
            if task_status == 'completed':
                print(f"Task เสร็จสิ้น: {status.get('output_file')}")
                return status
            elif task_status == 'failed':
                print(f"Task ล้มเหลว: {status.get('error_message')}")
                return status
        
        time.sleep(5)  # รอ 5 วินาที
    
    print(f"หมดเวลาในการรอ task: {task_id}")
    return None

def get_queue_info():
    """ดึงข้อมูล queue"""
    response = requests.get(f"{API_BASE_URL}/queue/info")
    
    if response.status_code == 200:
        result = response.json()
        print("ข้อมูล Queue:")
        for queue_name, info in result['queues'].items():
            print(f"  {queue_name}: {info['message_count']} messages, {info['consumer_count']} consumers")
        return result
    else:
        print(f"เกิดข้อผิดพลาดในการดึงข้อมูล queue: {response.text}")
        return None

def main():
    """ตัวอย่างการใช้งาน"""
    print("=== ตัวอย่างการใช้งาน Video Processing กับ RabbitMQ ===\n")
    
    # ตรวจสอบสถานะ queue
    print("1. ตรวจสอบสถานะ Queue")
    get_queue_info()
    print()
    
    # สมมติว่ามีไฟล์วิดีโออยู่แล้ว
    video_file = "uploads/sample_video.mp4"
    
    # ตัวอย่าง 1: ตัดวิดีโอ
    print("2. ตัวอย่างการตัดวิดีโอ")
    trim_task_id = trim_video(video_file, 10.0, 30.0)
    if trim_task_id:
        result = wait_for_task_completion(trim_task_id)
        if result and result.get('status') == 'completed':
            trimmed_file = result.get('output_file')
            print(f"ไฟล์ที่ตัดแล้ว: {trimmed_file}")
    print()
    
    # ตัวอย่าง 2: แปลงรูปแบบ
    print("3. ตัวอย่างการแปลงรูปแบบ")
    convert_task_id = convert_format(video_file, "avi")
    if convert_task_id:
        result = wait_for_task_completion(convert_task_id)
        if result and result.get('status') == 'completed':
            converted_file = result.get('output_file')
            print(f"ไฟล์ที่แปลงแล้ว: {converted_file}")
    print()
    
    # ตัวอย่าง 3: ปรับขนาดวิดีโอ
    print("4. ตัวอย่างการปรับขนาดวิดีโอ")
    resize_task_id = resize_video(video_file, 1280, 720)
    if resize_task_id:
        result = wait_for_task_completion(resize_task_id)
        if result and result.get('status') == 'completed':
            resized_file = result.get('output_file')
            print(f"ไฟล์ที่ปรับขนาดแล้ว: {resized_file}")
    print()
    
    # ตัวอย่าง 4: รวมวิดีโอ (สมมติว่ามีไฟล์หลายไฟล์)
    print("5. ตัวอย่างการรวมวิดีโอ")
    video_files = ["uploads/video1.mp4", "uploads/video2.mp4"]
    merge_task_id = merge_videos(video_files)
    if merge_task_id:
        result = wait_for_task_completion(merge_task_id)
        if result and result.get('status') == 'completed':
            merged_file = result.get('output_file')
            print(f"ไฟล์ที่รวมแล้ว: {merged_file}")
    print()
    
    # ตรวจสอบสถานะ queue อีกครั้ง
    print("6. ตรวจสอบสถานะ Queue หลังการประมวลผล")
    get_queue_info()
    print()
    
    print("=== เสร็จสิ้นการทดสอบ ===")

if __name__ == "__main__":
    main() 