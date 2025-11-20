#!/usr/bin/env python3
"""
สคริปต์ทดสอบการทำ Transcription สำหรับไฟล์ trimmed_short.mp4
"""

import asyncio
import aiohttp
import json
import time
from pathlib import Path

# ตั้งค่า API URL
API_BASE_URL = "http://localhost:8001"

async def test_transcription():
    """ทดสอบการทำ transcription"""
    
    print("🎬 เริ่มทดสอบการทำ Transcription")
    print("=" * 50)
    
    # ตรวจสอบไฟล์
    video_file = "trimmed_short.mp4"
    if not Path(video_file).exists():
        print(f"❌ ไม่พบไฟล์ {video_file}")
        return
    
    print(f"✅ พบไฟล์: {video_file}")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. เริ่มการทำ transcription
            print("\n📝 เริ่มการทำ transcription...")
            
            transcription_request = {
                "file_path": video_file,
                "language": "th",  # ภาษาไทย
                "model_size": "base",  # ขนาดโมเดล
                "chunk_duration": 30  # ความยาว chunk (วินาที)
            }
            
            async with session.post(
                f"{API_BASE_URL}/transcribe/",
                json=transcription_request
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    task_id = result["task_id"]
                    print(f"✅ เริ่ม transcription สำเร็จ")
                    print(f"   Task ID: {task_id}")
                    print(f"   สถานะ: {result['status']}")
                else:
                    error_text = await response.text()
                    print(f"❌ เกิดข้อผิดพลาด: {response.status}")
                    print(f"   {error_text}")
                    return
            
            # 2. ตรวจสอบสถานะ
            print("\n⏳ ตรวจสอบสถานะการประมวลผล...")
            
            max_attempts = 60  # สูงสุด 60 ครั้ง (5 นาที)
            attempt = 0
            
            while attempt < max_attempts:
                async with session.get(f"{API_BASE_URL}/transcribe/{task_id}") as response:
                    if response.status == 200:
                        status_result = await response.json()
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
                        print(f"❌ ไม่สามารถตรวจสอบสถานะได้: {response.status}")
                        return
                
                attempt += 1
                await asyncio.sleep(5)  # รอ 5 วินาที
            
            if attempt >= max_attempts:
                print("⏰ หมดเวลารอการประมวลผล")
                return
            
            # 3. ดึงข้อความที่แปลงแล้ว
            print("\n📄 ดึงข้อความที่แปลงแล้ว...")
            
            async with session.get(f"{API_BASE_URL}/transcribe/{task_id}/text") as response:
                if response.status == 200:
                    text_result = await response.json()
                    print("✅ ได้ข้อความที่แปลงแล้ว:")
                    print("-" * 30)
                    print(text_result["full_text"])
                    print("-" * 30)
                    print(f"   ภาษา: {text_result['language']}")
                    print(f"   ความยาวทั้งหมด: {text_result['total_duration']} วินาที")
                else:
                    error_text = await response.text()
                    print(f"❌ ไม่สามารถดึงข้อความได้: {response.status}")
                    print(f"   {error_text}")
            
            # 4. ดึง chunks
            print("\n📊 ดึงข้อมูล chunks...")
            
            async with session.get(f"{API_BASE_URL}/transcribe/{task_id}/chunks") as response:
                if response.status == 200:
                    chunks_result = await response.json()
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
                    error_text = await response.text()
                    print(f"❌ ไม่สามารถดึง chunks ได้: {response.status}")
                    print(f"   {error_text}")
            
            # 5. ดึงสถิติ
            print("\n📈 ดึงสถิติ...")
            
            async with session.get(f"{API_BASE_URL}/transcribe/{task_id}/stats") as response:
                if response.status == 200:
                    stats_result = await response.json()
                    print("✅ สถิติการทำ transcription:")
                    for key, value in stats_result.items():
                        print(f"   {key}: {value}")
                else:
                    error_text = await response.text()
                    print(f"❌ ไม่สามารถดึงสถิติได้: {response.status}")
                    print(f"   {error_text}")
            
            # 6. ทดสอบการค้นหา
            print("\n🔍 ทดสอบการค้นหา...")
            
            # ค้นหาคำที่อาจมีในข้อความ
            search_queries = ["ครับ", "ค่ะ", "สวัสดี", "ขอบคุณ"]
            
            for query in search_queries:
                async with session.get(
                    f"{API_BASE_URL}/transcribe/{task_id}/search",
                    params={"query": query, "case_sensitive": False}
                ) as response:
                    if response.status == 200:
                        search_result = await response.json()
                        results = search_result["results"]
                        print(f"   ค้นหา '{query}': พบ {len(results)} รายการ")
                        
                        for result in results[:2]:  # แสดง 2 รายการแรก
                            print(f"     - {result['text']} (เวลา: {result['start_time']:.2f}s)")
                    else:
                        print(f"   ค้นหา '{query}': ไม่สามารถค้นหาได้")
            
            # 7. แสดงรายการ transcription ทั้งหมด
            print("\n📋 รายการ transcription ทั้งหมด...")
            
            async with session.get(f"{API_BASE_URL}/transcribe/") as response:
                if response.status == 200:
                    all_transcriptions = await response.json()
                    print(f"✅ มี transcription ทั้งหมด {len(all_transcriptions)} รายการ")
                    
                    for i, transcription in enumerate(all_transcriptions[:3]):
                        print(f"   {i+1}. {transcription['task_id'][:8]}... - {transcription['status']}")
                else:
                    print(f"❌ ไม่สามารถดึงรายการได้: {response.status}")
            
            print("\n🎉 การทดสอบเสร็จสิ้น!")
            
        except aiohttp.ClientError as e:
            print(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {e}")

async def test_whisper_service_directly():
    """ทดสอบ WhisperService โดยตรง"""
    
    print("\n🔧 ทดสอบ WhisperService โดยตรง")
    print("=" * 50)
    
    try:
        from app.services.whisper_service import WhisperService
        from app.services.file_service import FileService
        
        whisper_service = WhisperService()
        file_service = FileService()
        
        video_file = "trimmed_short.mp4"
        
        # ตรวจสอบไฟล์
        if not Path(video_file).exists():
            print(f"❌ ไม่พบไฟล์ {video_file}")
            return
        
        print(f"✅ พบไฟล์: {video_file}")
        
        # แยกเสียงจากวิดีโอ
        print("🎵 แยกเสียงจากวิดีโอ...")
        audio_path = file_service.extract_audio(video_file)
        print(f"✅ ได้ไฟล์เสียง: {audio_path}")
        
        # สร้าง chunks
        print("📦 สร้าง chunks...")
        chunks = file_service.create_chunks(audio_path, 30)
        print(f"✅ สร้าง chunks ได้ {len(chunks)} ชิ้น")
        
        # ทำ transcription
        print("🎤 ทำ transcription...")
        chunk_results = whisper_service.transcribe_chunks(chunks, "base", "th")
        print(f"✅ ทำ transcription chunks ได้ {len(chunk_results)} ชิ้น")
        
        # รวมผลลัพธ์
        print("🔗 รวมผลลัพธ์...")
        merged_result = whisper_service.merge_transcriptions(chunk_results, 30)
        
        print("✅ ผลลัพธ์การทำ transcription:")
        print("-" * 30)
        print(merged_result.get("text", ""))
        print("-" * 30)
        
        # ลบไฟล์ชั่วคราว
        print("🧹 ลบไฟล์ชั่วคราว...")
        temp_files = [audio_path] + chunks
        file_service.cleanup_temp_files(temp_files)
        print("✅ ลบไฟล์ชั่วคราวเสร็จสิ้น")
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")

if __name__ == "__main__":
    print("🚀 เริ่มทดสอบระบบ Transcription")
    print("เลือกการทดสอบ:")
    print("1. ทดสอบผ่าน API")
    print("2. ทดสอบ WhisperService โดยตรง")
    print("3. ทดสอบทั้งสองแบบ")
    
    choice = input("กรุณาเลือก (1/2/3): ").strip()
    
    if choice == "1":
        asyncio.run(test_transcription())
    elif choice == "2":
        asyncio.run(test_whisper_service_directly())
    elif choice == "3":
        asyncio.run(test_transcription())
        asyncio.run(test_whisper_service_directly())
    else:
        print("❌ ตัวเลือกไม่ถูกต้อง") 