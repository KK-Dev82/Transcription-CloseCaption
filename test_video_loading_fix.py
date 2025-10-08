#!/usr/bin/env python3
"""
Script ทดสอบการแก้ไขปัญหา Failed to fetch เมื่อโหลดไฟล์วิดีโอจาก history
"""

import requests
import json
import sys
from pathlib import Path

# Configuration
LOCAL_BASE_URL = "http://localhost:8001"
STAGING_BASE_URL = "https://staging-ph2.bms.senate.go.th/transcribe"

def test_endpoints(base_url, environment_name):
    """ทดสอบ endpoints ต่างๆ"""
    print(f"\n🔍 ทดสอบ {environment_name} Environment")
    print(f"Base URL: {base_url}")
    
    # 1. ทดสอบ Health Check
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health Check: OK")
        else:
            print(f"❌ Health Check: Failed ({response.status_code})")
    except Exception as e:
        print(f"❌ Health Check: Error - {e}")
    
    # 2. ทดสอบ History API
    try:
        response = requests.get(f"{base_url}/history/transcriptions?limit=5", timeout=10)
        if response.status_code == 200:
            data = response.json()
            history_items = data.get("history", [])
            print(f"✅ History API: OK ({len(history_items)} items)")
            
            # ทดสอบกับ task แรก
            if history_items:
                first_task = history_items[0]
                task_id = first_task.get("task_id")
                print(f"📋 Testing with task: {task_id}")
                
                # 3. ทดสอบ Metadata API
                try:
                    meta_response = requests.get(f"{base_url}/metadata/{task_id}", timeout=10)
                    if meta_response.status_code == 200:
                        meta_data = meta_response.json()
                        print("✅ Metadata API: OK")
                        print(f"   File exists: {meta_data.get('file_exists')}")
                        print(f"   File name: {meta_data.get('file_name')}")
                        print(f"   URLs: {meta_data.get('urls', {})}")
                    else:
                        print(f"❌ Metadata API: Failed ({meta_response.status_code})")
                except Exception as e:
                    print(f"❌ Metadata API: Error - {e}")
                
                # 4. ทดสอบ File Serving
                file_path = first_task.get("file_path", "")
                if file_path:
                    clean_path = file_path.replace("uploads/", "") if file_path.startswith("uploads/") else file_path
                    
                    # ทดสอบ endpoints ต่างๆ
                    endpoints_to_test = [
                        f"/file/{clean_path}",
                        f"/uploads/{clean_path}",
                        f"/media-uploads/{clean_path}"
                    ]
                    
                    for endpoint in endpoints_to_test:
                        try:
                            file_response = requests.head(f"{base_url}{endpoint}", timeout=5)
                            if file_response.status_code == 200:
                                print(f"✅ File serving {endpoint}: OK")
                            else:
                                print(f"❌ File serving {endpoint}: Failed ({file_response.status_code})")
                        except Exception as e:
                            print(f"❌ File serving {endpoint}: Error - {e}")
                
        else:
            print(f"❌ History API: Failed ({response.status_code})")
    except Exception as e:
        print(f"❌ History API: Error - {e}")

def main():
    """Main function"""
    print("🚀 ทดสอบการแก้ไขปัญหา Failed to fetch เมื่อโหลดไฟล์วิดีโอ")
    
    # ทดสอบ Local Environment
    test_endpoints(LOCAL_BASE_URL, "Local")
    
    # ทดสอบ Staging Environment
    test_endpoints(STAGING_BASE_URL, "Staging")
    
    print("\n📋 สรุปการแก้ไขที่ทำ:")
    print("1. ✅ เพิ่ม /media-uploads static mount สำหรับ staging compatibility")
    print("2. ✅ ปรับปรุง /file/{file_path:path} endpoint ให้รองรับ alternative paths")
    print("3. ✅ เพิ่ม /metadata/{task_id} endpoint สำหรับดึงข้อมูลไฟล์")
    print("4. ✅ เพิ่ม support สำหรับไฟล์ใน storage directory")
    print("5. ✅ เพิ่ม media types เพิ่มเติม (.avi, .mov)")
    
    print("\n🔧 วิธีใช้งาน:")
    print("- Local: ใช้ /file/{filename} หรือ /uploads/{filename}")
    print("- Staging: ใช้ /media-uploads/{filename} หรือ /file/{filename}")
    print("- Metadata: ใช้ /metadata/{task_id} เพื่อดูข้อมูลไฟล์")

if __name__ == "__main__":
    main()
