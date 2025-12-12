#!/usr/bin/env python3
"""
Send 50 Tasks Final - ส่ง 50 tasks และ monitor จนเสร็จ
ใช้ Batch API เหมือน dashboard (เสถียรกว่า)
"""
import asyncio
import aiohttp
import sys
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

dashboard_dir = Path(__file__).parent
sys.path.insert(0, str(dashboard_dir))

try:
    from server_constants import SERVERS
except ImportError:
    from config import SERVERS

# Dashboard API URL (assume running locally or set via env)
DASHBOARD_API_URL = os.getenv("DASHBOARD_API_URL", "http://localhost:8020")  # Default dashboard port

async def start_batch_transcription(server_name: str, video_files: list, model_size: str = "base", language: str = "th", concurrency: int = None):
    """Start batch transcription using dashboard API"""
    if concurrency is None:
        concurrency = len(video_files)  # ส่งพร้อมกันทั้งหมด
    
    async with aiohttp.ClientSession() as session:
        payload = {
            "server_name": server_name,
            "video_files": video_files,
            "concurrency": concurrency,  # ใช้ concurrency ที่กำหนด
            "model_size": model_size,
            "language": language,
            "use_chunking": False
        }
        
        try:
            async with session.post(
                f"{DASHBOARD_API_URL}/api/batch/transcription",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("batch_id")
                else:
                    error_text = await response.text()
                    print(f"❌ Batch API error: {response.status} - {error_text}")
                    return None
        except Exception as e:
            print(f"❌ Error calling batch API: {e}")
            return None

async def get_batch_status(batch_id: str):
    """Get batch status"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{DASHBOARD_API_URL}/api/batch/{batch_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
        except:
            return None

async def get_task_detail(server_name: str, task_id: str):
    """Get task detail from server API"""
    if server_name not in SERVERS:
        return {"status": "unknown"}
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{api_url}/transcribe/{task_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "status": result.get("status", "unknown"),
                        "processing_time": result.get("processing_time") or result.get("time_used"),
                        "audio_extraction_time": result.get("audio_extraction_time"),
                        "transcription_time": result.get("transcription_time"),
                        "model_size": result.get("model_size", "unknown"),
                        "full_text": result.get("full_text") or result.get("corrected_text") or result.get("original_text"),
                        "created_at": result.get("created_at"),
                        "completed_at": result.get("completed_at") or result.get("updated_at"),
                        "file_name": result.get("file_name") or result.get("filename")
                    }
                else:
                    return {"status": "unknown"}
        except:
            return {"status": "unknown"}

async def check_dashboard_available():
    """Check if dashboard API is available"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{DASHBOARD_API_URL}/api/servers",
                timeout=aiohttp.ClientTimeout(total=2)
            ) as response:
                return response.status == 200
    except:
        return False

async def main():
    server_name = '4000-ada-sc'
    if server_name not in SERVERS:
        print(f'❌ Server {server_name} not found')
        return
    
    file_path = '/workspace/transcription-service/uploads/v10-1.mp4'
    target_count = 50
    
    # ตรวจสอบว่า dashboard ทำงานอยู่หรือไม่
    dashboard_available = await check_dashboard_available()
    
    print('='*80)
    if dashboard_available:
        print('📤 กำลังส่ง 50 tasks ไปทดสอบ (ใช้ Batch API เหมือน Dashboard)...')
        print(f'✅ Dashboard API พร้อมใช้งาน: {DASHBOARD_API_URL}')
    else:
        print('📤 กำลังส่ง 50 tasks ไปทดสอบ...')
        print(f'⚠️  Dashboard API ไม่พร้อมใช้งาน ({DASHBOARD_API_URL})')
        print('   จะใช้วิธีส่งตรงผ่าน SSH แทน')
    print(f'Server: {server_name}')
    print(f'File Path: {file_path}')
    print(f'Target: {target_count} tasks')
    print('='*80)
    print()
    
    start_time = datetime.now(timezone.utc)
    task_ids = []
    
    if dashboard_available:
        # ใช้ Batch API (เสถียรกว่า) - ส่งพร้อมกัน 50 tasks
        print('📤 Sending batch transcription via Dashboard API...')
        print(f'   Concurrency: {target_count} (ส่งพร้อมกันทั้งหมด)')
        video_files = [file_path] * target_count
        
        batch_id = await start_batch_transcription(
            server_name=server_name,
            video_files=video_files,
            model_size='base',
            language='th',
            concurrency=target_count  # ส่งพร้อมกัน 50 tasks
        )
        
        if not batch_id:
            print('❌ ไม่สามารถสร้าง batch transcription ได้')
            return
        
        print(f'✅ Batch created: {batch_id}')
        print()
        
        # รอ task_ids จาก batch
        print('⏳ กำลังรอ task_ids จาก batch...')
        max_wait = 60  # รอสูงสุด 60 วินาที
        
        for i in range(max_wait):
            await asyncio.sleep(1)
            batch_status = await get_batch_status(batch_id)
            
            if batch_status and batch_status.get("task_ids"):
                task_ids = batch_status["task_ids"]
                if len(task_ids) == target_count:
                    print(f'✅ ได้รับ task_ids ทั้งหมด: {len(task_ids)} tasks')
                    break
                elif len(task_ids) > 0:
                    print(f'⏳ ได้รับ task_ids: {len(task_ids)}/{target_count}...')
            elif batch_status and batch_status.get("status") == "failed":
                print(f'❌ Batch failed!')
                return
        
        if len(task_ids) == 0:
            print('❌ ไม่ได้รับ task_ids จาก batch')
            return
    else:
        # ใช้วิธีเดิม (SSH) - ต้อง import functions เดิม
        print('❌ Dashboard API ไม่พร้อมใช้งาน')
        print('   กรุณารัน dashboard ก่อน: cd dashboard && python3 main.py')
        print('   หรือตั้งค่า DASHBOARD_API_URL environment variable')
        return
    
    if len(task_ids) < target_count:
        print(f'⚠️  เตือน: ได้รับเพียง {len(task_ids)}/{target_count} task_ids')
    
    print(f'Task IDs (first 5): {[t[:36] for t in task_ids[:5]]}')
    print(f'Task IDs (last 5): {[t[:36] for t in task_ids[-5:]]}')
    print()
    print('🔍 กำลัง monitor จนเสร็จทั้งหมด...')
    print('='*80)
    
    # Monitor until all completed
    check_interval = 30
    
    while True:
        await asyncio.sleep(check_interval)
        
        completed = 0
        failed = 0
        processing = 0
        pending = 0
        routing = 0
        
        for task_id in task_ids:
            detail = await get_task_detail(server_name, task_id)
            status = detail.get("status", "unknown").lower()
            
            if status == 'completed':
                completed += 1
            elif status == 'failed':
                failed += 1
            elif status in ['processing', 'transcribing']:
                processing += 1
            elif status == 'routing':
                routing += 1
            else:
                pending += 1
        
        current_time = datetime.now(timezone.utc)
        elapsed = (current_time - start_time).total_seconds() / 60
        
        thai_tz = timezone(timedelta(hours=7))
        current_thai = current_time.astimezone(thai_tz)
        
        status_line = f'[{current_thai.strftime("%H:%M:%S")}] Completed: {completed}/{len(task_ids)}, Processing: {processing}, Routing: {routing}, Pending: {pending}, Failed: {failed} | Elapsed: {elapsed:.1f} min'
        print(status_line)
        
        if completed + failed >= len(task_ids):
            break
    
    # Get final details for analysis
    print()
    print('📊 กำลังรวบรวมข้อมูลสำหรับวิเคราะห์...')
    
    processing_times = []
    audio_extraction_times = []
    transcription_times = []
    task_details = []
    model_sizes = set()
    full_texts = []
    
    for task_id in task_ids:
        detail = await get_task_detail(server_name, task_id)
        status = detail.get("status", "unknown").lower()
        
        if status == 'completed':
            task_details.append(detail)
            
            pt = detail.get("processing_time")
            if pt is not None:
                try:
                    processing_times.append(float(pt))
                except:
                    pass
            
            aet = detail.get("audio_extraction_time")
            if aet is not None:
                try:
                    audio_extraction_times.append(float(aet))
                except:
                    pass
            
            tt = detail.get("transcription_time")
            if tt is not None:
                try:
                    transcription_times.append(float(tt))
                except:
                    pass
            
            model_size = detail.get("model_size")
            if model_size:
                model_sizes.add(model_size)
            
            full_text = detail.get("full_text")
            if full_text:
                full_texts.append(full_text)
    
    end_time = datetime.now(timezone.utc)
    wall_clock_duration = (end_time - start_time).total_seconds()
    
    thai_tz = timezone(timedelta(hours=7))
    start_thai = start_time.astimezone(thai_tz)
    end_thai = end_time.astimezone(thai_tz)
    
    # คำนวณ start/end time จาก tasks
    first_created = None
    last_completed = None
    
    for detail in task_details:
        created_at = detail.get("created_at")
        completed_at = detail.get("completed_at")
        
        if created_at:
            try:
                if 'Z' in created_at:
                    created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created_dt = datetime.fromisoformat(created_at)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                
                if first_created is None or created_dt < first_created:
                    first_created = created_dt
            except:
                pass
        
        if completed_at:
            try:
                if 'Z' in completed_at:
                    completed_dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                else:
                    completed_dt = datetime.fromisoformat(completed_at)
                    if completed_dt.tzinfo is None:
                        completed_dt = completed_dt.replace(tzinfo=timezone.utc)
                
                if last_completed is None or completed_dt > last_completed:
                    last_completed = completed_dt
            except:
                pass
    
    # ถ้าไม่มี first_created/last_completed ใช้ start_time/end_time แทน
    if first_created is None:
        first_created = start_time
    if last_completed is None:
        last_completed = end_time
    
    total_task_duration = (last_completed - first_created).total_seconds()
    first_created_thai = first_created.astimezone(thai_tz)
    last_completed_thai = last_completed.astimezone(thai_tz)
    
    # วิเคราะห์คุณภาพข้อความไทย
    thai_quality = {
        "total_tasks_with_text": len(full_texts),
        "total_chars": 0,
        "thai_chars": 0,
        "has_thai": 0
    }
    
    for text in full_texts:
        if text:
            thai_quality["total_chars"] += len(text)
            thai_chars = sum(1 for c in text if '\u0e00' <= c <= '\u0e7f')
            thai_quality["thai_chars"] += thai_chars
            if thai_chars > 0:
                thai_quality["has_thai"] += 1
    
    print()
    print('='*80)
    print('📈 สรุปผลการทดสอบ:')
    print('='*80)
    print(f'📤 Tasks ที่ส่งไป: {len(task_ids)}/{target_count} tasks')
    print(f'✅ Completed: {completed}/{len(task_ids)}')
    print(f'❌ Failed: {failed}/{len(task_ids)}')
    
    # ตรวจสอบว่า completed ครบหรือไม่
    if completed < len(task_ids):
        print(f'⚠️  เตือน: Completed ไม่ครบ! ({completed}/{len(task_ids)})')
    
    print()
    print('1️⃣  START/END TIME:')
    print(f'   ⏰ Start Task: {first_created_thai.strftime("%Y-%m-%d %H:%M:%S")} (UTC+7)')
    print(f'   ⏰ End Task (completed): {last_completed_thai.strftime("%Y-%m-%d %H:%M:%S")} (UTC+7)')
    print(f'   ⏱️  ใช้เวลาทั้งหมด: {total_task_duration/60:.1f} นาที ({total_task_duration/3600:.2f} ชั่วโมง)')
    print()
    
    # Processing time analysis
    print('2️⃣  AVERAGE TRANSCRIPTION TIME PER TASK:')
    if transcription_times:
        avg_trans = sum(transcription_times) / len(transcription_times)
        min_trans = min(transcription_times)
        max_trans = max(transcription_times)
        print(f'   ⏱️  Average: {avg_trans:.2f} วินาที ({avg_trans/60:.2f} นาที)')
        print(f'   ⏱️  Min: {min_trans:.2f} วินาที')
        print(f'   ⏱️  Max: {max_trans:.2f} วินาที')
        print(f'   📊 Tasks ที่มี transcription_time: {len(transcription_times)}/{completed} tasks')
    elif processing_times:
        avg_processing = sum(processing_times) / len(processing_times)
        print(f'   ⏱️  Average Processing Time: {avg_processing:.2f} วินาที ({avg_processing/60:.2f} นาที)')
        print(f'   📊 Tasks ที่มี processing_time: {len(processing_times)}/{completed} tasks')
    else:
        print('   ⚠️  ไม่มีข้อมูล transcription_time')
    print()
    
    print('3️⃣  MODEL ที่ใช้:')
    if model_sizes:
        print(f'   🤖 Models: {", ".join(sorted(model_sizes))}')
    else:
        print('   ⚠️  ไม่พบข้อมูล model')
    print()
    
    print('4️⃣  TEXT CORRECTION QUALITY:')
    if thai_quality["total_tasks_with_text"] > 0:
        thai_percentage = (thai_quality["thai_chars"] / thai_quality["total_chars"] * 100) if thai_quality["total_chars"] > 0 else 0
        print(f'   📝 Tasks ที่มี text: {thai_quality["total_tasks_with_text"]}/{completed} tasks')
        print(f'   📊 Total Characters: {thai_quality["total_chars"]:,} ตัวอักษร')
        print(f'   🇹🇭 Thai Characters: {thai_quality["thai_chars"]:,} ตัวอักษร ({thai_percentage:.1f}%)')
        print(f'   ✅ Tasks with Thai text: {thai_quality["has_thai"]}/{thai_quality["total_tasks_with_text"]} tasks')
        if thai_percentage > 50:
            print('   ✅ คุณภาพดี: มีข้อความภาษาไทยมากกว่า 50%')
        elif thai_percentage > 20:
            print('   ⚠️  คุณภาพปานกลาง: มีข้อความภาษาไทย 20-50%')
        else:
            print('   ❌ คุณภาพต่ำ: มีข้อความภาษาไทยน้อยกว่า 20%')
    else:
        print('   ⚠️  ไม่มีข้อมูล text')
    print()
    
    print('5️⃣  FULL TEXT EXAMPLE (Task 1):')
    if full_texts and len(full_texts) > 0:
        example_text = full_texts[0]
        preview_length = 500
        if len(example_text) > preview_length:
            print(f'   📝 (แสดง {preview_length} ตัวอักษรแรก):')
            print(f'   {example_text[:preview_length]}...')
            print(f'   ... (เหลืออีก {len(example_text) - preview_length} ตัวอักษร)')
        else:
            print(f'   📝 (ทั้งหมด {len(example_text)} ตัวอักษร):')
            print(f'   {example_text}')
    else:
        print('   ⚠️  ไม่มีข้อมูล full_text')
    print()
    
    print('6️⃣  GPU USAGE:')
    print('   ⚠️  ต้องตรวจสอบจาก server โดยตรง (nvidia-smi)')
    print('   💡 ใช้คำสั่ง: ssh 4000-ada-sc "nvidia-smi"')
    print()
    
    print('7️⃣  สรุปผลและข้อเสนอแนะ:')
    print('   📊 Performance:')
    if transcription_times:
        avg_trans = sum(transcription_times) / len(transcription_times)
        if avg_trans < 60:
            print(f'      ✅ ดี: Average transcription time {avg_trans:.1f}s ต่อ task')
        elif avg_trans < 120:
            print(f'      ⚠️  ปานกลาง: Average transcription time {avg_trans:.1f}s ต่อ task')
        else:
            print(f'      ❌ ช้า: Average transcription time {avg_trans:.1f}s ต่อ task')
    
    if total_task_duration < 3600:
        print(f'      ✅ ดี: Total duration {total_task_duration/60:.1f} นาที (< 1 ชั่วโมง)')
    else:
        print(f'      ⚠️  ใช้เวลานาน: Total duration {total_task_duration/3600:.2f} ชั่วโมง')
    
    print('   🔒 Stability:')
    success_rate = (completed / len(task_ids) * 100) if len(task_ids) > 0 else 0
    if success_rate >= 95:
        print(f'      ✅ ดีมาก: Success rate {success_rate:.1f}%')
    elif success_rate >= 80:
        print(f'      ⚠️  ปานกลาง: Success rate {success_rate:.1f}%')
    else:
        print(f'      ❌ ต่ำ: Success rate {success_rate:.1f}%')
    
    if len(task_ids) < target_count:
        print(f'      ⚠️  ส่งได้ไม่ครบ: {len(task_ids)}/{target_count} tasks')
    
    print('   🎯 Accuracy:')
    if thai_quality["total_tasks_with_text"] > 0:
        thai_percentage = (thai_quality["thai_chars"] / thai_quality["total_chars"] * 100) if thai_quality["total_chars"] > 0 else 0
        if thai_percentage > 50:
            print(f'      ✅ ดี: มีข้อความภาษาไทย {thai_percentage:.1f}%')
        else:
            print(f'      ⚠️  ควรปรับปรุง: มีข้อความภาษาไทย {thai_percentage:.1f}%')
    
    print()
    print('   💡 ข้อเสนอแนะ:')
    if total_task_duration > 3600:
        print('      - พิจารณาเพิ่ม concurrency หรือใช้ GPU เพิ่มเติม')
    if success_rate < 95:
        print('      - ตรวจสอบ error logs และเพิ่ม retry mechanism')
    if thai_quality["total_tasks_with_text"] > 0:
        thai_percentage = (thai_quality["thai_chars"] / thai_quality["total_chars"] * 100) if thai_quality["total_chars"] > 0 else 0
        if thai_percentage < 50:
            print('      - ตรวจสอบ model และ language settings')
            print('      - พิจารณาใช้ model ที่ใหญ่กว่า (medium/large)')
    
    print()
    print('='*80)

if __name__ == '__main__':
    asyncio.run(main())
