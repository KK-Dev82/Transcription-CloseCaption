#!/usr/bin/env python3
"""
สคริปต์ทดสอบฟีเจอร์วิดีโอทั้งหมด
- แบ่งตอนวิดีโอ (segmentation)
- ตัดวิดีโอ (trim)
- สร้าง Close Caption
"""

import requests
import json
import time
import os
from pathlib import Path

# ตั้งค่า
API_BASE_URL = "http://localhost:8001"
TEST_VIDEO_PATH = "test_video.mp4"  # ไฟล์วิดีโอทดสอบ

def upload_video(file_path):
    """อัปโหลดไฟล์วิดีโอ"""
    print(f"📤 อัปโหลดไฟล์: {file_path}")
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'video/mp4')}
        response = requests.post(f"{API_BASE_URL}/video/upload", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ อัปโหลดสำเร็จ: {result['file_path']}")
        return result['file_path']
    else:
        print(f"❌ อัปโหลดล้มเหลว: {response.text}")
        return None

def segment_video(file_path, segment_duration=600, overlap=5):
    """แบ่งตอนวิดีโอ"""
    print(f"✂️ แบ่งตอนวิดีโอ: {segment_duration} วินาที, overlap {overlap} วินาที")
    
    data = {
        "file_path": file_path,
        "segment_duration": segment_duration,
        "overlap": overlap
    }
    
    response = requests.post(f"{API_BASE_URL}/video/segment", json=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ แบ่งตอนสำเร็จ: {result['job_id']}")
        return result['job_id']
    else:
        print(f"❌ แบ่งตอนล้มเหลว: {response.text}")
        return None

def trim_video(file_path, start_time, end_time):
    """ตัดวิดีโอ"""
    print(f"✂️ ตัดวิดีโอ: {start_time} - {end_time}")
    
    data = {
        "file_path": file_path,
        "start_time": start_time,
        "end_time": end_time
    }
    
    response = requests.post(f"{API_BASE_URL}/video/trim", json=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ ตัดวิดีโอสำเร็จ: {result['job_id']}")
        return result['job_id']
    else:
        print(f"❌ ตัดวิดีโอล้มเหลว: {response.text}")
        return None

def transcribe_audio(file_path, model_size="base"):
    """แปลงเสียงเป็นข้อความ"""
    print(f"🎤 แปลงเสียงเป็นข้อความ: {model_size}")
    
    data = {
        "file_path": file_path,
        "model_size": model_size
    }
    
    response = requests.post(f"{API_BASE_URL}/transcription/transcribe", json=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ แปลงเสียงสำเร็จ: {result['job_id']}")
        return result['job_id']
    else:
        print(f"❌ แปลงเสียงล้มเหลว: {response.text}")
        return None

def create_close_caption(video_path, transcription_path):
    """สร้าง Close Caption"""
    print(f"📝 สร้าง Close Caption")
    
    data = {
        "video_path": video_path,
        "transcription_path": transcription_path
    }
    
    response = requests.post(f"{API_BASE_URL}/caption/create", json=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ สร้าง Close Caption สำเร็จ: {result['job_id']}")
        return result['job_id']
    else:
        print(f"❌ สร้าง Close Caption ล้มเหลว: {response.text}")
        return None

def check_job_status(job_id):
    """ตรวจสอบสถานะงาน"""
    print(f"🔍 ตรวจสอบสถานะงาน: {job_id}")
    
    response = requests.get(f"{API_BASE_URL}/queue/status/{job_id}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"📊 สถานะ: {result['status']}")
        if result['status'] == 'completed':
            print(f"📁 ผลลัพธ์: {result.get('result', 'N/A')}")
        return result
    else:
        print(f"❌ ตรวจสอบสถานะล้มเหลว: {response.text}")
        return None

def wait_for_job_completion(job_id, timeout=300):
    """รอให้งานเสร็จสิ้น"""
    print(f"⏳ รอให้งานเสร็จสิ้น: {job_id}")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        result = check_job_status(job_id)
        if result and result['status'] in ['completed', 'failed']:
            return result
        time.sleep(5)
    
    print(f"⏰ หมดเวลา: {timeout} วินาที")
    return None

def test_video_segmentation():
    """ทดสอบการแบ่งตอนวิดีโอ"""
    print("\n" + "="*50)
    print("🧪 ทดสอบการแบ่งตอนวิดีโอ")
    print("="*50)
    
    # อัปโหลดไฟล์
    file_path = upload_video(TEST_VIDEO_PATH)
    if not file_path:
        return
    
    # แบ่งตอนวิดีโอ (10 นาที, overlap 5 วินาที)
    job_id = segment_video(file_path, segment_duration=600, overlap=5)
    if not job_id:
        return
    
    # รอให้เสร็จสิ้น
    result = wait_for_job_completion(job_id)
    if result and result['status'] == 'completed':
        print(f"🎉 แบ่งตอนวิดีโอเสร็จสิ้น!")
        print(f"📁 ไฟล์ที่ได้: {result.get('result', 'N/A')}")

def test_video_trim():
    """ทดสอบการตัดวิดีโอ"""
    print("\n" + "="*50)
    print("🧪 ทดสอบการตัดวิดีโอ")
    print("="*50)
    
    # อัปโหลดไฟล์
    file_path = upload_video(TEST_VIDEO_PATH)
    if not file_path:
        return
    
    # ตัดวิดีโอ (0-30 วินาที)
    job_id = trim_video(file_path, start_time=0, end_time=30)
    if not job_id:
        return
    
    # รอให้เสร็จสิ้น
    result = wait_for_job_completion(job_id)
    if result and result['status'] == 'completed':
        print(f"🎉 ตัดวิดีโอเสร็จสิ้น!")
        print(f"📁 ไฟล์ที่ได้: {result.get('result', 'N/A')}")

def test_close_caption():
    """ทดสอบการสร้าง Close Caption"""
    print("\n" + "="*50)
    print("🧪 ทดสอบการสร้าง Close Caption")
    print("="*50)
    
    # อัปโหลดไฟล์
    file_path = upload_video(TEST_VIDEO_PATH)
    if not file_path:
        return
    
    # แปลงเสียงเป็นข้อความ
    transcribe_job = transcribe_audio(file_path, model_size="base")
    if not transcribe_job:
        return
    
    # รอให้แปลงเสียงเสร็จ
    transcribe_result = wait_for_job_completion(transcribe_job)
    if not transcribe_result or transcribe_result['status'] != 'completed':
        print("❌ แปลงเสียงล้มเหลว")
        return
    
    transcription_path = transcribe_result.get('result', '')
    
    # สร้าง Close Caption
    caption_job = create_close_caption(file_path, transcription_path)
    if not caption_job:
        return
    
    # รอให้สร้าง Close Caption เสร็จ
    caption_result = wait_for_job_completion(caption_job)
    if caption_result and caption_result['status'] == 'completed':
        print(f"🎉 สร้าง Close Caption เสร็จสิ้น!")
        print(f"📁 ไฟล์ที่ได้: {caption_result.get('result', 'N/A')}")

def main():
    """ฟังก์ชันหลัก"""
    print("🚀 เริ่มทดสอบฟีเจอร์วิดีโอ")
    
    # ตรวจสอบไฟล์ทดสอบ
    if not os.path.exists(TEST_VIDEO_PATH):
        print(f"❌ ไม่พบไฟล์ทดสอบ: {TEST_VIDEO_PATH}")
        print("กรุณาวางไฟล์วิดีโอทดสอบในโฟลเดอร์หลัก")
        return
    
    # ทดสอบฟีเจอร์ต่างๆ
    test_video_trim()
    test_video_segmentation()
    test_close_caption()
    
    print("\n🎉 ทดสอบเสร็จสิ้น!")

if __name__ == "__main__":
    main() 