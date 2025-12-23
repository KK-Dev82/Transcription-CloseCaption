#!/usr/bin/env python3
"""
Test Script สำหรับทดสอบ 25 Concurrent Requests
ส่ง 25 requests พร้อมกันด้วยไฟล์ v30-1.mp4 จาก korrakang
ตรวจสอบความเสถียร - ควรรับได้ 25/25 ไม่มี chunk fail
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import List, Dict
import sys
from pathlib import Path

# API endpoint
API_BASE_URL = "http://localhost:8010"
TEST_FILE = "v30-1.mp4"
KORRAKANG_BASE_URL = "https://korrakang.com/video"  # URL สำหรับ video files

async def send_transcription_request(session: aiohttp.ClientSession, request_id: int) -> Dict:
    """ส่ง transcription request"""
    url = f"{API_BASE_URL}/api/transcribe/"
    
    # ใช้ file_url จาก korrakang
    file_url = f"{KORRAKANG_BASE_URL}/{TEST_FILE}"
    
    payload = {
        "file_url": file_url,
        "language": "th",
        "model_size": "base",
        "chunk_duration": 150,
        "use_chunking": True
    }
    
    start_time = time.time()
    try:
        # เพิ่ม timeout สำหรับการดาวน์โหลดไฟล์ขนาดใหญ่ (307MB)
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=300, connect=30)) as response:
            if response.status == 429:
                return {
                    "request_id": request_id,
                    "status": "rate_limited",
                    "status_code": 429,
                    "error": "Rate limit exceeded",
                    "response_time": time.time() - start_time
                }
            
            response_data = await response.json()
            return {
                "request_id": request_id,
                "status": "success" if response.status == 200 else "error",
                "status_code": response.status,
                "task_id": response_data.get("task_id"),
                "response": response_data,
                "response_time": time.time() - start_time
            }
    except asyncio.TimeoutError:
        return {
            "request_id": request_id,
            "status": "timeout",
            "error": "Request timeout",
            "response_time": time.time() - start_time
        }
    except Exception as e:
        return {
            "request_id": request_id,
            "status": "error",
            "error": str(e),
            "response_time": time.time() - start_time
        }

async def check_task_status(session: aiohttp.ClientSession, task_id: str) -> Dict:
    """ตรวจสอบสถานะ task"""
    url = f"{API_BASE_URL}/api/tasks/{task_id}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                return await response.json()
            return {"status": "error", "status_code": response.status}
    except Exception as e:
        return {"status": "error", "error": str(e)}

async def monitor_tasks(session: aiohttp.ClientSession, task_ids: List[str], max_wait: int = 3600):
    """Monitor tasks จนเสร็จทั้งหมด"""
    print(f"\n📊 Monitoring {len(task_ids)} tasks...")
    start_time = time.time()
    completed = set()
    failed = set()
    
    while len(completed) + len(failed) < len(task_ids):
        if time.time() - start_time > max_wait:
            print(f"⏰ Timeout after {max_wait}s")
            break
        
        for task_id in task_ids:
            if task_id in completed or task_id in failed:
                continue
            
            status_data = await check_task_status(session, task_id)
            status = status_data.get("status", "unknown")
            progress = status_data.get("progress", 0)
            current_stage = status_data.get("current_stage", "unknown")
            
            if status == "completed":
                completed.add(task_id)
                print(f"✅ Task {task_id[:8]}... completed (Progress: {progress}%)")
            elif status == "failed":
                failed.add(task_id)
                error = status_data.get("error_message", "Unknown error")
                print(f"❌ Task {task_id[:8]}... failed: {error}")
            else:
                # แสดง progress ทุก 10% หรือเมื่อ stage เปลี่ยน
                if progress % 10 == 0 or current_stage != "unknown":
                    print(f"⏳ Task {task_id[:8]}... {status} ({progress}%) - {current_stage}")
        
        # รอ 5 วินาทีก่อน check อีกครั้ง
        await asyncio.sleep(5)
    
    elapsed = time.time() - start_time
    return {
        "completed": len(completed),
        "failed": len(failed),
        "total": len(task_ids),
        "elapsed_time": elapsed
    }

async def main():
    """Main test function"""
    print("=" * 80)
    print("🧪 Testing 25 Concurrent Transcription Requests")
    print("=" * 80)
    print(f"File: {TEST_FILE} from {KORRAKANG_BASE_URL}")
    print(f"API: {API_BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 80)
    
    # สร้าง session
    connector = aiohttp.TCPConnector(limit=30)  # Allow up to 30 concurrent connections
    timeout = aiohttp.ClientTimeout(total=300, connect=30)  # เพิ่ม timeout สำหรับการดาวน์โหลดไฟล์ขนาดใหญ่
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # ส่ง 25 requests พร้อมกัน
        print(f"\n📤 Sending 25 concurrent requests...")
        start_time = time.time()
        
        tasks = [send_transcription_request(session, i+1) for i in range(25)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        send_time = time.time() - start_time
        print(f"✅ All requests sent in {send_time:.2f}s\n")
        
        # วิเคราะห์ผลลัพธ์
        successful = []
        rate_limited = []
        errors = []
        
        for result in results:
            if isinstance(result, Exception):
                errors.append({"error": str(result)})
            elif result.get("status") == "success":
                successful.append(result)
            elif result.get("status") == "rate_limited":
                rate_limited.append(result)
            else:
                errors.append(result)
        
        print("=" * 80)
        print("📊 Request Results:")
        print("=" * 80)
        print(f"✅ Successful: {len(successful)}/25")
        print(f"⚠️  Rate Limited (429): {len(rate_limited)}/25")
        print(f"❌ Errors: {len(errors)}/25")
        print("=" * 80)
        
        if rate_limited:
            print("\n⚠️  Rate Limited Requests:")
            for r in rate_limited:
                print(f"   Request {r['request_id']}: {r.get('error', 'Rate limit exceeded')}")
        
        if errors:
            print("\n❌ Error Requests:")
            for r in errors:
                print(f"   Request {r.get('request_id', '?')}: {r.get('error', 'Unknown error')}")
        
        # ดึง task_ids จาก successful requests
        task_ids = [r["task_id"] for r in successful if r.get("task_id")]
        
        if not task_ids:
            print("\n❌ No successful requests to monitor")
            return
        
        print(f"\n📋 Monitoring {len(task_ids)} tasks...")
        
        # Monitor tasks
        monitor_results = await monitor_tasks(session, task_ids)
        
        # สรุปผลลัพธ์
        print("\n" + "=" * 80)
        print("📊 Final Results:")
        print("=" * 80)
        print(f"Total Requests: 25")
        print(f"Successful Requests: {len(successful)}/25")
        print(f"Rate Limited: {len(rate_limited)}/25")
        print(f"Errors: {len(errors)}/25")
        print(f"\nTask Completion:")
        print(f"  Completed: {monitor_results['completed']}/{monitor_results['total']}")
        print(f"  Failed: {monitor_results['failed']}/{monitor_results['total']}")
        print(f"  Elapsed Time: {monitor_results['elapsed_time']:.2f}s ({monitor_results['elapsed_time']/60:.2f} minutes)")
        print("=" * 80)
        
        # ตรวจสอบความเสถียร
        success_rate = len(successful) / 25 * 100
        completion_rate = monitor_results['completed'] / monitor_results['total'] * 100 if monitor_results['total'] > 0 else 0
        
        print("\n🎯 Stability Check:")
        print(f"  Request Success Rate: {success_rate:.1f}% (Target: 100%)")
        print(f"  Task Completion Rate: {completion_rate:.1f}% (Target: 100%)")
        
        if success_rate == 100 and completion_rate == 100:
            print("  ✅ PASS: All 25 requests accepted and completed successfully!")
        elif success_rate == 100:
            print(f"  ⚠️  PARTIAL: All requests accepted but {monitor_results['failed']} tasks failed")
        else:
            print(f"  ❌ FAIL: Only {len(successful)}/25 requests accepted")
        
        print("=" * 80)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

