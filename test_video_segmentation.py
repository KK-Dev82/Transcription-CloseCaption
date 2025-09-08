#!/usr/bin/env python3
"""
สคริปต์ทดสอบฟีเจอร์วิดีโอทั้งหมด
- แบ่งตอนวิดีโอ (segmentation) + transcription
- ตัดวิดีโอ (trim)
- สร้าง Close Caption
"""

import requests
import json
import time
import os
from datetime import datetime

API_BASE_URL = "http://localhost:8001"

class VideoFeatureTester:
    def __init__(self):
        self.session = requests.Session()
    
    def upload_video(self, video_path):
        """อัปโหลดไฟล์วิดีโอ"""
        print(f"📤 อัปโหลดไฟล์: {video_path}")
        
        with open(video_path, 'rb') as f:
            files = {'file': (os.path.basename(video_path), f, 'video/mp4')}
            response = self.session.post(f"{API_BASE_URL}/video/upload", files=files)
        
        if response.status_code == 200:
            result = response.json()
            file_path = result.get('file_path')
            print(f"✅ อัปโหลดสำเร็จ: {file_path}")
            return file_path
        else:
            print(f"❌ อัปโหลดล้มเหลว: {response.status_code}")
            print(f"Error: {response.text}")
            return None
    
    def start_segmentation(self, file_path, segment_duration=600, overlap=5):
        """เริ่มการแบ่งตอนวิดีโอ"""
        print(f"🚀 เริ่ม Video Segmentation")
        print(f"📹 ไฟล์: {file_path}")
        print(f"⏱️  ตอนละ: {segment_duration} วินาที ({segment_duration/60:.1f} นาที)")
        print(f"🔄 Overlap: {overlap} วินาที")
        
        segmentation_data = {
            "file_path": file_path,
            "segment_duration": segment_duration,
            "overlap": overlap,
            "language": "th",
            "model_size": "base"
        }
        
        response = self.session.post(f"{API_BASE_URL}/video/segment", json=segmentation_data)
        if response.status_code == 200:
            result = response.json()
            job_id = result.get('job_id')
            print(f"✅ ส่งงาน segmentation: {job_id}")
            return job_id
        else:
            print(f"❌ ส่งงาน segmentation ล้มเหลว: {response.status_code}")
            print(f"Error: {response.text}")
            return None
    
    def start_trim(self, file_path, start_time, end_time):
        """เริ่มการตัดวิดีโอ"""
        print(f"✂️ เริ่ม Video Trim")
        print(f"📹 ไฟล์: {file_path}")
        print(f"⏱️  ตัดช่วง: {start_time}s - {end_time}s")
        
        data = {
            "input_file": file_path,
            "start_time": start_time,
            "end_time": end_time
        }
        
        response = self.session.post(f"{API_BASE_URL}/video/trim", data=data)
        if response.status_code == 200:
            result = response.json()
            job_id = result.get('task_id')
            print(f"✅ ส่งงาน trim: {job_id}")
            return job_id
        else:
            print(f"❌ ส่งงาน trim ล้มเหลว: {response.status_code}")
            print(f"Error: {response.text}")
            return None
    
    def start_transcription(self, file_path, model_size="base"):
        """เริ่มการแปลงเสียงเป็นข้อความ"""
        print(f"🎤 เริ่ม Transcription")
        print(f"📹 ไฟล์: {file_path}")
        print(f"🤖 โมเดล: {model_size}")
        
        data = {
            "file_path": file_path,
            "model_size": model_size,
            "language": "th",
            "chunk_duration": 30
        }
        
        response = self.session.post(f"{API_BASE_URL}/transcribe/", json=data)
        if response.status_code == 200:
            result = response.json()
            job_id = result.get('task_id')
            print(f"✅ ส่งงาน transcription: {job_id}")
            return job_id
        else:
            print(f"❌ ส่งงาน transcription ล้มเหลว: {response.status_code}")
            print(f"Error: {response.text}")
            return None
    
    def start_close_caption(self, video_path, transcription_path):
        """เริ่มการสร้าง Close Caption"""
        print(f"📝 เริ่มสร้าง Close Caption")
        print(f"📹 วิดีโอ: {video_path}")
        print(f"📄 Transcription: {transcription_path}")
        
        data = {
            "file_path": video_path,
            "language": "th",
            "model_size": "base",
            "subtitle_format": "srt"
        }
        
        response = self.session.post(f"{API_BASE_URL}/caption/", json=data)
        if response.status_code == 200:
            result = response.json()
            job_id = result.get('task_id')
            print(f"✅ ส่งงาน close caption: {job_id}")
            return job_id
        else:
            print(f"❌ ส่งงาน close caption ล้มเหลว: {response.status_code}")
            print(f"Error: {response.text}")
            return None
    
    def check_job_status(self, job_id, job_type="video"):
        """ตรวจสอบสถานะงาน"""
        if job_type == "transcription":
            response = self.session.get(f"{API_BASE_URL}/transcribe/{job_id}")
        elif job_type == "caption":
            response = self.session.get(f"{API_BASE_URL}/caption/{job_id}")
        else:
            response = self.session.get(f"{API_BASE_URL}/video/status/{job_id}")
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ ตรวจสอบสถานะล้มเหลว: {response.status_code}")
            return None
    
    def wait_for_job_completion(self, job_id, job_type="video", timeout=300):
        """รอให้งานเสร็จสิ้น"""
        print(f"⏳ รอ {job_type} {job_id}...")
        
        for i in range(timeout // 5):  # ตรวจสอบทุก 5 วินาที
            time.sleep(5)
            
            status_data = self.check_job_status(job_id, job_type)
            if status_data:
                status = status_data.get('status')
                progress = status_data.get('progress', 0)
                
                # แสดง progress แบบละเอียด
                if job_type == "video":
                    current_segment = status_data.get('current_segment', 0)
                    total_segments = status_data.get('total_segments', 0)
                    if total_segments > 0:
                        print(f"📊 Status: {status} - Progress: {progress}% - Segment: {current_segment}/{total_segments}")
                    else:
                        print(f"📊 Status: {status} - Progress: {progress}%")
                else:
                    print(f"📊 Status: {status} - Progress: {progress}%")
                
                if status == 'completed':
                    print(f"✅ {job_type} เสร็จสิ้น")
                    return status_data
                elif status == 'failed':
                    print(f"❌ {job_type} ล้มเหลว")
                    return None
            
            if i % 12 == 0:  # แสดงสถานะทุก 1 นาที
                print(f"⏰ รอมาแล้ว {(i+1)*5} วินาที...")
        
        print(f"⏰ {job_type} หมดเวลา")
        return None
    
    def test_video_trim(self, file_path):
        """ทดสอบการตัดวิดีโอ"""
        print("\n" + "="*50)
        print("🧪 ทดสอบการตัดวิดีโอ")
        print("="*50)
        
        # ตัดวิดีโอ (0-30 วินาที)
        job_id = self.start_trim(file_path, start_time=0, end_time=30)
        if not job_id:
            return None
        
        # รอให้เสร็จสิ้น
        result = self.wait_for_job_completion(job_id, "video")
        if result and result['status'] == 'completed':
            print(f"🎉 ตัดวิดีโอเสร็จสิ้น!")
            print(f"📁 ไฟล์ที่ได้: {result.get('result', 'N/A')}")
            return result.get('result')
        return None
    
    def test_video_segmentation(self, file_path):
        """ทดสอบการแบ่งตอนวิดีโอ"""
        print("\n" + "="*50)
        print("🧪 ทดสอบการแบ่งตอนวิดีโอ")
        print("="*50)
        print("📹 แบ่งวิดีโอเป็นตอนละ 600 วินาที (10 นาที)")
        print("🔄 Overlap: 5 วินาที")
        print("🎤 ทำ transcription ทันทีหลังตัดแต่ละตอน")
        print("="*50)
        
        # แบ่งตอนวิดีโอ (10 นาที, overlap 5 วินาที)
        job_id = self.start_segmentation(file_path, segment_duration=600, overlap=5)
        if not job_id:
            return None
        
        # รอให้เสร็จสิ้น
        result = self.wait_for_job_completion(job_id, "video", timeout=1200)  # รอ 20 นาที
        if result and result['status'] == 'completed':
            print(f"🎉 แบ่งตอนวิดีโอเสร็จสิ้น!")
            print(f"📁 ไฟล์ที่ได้: {result.get('result', 'N/A')}")
            
            # แสดงสรุปผลลัพธ์
            segments = result.get('segments', [])
            if segments:
                print(f"\n📊 สรุปผลลัพธ์:")
                print(f"  จำนวน segments: {len(segments)}")
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
                    
                    print(f"  Segment {i+1}: {start_time:.1f}s-{end_time:.1f}s ({duration:.1f}s) - {len(text)} ตัวอักษร")
                
                print(f"\n⏱️  ความยาวรวม: {total_duration:.1f} วินาที ({total_duration/60:.1f} นาที)")
                print(f"📝 ข้อความรวม: {len(total_text)} ตัวอักษร")
                
                # บันทึกข้อความรวม
                with open("full_transcription.txt", 'w', encoding='utf-8') as f:
                    f.write(total_text)
                
                print("📄 บันทึกข้อความรวม: full_transcription.txt")
            
            return result.get('result')
        return None
    
    def test_close_caption(self, file_path):
        """ทดสอบการสร้าง Close Caption"""
        print("\n" + "="*50)
        print("🧪 ทดสอบการสร้าง Close Caption")
        print("="*50)
        
        # แปลงเสียงเป็นข้อความ
        transcribe_job = self.start_transcription(file_path, model_size="base")
        if not transcribe_job:
            return None
        
        # รอให้แปลงเสียงเสร็จ
        transcribe_result = self.wait_for_job_completion(transcribe_job, "transcription")
        if not transcribe_result or transcribe_result['status'] != 'completed':
            print("❌ แปลงเสียงล้มเหลว")
            return None
        
        transcription_path = transcribe_result.get('result', '')
        
        # สร้าง Close Caption
        caption_job = self.start_close_caption(file_path, transcription_path)
        if not caption_job:
            return None
        
        # รอให้สร้าง Close Caption เสร็จ
        caption_result = self.wait_for_job_completion(caption_job, "caption")
        if caption_result and caption_result['status'] == 'completed':
            print(f"🎉 สร้าง Close Caption เสร็จสิ้น!")
            print(f"📁 ไฟล์ที่ได้: {caption_result.get('result', 'N/A')}")
            return caption_result.get('result')
        return None
    
    def save_results(self, results, output_file="test_results.json"):
        """บันทึกผลลัพธ์"""
        print(f"\n💾 บันทึกผลลัพธ์: {output_file}")
        
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'test_results': results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ บันทึกผลลัพธ์สำเร็จ: {output_file}")

def main():
    """ฟังก์ชันหลัก"""
    print("🎬 เริ่มทดสอบฟีเจอร์วิดีโอทั้งหมด")
    print("=" * 60)
    
    tester = VideoFeatureTester()
    
    # 1. อัปโหลดวิดีโอ
    video_path = "test_video.mp4"
    if not os.path.exists(video_path):
        print(f"❌ ไม่พบไฟล์: {video_path}")
        print("กรุณาวางไฟล์วิดีโอทดสอบในโฟลเดอร์หลัก")
        return
    
    file_path = tester.upload_video(video_path)
    if not file_path:
        return
    
    # 2. ทดสอบฟีเจอร์ต่างๆ
    results = {}
    
    # ทดสอบการแบ่งตอนวิดีโอ (เน้นเป็นหลัก)
    print("\n🎯 เน้นการทดสอบ: การแบ่งตอนวิดีโอ + Transcription")
    segmentation_result = tester.test_video_segmentation(file_path)
    results['segmentation'] = segmentation_result
    
    # ทดสอบการตัดวิดีโอ (ทดสอบเพิ่มเติม)
    print("\n🔧 ทดสอบเพิ่มเติม: การตัดวิดีโอ")
    trim_result = tester.test_video_trim(file_path)
    results['trim'] = trim_result
    
    # ทดสอบการสร้าง Close Caption (ทดสอบเพิ่มเติม)
    print("\n🔧 ทดสอบเพิ่มเติม: การสร้าง Close Caption")
    caption_result = tester.test_close_caption(file_path)
    results['close_caption'] = caption_result
    
    # 3. บันทึกผลลัพธ์
    tester.save_results(results)
    
    print("\n🎉 การทดสอบเสร็จสิ้น!")
    print("\n📊 สรุปผลลัพธ์:")
    for feature, result in results.items():
        status = "✅ สำเร็จ" if result else "❌ ล้มเหลว"
        print(f"  {feature}: {status}")
    
    # แสดงข้อความสำคัญ
    if results.get('segmentation'):
        print("\n🎯 ผลลัพธ์หลัก: การแบ่งตอนวิดีโอสำเร็จ!")
        print("📁 ไฟล์ที่ได้:")
        print("  - วิดีโอแต่ละตอนใน temp/")
        print("  - ข้อความรวมใน full_transcription.txt")
        print("  - ผลลัพธ์รายละเอียดใน test_results.json")

if __name__ == "__main__":
    main() 