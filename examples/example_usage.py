#!/usr/bin/env python3
"""
ตัวอย่างการใช้งาน Transcription & Close Caption Service API
"""

import requests
import json
import time
import websockets
import asyncio
from pathlib import Path

# ตั้งค่า
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

def upload_file(file_path: str):
    """อัปโหลดไฟล์"""
    print(f"กำลังอัปโหลดไฟล์: {file_path}")
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{BASE_URL}/upload/", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"อัปโหลดสำเร็จ: {result['file_path']}")
        return result
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def start_transcription(file_path: str):
    """เริ่มการแปลงเสียงเป็นข้อความ"""
    print(f"เริ่มการแปลงเสียง: {file_path}")
    
    data = {
        "file_path": file_path,
        "language": "th",
        "model_size": "base",
        "chunk_duration": 30
    }
    
    response = requests.post(f"{BASE_URL}/transcribe/", json=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"เริ่มการแปลงเสียงสำเร็จ: {result['task_id']}")
        return result
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def start_caption(file_path: str):
    """เริ่มการสร้าง close caption"""
    print(f"เริ่มการสร้าง caption: {file_path}")
    
    data = {
        "file_path": file_path,
        "language": "th",
        "model_size": "tiny",
        "subtitle_format": "srt"
    }
    
    response = requests.post(f"{BASE_URL}/caption/", json=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"เริ่มการสร้าง caption สำเร็จ: {result['task_id']}")
        return result
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def check_status(endpoint: str, task_id: str):
    """ตรวจสอบสถานะ"""
    response = requests.get(f"{BASE_URL}/{endpoint}/{task_id}")
    
    if response.status_code == 200:
        result = response.json()
        return result['status']
    else:
        return None

def wait_for_completion(endpoint: str, task_id: str, timeout: int = 300):
    """รอให้เสร็จสิ้น"""
    print(f"รอให้ {endpoint} เสร็จสิ้น...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = check_status(endpoint, task_id)
        
        if status == "completed":
            print(f"{endpoint} เสร็จสิ้นแล้ว!")
            return True
        elif status == "failed":
            print(f"{endpoint} ล้มเหลว!")
            return False
        
        print(f"สถานะ: {status}")
        time.sleep(5)
    
    print("หมดเวลา!")
    return False

def search_transcription(task_id: str, query: str):
    """ค้นหาข้อความใน transcription"""
    print(f"ค้นหา: {query}")
    
    params = {"query": query, "case_sensitive": False}
    response = requests.get(f"{BASE_URL}/transcribe/{task_id}/search", params=params)
    
    if response.status_code == 200:
        result = response.json()
        print(f"พบ {result['total_results']} ผลลัพธ์")
        
        for i, match in enumerate(result['results'], 1):
            print(f"\nผลลัพธ์ {i}:")
            print(f"  เวลา: {match['start_time']:.1f}s - {match['end_time']:.1f}s")
            print(f"  ข้อความ: {match['highlighted_text']}")
        
        return result
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def get_transcription_text(task_id: str):
    """ดึงข้อความที่แปลงแล้ว"""
    response = requests.get(f"{BASE_URL}/transcribe/{task_id}/text")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nข้อความที่แปลงแล้ว:")
        print(f"ความยาว: {result['total_duration']:.1f} วินาที")
        print(f"ภาษา: {result['language']}")
        print(f"ข้อความ: {result['full_text'][:200]}...")
        return result
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

def get_caption_subtitle(task_id: str):
    """ดึงไฟล์ subtitle"""
    response = requests.get(f"{BASE_URL}/caption/{task_id}/subtitle")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nไฟล์ subtitle:")
        print(f"รูปแบบ: {result['subtitle_format']}")
        print(f"จำนวน segments: {result['total_segments']}")
        
        # บันทึกไฟล์
        output_file = f"output_{task_id}.{result['subtitle_format']}"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result['subtitle_content'])
        
        print(f"บันทึกไฟล์: {output_file}")
        return result
    else:
        print(f"เกิดข้อผิดพลาด: {response.text}")
        return None

async def monitor_progress(ws_url: str, task_id: str):
    """ติดตามความคืบหน้าผ่าน WebSocket"""
    print(f"ติดตามความคืบหน้าผ่าน WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            async for message in websocket:
                data = json.loads(message)
                print(f"สถานะ: {data['status']}, ความคืบหน้า: {data['progress']}%")
                
                if data['status'] in ['completed', 'failed', 'cancelled']:
                    break
    except Exception as e:
        print(f"เกิดข้อผิดพลาดใน WebSocket: {e}")

def main():
    """ตัวอย่างการใช้งานหลัก"""
    print("=== ตัวอย่างการใช้งาน Transcription & Close Caption Service ===\n")
    
    # ตรวจสอบสถานะระบบ
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code != 200:
        print("ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้")
        return
    
    print("✅ เชื่อมต่อกับเซิร์ฟเวอร์สำเร็จ\n")
    
    # ตัวอย่างไฟล์ (ต้องมีไฟล์จริง)
    test_file = "test_video.mp4"  # เปลี่ยนเป็นไฟล์ที่มีอยู่จริง
    
    if not Path(test_file).exists():
        print(f"ไม่พบไฟล์: {test_file}")
        print("กรุณาเปลี่ยนเป็นไฟล์ที่มีอยู่จริง")
        return
    
    # 1. อัปโหลดไฟล์
    upload_result = upload_file(test_file)
    if not upload_result:
        return
    
    file_path = upload_result['file_path']
    print(f"ไฟล์ที่อัปโหลด: {file_path}\n")
    
    # 2. เริ่มการแปลงเสียง
    transcription_result = start_transcription(file_path)
    if not transcription_result:
        return
    
    transcription_task_id = transcription_result['task_id']
    
    # 3. เริ่มการสร้าง caption
    caption_result = start_caption(file_path)
    if not caption_result:
        return
    
    caption_task_id = caption_result['task_id']
    
    # 4. รอให้เสร็จสิ้น
    print("\n=== รอให้เสร็จสิ้น ===")
    
    # รอ transcription
    if wait_for_completion("transcribe", transcription_task_id):
        # ดึงผลลัพธ์ transcription
        get_transcription_text(transcription_task_id)
        
        # ค้นหาข้อความ
        search_transcription(transcription_task_id, "ประชุม")
    
    # รอ caption
    if wait_for_completion("caption", caption_task_id):
        # ดึงผลลัพธ์ caption
        get_caption_subtitle(caption_task_id)
    
    print("\n=== เสร็จสิ้น ===")

if __name__ == "__main__":
    main() 