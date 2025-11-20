#!/usr/bin/env python3
"""
สคริปต์รันการทดสอบทั้งหมด
"""

import subprocess
import sys
import time
from pathlib import Path

def run_test(test_file, description):
    """รันไฟล์ทดสอบ"""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"📁 ไฟล์: {test_file}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ {description} - สำเร็จ")
            if result.stdout:
                print("📄 Output:")
                print(result.stdout)
        else:
            print(f"❌ {description} - ล้มเหลว")
            if result.stderr:
                print("❌ Error:")
                print(result.stderr)
            if result.stdout:
                print("📄 Output:")
                print(result.stdout)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - หมดเวลา")
        return False
    except Exception as e:
        print(f"❌ {description} - เกิดข้อผิดพลาด: {e}")
        return False

def main():
    """รันการทดสอบทั้งหมด"""
    print("🚀 เริ่มรันการทดสอบทั้งหมด")
    print("=" * 60)
    
    # ตรวจสอบว่าไฟล์ทดสอบมีอยู่
    test_files = [
        ("test_api_endpoints.py", "API Endpoints Testing"),
        ("test_transcription.py", "Transcription API Testing"),
        ("test_transcription_docker.py", "Docker Transcription Testing"),
        ("test_video_features.py", "Video Features Testing"),
        ("test_video_segmentation.py", "Video Segmentation Testing"),
        ("test_video_trim.py", "Video Trim Testing"),
        ("test_segmentation_only.py", "Segmentation Only Testing"),
        ("test_thai_processing.py", "Thai Text Processing Testing")
    ]
    
    # ตรวจสอบไฟล์ที่ขาดหายไป
    missing_files = []
    for test_file, _ in test_files:
        if not Path(test_file).exists():
            missing_files.append(test_file)
    
    if missing_files:
        print("❌ ไฟล์ทดสอบที่ขาดหายไป:")
        for file in missing_files:
            print(f"  - {file}")
        print("\nกรุณาตรวจสอบว่าไฟล์ทดสอบอยู่ในโฟลเดอร์เดียวกัน")
        return
    
    # รันการทดสอบ
    results = {}
    start_time = time.time()
    
    for test_file, description in test_files:
        success = run_test(test_file, description)
        results[description] = success
        time.sleep(2)  # รอ 2 วินาทีระหว่าง tests
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # สรุปผลลัพธ์
    print(f"\n{'='*60}")
    print("📊 สรุปผลลัพธ์การทดสอบ")
    print(f"{'='*60}")
    
    passed = sum(1 for success in results.values() if success)
    failed = len(results) - passed
    
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/len(results))*100:.1f}%")
    print(f"Total Time: {total_time:.2f}s")
    print()
    
    for description, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {description}")
    
    print(f"\n{'='*60}")
    
    if failed == 0:
        print("🎉 การทดสอบทั้งหมดสำเร็จ!")
    else:
        print(f"⚠️  {failed} การทดสอบล้มเหลว กรุณาตรวจสอบและแก้ไข")
    
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
