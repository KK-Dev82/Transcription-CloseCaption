#!/usr/bin/env python3
"""
สคริปต์ทดสอบการทำ Transcription สำหรับไฟล์ trimmed_short.mp4 ผ่าน Docker
"""

import subprocess
import json
import time
import requests
from pathlib import Path

# ตั้งค่า API URL
API_BASE_URL = "http://localhost:8001"

def run_docker_command(command):
    """รันคำสั่ง Docker"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def test_transcription_api():
    """ทดสอบการทำ transcription ผ่าน API"""
    
    print("🎬 เริ่มทดสอบการทำ Transcription ผ่าน API")
    print("=" * 50)
    
    # ตรวจสอบไฟล์
    video_file = "trimmed_short.mp4"
    if not Path(video_file).exists():
        print(f"❌ ไม่พบไฟล์ {video_file}")
        return
    
    print(f"✅ พบไฟล์: {video_file}")
    
    try:
        # 1. ตรวจสอบ API health
        print("\n🏥 ตรวจสอบ API health...")
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print("✅ API ทำงานปกติ")
            print(f"   สถานะ: {health_data.get('status')}")
        else:
            print(f"❌ API ไม่ตอบสนอง: {response.status_code}")
            return
        
        # 2. เริ่มการทำ transcription
        print("\n📝 เริ่มการทำ transcription...")
        
        transcription_request = {
            "file_path": video_file,
            "language": "th",  # ภาษาไทย
            "model_size": "base",  # ขนาดโมเดล
            "chunk_duration": 30  # ความยาว chunk (วินาที)
        }
        
        response = requests.post(
            f"{API_BASE_URL}/transcribe/",
            json=transcription_request,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result["task_id"]
            print(f"✅ เริ่ม transcription สำเร็จ")
            print(f"   Task ID: {task_id}")
            print(f"   สถานะ: {result['status']}")
        else:
            print(f"❌ เกิดข้อผิดพลาด: {response.status_code}")
            print(f"   {response.text}")
            return
        
        # 3. ตรวจสอบสถานะ
        print("\n⏳ ตรวจสอบสถานะการประมวลผล...")
        
        max_attempts = 60  # สูงสุด 60 ครั้ง (5 นาที)
        attempt = 0
        
        while attempt < max_attempts:
            response = requests.get(f"{API_BASE_URL}/transcribe/{task_id}", timeout=10)
            if response.status_code == 200:
                status_result = response.json()
                current_status = status_result["status"]
                
                print(f"   พยายามที่ {attempt + 1}: สถานะ = {current_status}")
                
                if current_status == "completed":
                    print("✅ การทำ transcription เสร็จสิ้น!")
                    break
                elif current_status == "failed":
                    print(f"❌ การทำ transcription ล้มเหลว: {status_result.get('error_message', 'ไม่ทราบสาเหตุ')}")
                    return
                elif current_status == "cancelled":
                    print("❌ การทำ transcription ถูกยกเลิก")
                    return
            
            else:
                print(f"❌ ไม่สามารถตรวจสอบสถานะได้: {response.status_code}")
                return
            
            attempt += 1
            time.sleep(5)  # รอ 5 วินาที
        
        if attempt >= max_attempts:
            print("⏰ หมดเวลารอการประมวลผล")
            return
        
        # 4. ดึงข้อความที่แปลงแล้ว
        print("\n📄 ดึงข้อความที่แปลงแล้ว...")
        
        response = requests.get(f"{API_BASE_URL}/transcribe/{task_id}/text", timeout=10)
        if response.status_code == 200:
            text_result = response.json()
            print("✅ ได้ข้อความที่แปลงแล้ว:")
            print("-" * 30)
            print(text_result["full_text"])
            print("-" * 30)
            print(f"   ภาษา: {text_result['language']}")
            print(f"   ความยาวทั้งหมด: {text_result['total_duration']} วินาที")
        else:
            print(f"❌ ไม่สามารถดึงข้อความได้: {response.status_code}")
            print(f"   {response.text}")
        
        # 5. ดึง chunks
        print("\n📊 ดึงข้อมูล chunks...")
        
        response = requests.get(f"{API_BASE_URL}/transcribe/{task_id}/chunks", timeout=10)
        if response.status_code == 200:
            chunks_result = response.json()
            chunks = chunks_result["chunks"]
            print(f"✅ ได้ chunks ทั้งหมด {len(chunks)} ชิ้น")
            
            # แสดง chunks แรก 3 ชิ้น
            for i, chunk in enumerate(chunks[:3]):
                print(f"   Chunk {i+1}:")
                print(f"     เวลา: {chunk['start_time']:.2f}s - {chunk['end_time']:.2f}s")
                print(f"     ข้อความ: {chunk['text']}")
                if chunk.get('confidence'):
                    print(f"     ความเชื่อมั่น: {chunk['confidence']:.3f}")
                print()
            
            if len(chunks) > 3:
                print(f"   ... และอีก {len(chunks) - 3} chunks")
        else:
            print(f"❌ ไม่สามารถดึง chunks ได้: {response.status_code}")
            print(f"   {response.text}")
        
        # 6. ทดสอบการค้นหา
        print("\n🔍 ทดสอบการค้นหา...")
        
        # ค้นหาคำที่อาจมีในข้อความ
        search_queries = ["ครับ", "ค่ะ", "สวัสดี", "ขอบคุณ"]
        
        for query in search_queries:
            response = requests.get(
                f"{API_BASE_URL}/transcribe/{task_id}/search",
                params={"query": query, "case_sensitive": False},
                timeout=10
            )
            if response.status_code == 200:
                search_result = response.json()
                results = search_result["results"]
                print(f"   ค้นหา '{query}': พบ {len(results)} รายการ")
                
                for result in results[:2]:  # แสดง 2 รายการแรก
                    print(f"     - {result['text']} (เวลา: {result['start_time']:.2f}s)")
            else:
                print(f"   ค้นหา '{query}': ไม่สามารถค้นหาได้")
        
        print("\n🎉 การทดสอบเสร็จสิ้น!")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")

def test_docker_whisper_directly():
    """ทดสอบ Whisper โดยตรงผ่าน Docker"""
    
    print("\n🔧 ทดสอบ Whisper โดยตรงผ่าน Docker")
    print("=" * 50)
    
    video_file = "trimmed_short.mp4"
    
    # ตรวจสอบไฟล์
    if not Path(video_file).exists():
        print(f"❌ ไม่พบไฟล์ {video_file}")
        return
    
    print(f"✅ พบไฟล์: {video_file}")
    
    try:
        # 1. แยกเสียงจากวิดีโอ
        print("🎵 แยกเสียงจากวิดีโอ...")
        success, stdout, stderr = run_docker_command(
            f"docker run --rm -v $(pwd):/workspace -w /workspace "
            f"jrottenberg/ffmpeg:latest -i {video_file} -vn -acodec pcm_s16le -ar 16000 -ac 1 temp_audio.wav"
        )
        
        if success:
            print("✅ แยกเสียงสำเร็จ: temp_audio.wav")
        else:
            print(f"❌ แยกเสียงล้มเหลว: {stderr}")
            return
        
        # 2. ทำ transcription ด้วย Whisper
        print("🎤 ทำ transcription ด้วย Whisper...")
        success, stdout, stderr = run_docker_command(
            f"docker run --rm -v $(pwd):/workspace -w /workspace "
            f"ghcr.io/ggerganov/whisper.cpp:main "
            f"./main -m models/ggml-base.bin -f temp_audio.wav -l th -otxt"
        )
        
        if success:
            print("✅ ทำ transcription สำเร็จ")
            
            # อ่านผลลัพธ์
            txt_file = "temp_audio.wav.txt"
            if Path(txt_file).exists():
                with open(txt_file, 'r', encoding='utf-8') as f:
                    transcription_text = f.read().strip()
                
                print("✅ ผลลัพธ์การทำ transcription:")
                print("-" * 30)
                print(transcription_text)
                print("-" * 30)
                
                # ลบไฟล์ชั่วคราว
                print("🧹 ลบไฟล์ชั่วคราว...")
                run_docker_command("rm -f temp_audio.wav temp_audio.wav.txt")
                print("✅ ลบไฟล์ชั่วคราวเสร็จสิ้น")
            else:
                print("❌ ไม่พบไฟล์ผลลัพธ์")
        else:
            print(f"❌ ทำ transcription ล้มเหลว: {stderr}")
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")

def test_docker_compose_services():
    """ทดสอบ services ใน Docker Compose"""
    
    print("\n🐳 ตรวจสอบ Docker Compose Services")
    print("=" * 50)
    
    try:
        # ตรวจสอบ containers ที่ทำงานอยู่
        print("📋 ตรวจสอบ containers ที่ทำงานอยู่...")
        success, stdout, stderr = run_docker_command("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
        
        if success:
            print("✅ Containers ที่ทำงานอยู่:")
            print(stdout)
        else:
            print(f"❌ ไม่สามารถตรวจสอบ containers ได้: {stderr}")
        
        # ตรวจสอบ logs ของ API
        print("\n📝 ตรวจสอบ logs ของ API...")
        success, stdout, stderr = run_docker_command("docker logs transcription-api --tail 20")
        
        if success:
            print("✅ API Logs:")
            print(stdout)
        else:
            print(f"❌ ไม่สามารถดึง logs ได้: {stderr}")
        
        # ตรวจสอบ logs ของ Video Worker
        print("\n🔧 ตรวจสอบ logs ของ Video Worker...")
        success, stdout, stderr = run_docker_command("docker logs video-worker-1 --tail 10")
        
        if success:
            print("✅ Video Worker Logs:")
            print(stdout)
        else:
            print(f"❌ ไม่สามารถดึง logs ได้: {stderr}")
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")

if __name__ == "__main__":
    print("🚀 เริ่มทดสอบระบบ Transcription ผ่าน Docker")
    print("เลือกการทดสอบ:")
    print("1. ทดสอบผ่าน API")
    print("2. ทดสอบ Whisper โดยตรงผ่าน Docker")
    print("3. ตรวจสอบ Docker Compose Services")
    print("4. ทดสอบทั้งหมด")
    
    choice = input("กรุณาเลือก (1/2/3/4): ").strip()
    
    if choice == "1":
        test_transcription_api()
    elif choice == "2":
        test_docker_whisper_directly()
    elif choice == "3":
        test_docker_compose_services()
    elif choice == "4":
        test_docker_compose_services()
        test_transcription_api()
        test_docker_whisper_directly()
    else:
        print("❌ ตัวเลือกไม่ถูกต้อง") 