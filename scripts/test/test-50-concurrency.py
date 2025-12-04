#!/usr/bin/env python3
"""
สคริปต์ทดสอบ 50 Concurrency สำหรับ Transcription Service

ทดสอบการส่ง 50 requests พร้อมกันไปยัง Transcription Service
เพื่อดู:
1. เวลารวมในการแปลงทั้งหมดทุก Task กี่นาที
2. เวลาที่ใช้แปลงแต่ละ task เท่าไร
"""

import asyncio
import aiohttp
import json
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import statistics
from collections import defaultdict

class ConcurrencyTest:
    def __init__(
        self,
        api_url: str,
        num_concurrent: int = 5,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        language: str = "th",
        model_size: str = "medium",
        poll_interval: int = 5
    ):
        self.api_url = api_url.rstrip('/')
        self.num_concurrent = num_concurrent
        self.file_path = file_path
        self.file_url = file_url
        self.file_name = file_name or "test-video-10min.mp4"
        self.language = language
        self.model_size = model_size
        self.poll_interval = poll_interval
        
        # Results storage
        self.results: List[Dict] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        # Metrics
        self.metrics = {
            'request_times': [],  # เวลาที่ใช้ในการส่ง request
            'queue_wait_times': [],  # เวลารอใน queue (created_at -> started processing)
            'processing_times': [],  # เวลาที่ใช้ในการประมวลผล (time_used)
            'total_times': [],  # เวลารวมทั้งหมด (created_at -> completed_at)
            'errors': []
        }
    
    async def send_transcription_request(
        self,
        session: aiohttp.ClientSession,
        task_id: int
    ) -> Dict:
        """ส่ง transcription request"""
        request_start = time.time()
        
        try:
            # ตรวจสอบ file_path ถ้าใช้ local file
            if self.file_path:
                # ถ้า file_path ไม่มี absolute path ให้ตรวจสอบจาก API
                # หรือใช้ file_url แทน
                pass  # Server จะตรวจสอบเอง
            
            payload = {
                "language": self.language,
                "model_size": self.model_size,
                "use_chunking": False
            }
            
            if self.file_path:
                payload["file_path"] = self.file_path
            elif self.file_url:
                payload["file_url"] = self.file_url
            else:
                raise ValueError("ต้องระบุ file_path หรือ file_url")
            
            if self.file_name:
                payload["file_name"] = self.file_name
            
            async with session.post(
                f'{self.api_url}/transcribe/',
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                request_time = time.time() - request_start
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Request failed: {response.status} - {error_text}")
                
                result = await response.json()
                task_id_value = result.get('task_id')
                
                return {
                    'task_id': task_id,
                    'api_task_id': task_id_value,
                    'status': result.get('status'),
                    'request_time': request_time,
                    'created_at': result.get('created_at'),
                    'success': True
                }
        except Exception as e:
            request_time = time.time() - request_start
            return {
                'task_id': task_id,
                'request_time': request_time,
                'success': False,
                'error': str(e)
            }
    
    async def poll_task_status(
        self,
        session: aiohttp.ClientSession,
        api_task_id: str,
        task_id: int,
        created_at: Optional[str]
    ) -> Dict:
        """Poll task status จนกว่า completed"""
        created_timestamp = None
        if created_at:
            try:
                from dateutil import parser
                created_timestamp = parser.parse(created_at).timestamp()
            except:
                pass
        
        last_status = None
        last_progress = 0
        
        while True:
            try:
                async with session.get(
                    f'{self.api_url}/transcribe/{api_task_id}',
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        current_status = result.get('status')
                        current_progress = result.get('progress', 0)
                        
                        # Log progress changes
                        if current_status != last_status or current_progress != last_progress:
                            print(f"  Task {task_id} ({api_task_id[:8]}...): {current_status} - {current_progress}%")
                            last_status = current_status
                            last_progress = current_progress
                        
                        if current_status == 'completed':
                            completed_at = result.get('completed_at')
                            time_used = result.get('time_used')
                            created_at_result = result.get('created_at')
                            
                            # คำนวณเวลาต่างๆ
                            completed_timestamp = None
                            if completed_at:
                                try:
                                    from dateutil import parser
                                    completed_timestamp = parser.parse(completed_at).timestamp()
                                except:
                                    pass
                            
                            # Total time (created -> completed)
                            total_time = None
                            if created_timestamp and completed_timestamp:
                                total_time = completed_timestamp - created_timestamp
                            
                            # Processing time
                            processing_time = time_used
                            
                            # Queue wait time (approx: total - processing)
                            queue_wait_time = None
                            if total_time is not None and processing_time is not None:
                                queue_wait_time = max(0, total_time - processing_time)
                            
                            return {
                                'task_id': task_id,
                                'api_task_id': api_task_id,
                                'status': 'completed',
                                'total_time': total_time,
                                'processing_time': processing_time,
                                'queue_wait_time': queue_wait_time,
                                'created_at': created_at_result,
                                'completed_at': completed_at,
                                'success': True
                            }
                        elif current_status in ['failed', 'cancelled']:
                            error_message = result.get('error_message', 'Unknown error')
                            return {
                                'task_id': task_id,
                                'api_task_id': api_task_id,
                                'status': current_status,
                                'error': error_message,
                                'success': False
                            }
                    else:
                        error_text = await response.text()
                        print(f"  ⚠️  Task {task_id}: HTTP {response.status} - {error_text[:100]}")
                
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                print(f"  ⚠️  Task {task_id}: Poll error - {str(e)[:100]}")
                await asyncio.sleep(self.poll_interval)
    
    async def run_single_task(self, session: aiohttp.ClientSession, task_id: int) -> Dict:
        """รันการทดสอบสำหรับ 1 task"""
        task_start = time.time()
        result = {
            'task_id': task_id,
            'request_result': None,
            'poll_result': None,
            'total_time': None,
            'success': False,
            'errors': []
        }
        
        try:
            # Step 1: Send request
            request_result = await self.send_transcription_request(session, task_id)
            result['request_result'] = request_result
            self.metrics['request_times'].append(request_result['request_time'])
            
            if not request_result.get('success'):
                result['errors'].append(f"Request failed: {request_result.get('error')}")
                return result
            
            api_task_id = request_result['api_task_id']
            created_at = request_result.get('created_at')
            
            print(f"✅ Task {task_id}: Request sent - Task ID: {api_task_id[:8]}...")
            
            # Step 2: Poll until completed
            poll_result = await self.poll_task_status(session, api_task_id, task_id, created_at)
            result['poll_result'] = poll_result
            
            if poll_result.get('success'):
                result['success'] = True
                
                # Record metrics
                if poll_result.get('total_time'):
                    self.metrics['total_times'].append(poll_result['total_time'])
                if poll_result.get('processing_time'):
                    self.metrics['processing_times'].append(poll_result['processing_time'])
                if poll_result.get('queue_wait_time'):
                    self.metrics['queue_wait_times'].append(poll_result['queue_wait_time'])
                
                total_time = poll_result.get('total_time', 0) or 0
                processing_time = poll_result.get('processing_time', 0) or 0
                queue_wait = poll_result.get('queue_wait_time', 0) or 0
                
                print(f"✅ Task {task_id}: Completed - Total: {total_time:.1f}s, Processing: {processing_time:.1f}s, Queue: {queue_wait:.1f}s")
            else:
                error_msg = poll_result.get('error', f"Status: {poll_result.get('status')}")
                result['errors'].append(f"Polling failed: {error_msg}")
                self.metrics['errors'].append({
                    'task_id': task_id,
                    'error': error_msg
                })
                print(f"❌ Task {task_id}: Failed - {error_msg}")
            
        except Exception as e:
            result['errors'].append(str(e))
            self.metrics['errors'].append({
                'task_id': task_id,
                'error': str(e)
            })
            print(f"❌ Task {task_id}: Exception - {str(e)[:100]}")
        
        result['total_time'] = time.time() - task_start
        return result
    
    async def run_concurrent_test(self):
        """รันการทดสอบพร้อมกัน"""
        print("="*80)
        print(f"🚀 เริ่มการทดสอบ 50 Concurrency")
        print("="*80)
        print(f"API URL: {self.api_url}")
        print(f"จำนวน Tasks: {self.num_concurrent}")
        print(f"File: {self.file_path or self.file_url}")
        print(f"Language: {self.language}")
        print(f"Model: {self.model_size}")
        print(f"Poll Interval: {self.poll_interval}s")
        print("="*80)
        print()
        
        self.start_time = time.time()
        
        connector = aiohttp.TCPConnector(limit=self.num_concurrent, limit_per_host=self.num_concurrent)
        timeout = aiohttp.ClientTimeout(total=7200)  # 2 hours timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # ส่ง requests ทั้งหมดพร้อมกัน
            print(f"📤 ส่ง {self.num_concurrent} requests พร้อมกัน...")
            tasks = [self.run_single_task(session, i + 1) for i in range(self.num_concurrent)]
            
            # รอให้ทุก task เสร็จ
            self.results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # แปลง exceptions เป็น error results
            for i, result in enumerate(self.results):
                if isinstance(result, Exception):
                    self.results[i] = {
                        'task_id': i + 1,
                        'success': False,
                        'errors': [str(result)]
                    }
        
        self.end_time = time.time()
        
        print()
        print("="*80)
        print("✅ การทดสอบเสร็จสิ้น")
        print("="*80)
    
    def generate_report(self, output_file: Optional[str] = None):
        """สร้างรายงานผลการทดสอบ"""
        if not self.results:
            print("⚠️  ไม่มีผลการทดสอบ")
            return
        
        total_test_time = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        successful_results = [r for r in self.results if r.get('success')]
        failed_results = [r for r in self.results if not r.get('success')]
        
        print()
        print("="*80)
        print("📊 รายงานผลการทดสอบ 50 Concurrency")
        print("="*80)
        print()
        
        print("📋 สรุปผลการทดสอบ:")
        print(f"  • จำนวน Tasks ทั้งหมด: {self.num_concurrent}")
        print(f"  • สำเร็จ: {len(successful_results)}")
        print(f"  • ล้มเหลว: {len(failed_results)}")
        print(f"  • อัตราความสำเร็จ: {len(successful_results) / self.num_concurrent * 100:.1f}%")
        print(f"  • เวลารวมการทดสอบ: {total_test_time / 60:.2f} นาที ({total_test_time:.1f} วินาที)")
        print()
        
        if self.metrics['total_times']:
            print("⏱️  เวลารวมในการแปลงทั้งหมดทุก Task:")
            total_times = self.metrics['total_times']
            print(f"  • มากที่สุด: {max(total_times):.1f} วินาที ({max(total_times) / 60:.2f} นาที)")
            print(f"  • น้อยที่สุด: {min(total_times):.1f} วินาที ({min(total_times) / 60:.2f} นาที)")
            print(f"  • เฉลี่ย: {statistics.mean(total_times):.1f} วินาที ({statistics.mean(total_times) / 60:.2f} นาที)")
            print(f"  • มัธยฐาน: {statistics.median(total_times):.1f} วินาที ({statistics.median(total_times) / 60:.2f} นาที)")
            if len(total_times) > 1:
                print(f"  • ส่วนเบี่ยงเบนมาตรฐาน: {statistics.stdev(total_times):.1f} วินาที")
            print()
        
        if self.metrics['processing_times']:
            print("⚙️  เวลาที่ใช้แปลงแต่ละ Task (Processing Time):")
            processing_times = self.metrics['processing_times']
            print(f"  • มากที่สุด: {max(processing_times):.1f} วินาที ({max(processing_times) / 60:.2f} นาที)")
            print(f"  • น้อยที่สุด: {min(processing_times):.1f} วินาที ({min(processing_times) / 60:.2f} นาที)")
            print(f"  • เฉลี่ย: {statistics.mean(processing_times):.1f} วินาที ({statistics.mean(processing_times) / 60:.2f} นาที)")
            print(f"  • มัธยฐาน: {statistics.median(processing_times):.1f} วินาที ({statistics.median(processing_times) / 60:.2f} นาที)")
            if len(processing_times) > 1:
                print(f"  • ส่วนเบี่ยงเบนมาตรฐาน: {statistics.stdev(processing_times):.1f} วินาที")
            print()
        
        if self.metrics['queue_wait_times']:
            print("⏳ เวลารอใน Queue:")
            queue_wait_times = self.metrics['queue_wait_times']
            print(f"  • มากที่สุด: {max(queue_wait_times):.1f} วินาที ({max(queue_wait_times) / 60:.2f} นาที)")
            print(f"  • น้อยที่สุด: {min(queue_wait_times):.1f} วินาที")
            print(f"  • เฉลี่ย: {statistics.mean(queue_wait_times):.1f} วินาที ({statistics.mean(queue_wait_times) / 60:.2f} นาที)")
            print(f"  • มัธยฐาน: {statistics.median(queue_wait_times):.1f} วินาที")
            if len(queue_wait_times) > 1:
                print(f"  • ส่วนเบี่ยงเบนมาตรฐาน: {statistics.stdev(queue_wait_times):.1f} วินาที")
            print()
        
        # Throughput
        if total_test_time > 0:
            print("📈 Throughput:")
            print(f"  • Tasks ต่อนาที: {len(successful_results) / (total_test_time / 60):.2f}")
            print(f"  • Tasks ต่อชั่วโมง: {len(successful_results) / (total_test_time / 3600):.2f}")
            print()
        
        # Errors
        if self.metrics['errors']:
            print(f"❌ ข้อผิดพลาด ({len(self.metrics['errors'])}):")
            for error in self.metrics['errors'][:10]:
                print(f"  • Task {error.get('task_id')}: {error.get('error', 'Unknown')[:80]}")
            if len(self.metrics['errors']) > 10:
                print(f"  ... และอีก {len(self.metrics['errors']) - 10} ข้อผิดพลาด")
            print()
        
        print("="*80)
        
        # Save to file
        if output_file:
            # Extract task IDs from results
            task_ids = []
            for result in self.results:
                task_id = None
                if isinstance(result, dict):
                    if result.get('request_result') and result['request_result'].get('api_task_id'):
                        task_id = result['request_result']['api_task_id']
                    elif result.get('poll_result') and result['poll_result'].get('api_task_id'):
                        task_id = result['poll_result']['api_task_id']
                if task_id:
                    task_ids.append(task_id)
            
            report_data = {
                'test_summary': {
                    'num_concurrent': self.num_concurrent,
                    'successful': len(successful_results),
                    'failed': len(failed_results),
                    'success_rate': len(successful_results) / self.num_concurrent * 100 if self.num_concurrent > 0 else 0,
                    'total_test_time': total_test_time
                },
                'task_ids': task_ids,  # Add task IDs for HTML monitor
                'metrics': {
                    'total_times': {
                        'mean': statistics.mean(self.metrics['total_times']) if self.metrics['total_times'] else None,
                        'median': statistics.median(self.metrics['total_times']) if self.metrics['total_times'] else None,
                        'min': min(self.metrics['total_times']) if self.metrics['total_times'] else None,
                        'max': max(self.metrics['total_times']) if self.metrics['total_times'] else None,
                    },
                    'processing_times': {
                        'mean': statistics.mean(self.metrics['processing_times']) if self.metrics['processing_times'] else None,
                        'median': statistics.median(self.metrics['processing_times']) if self.metrics['processing_times'] else None,
                        'min': min(self.metrics['processing_times']) if self.metrics['processing_times'] else None,
                        'max': max(self.metrics['processing_times']) if self.metrics['processing_times'] else None,
                    },
                    'queue_wait_times': {
                        'mean': statistics.mean(self.metrics['queue_wait_times']) if self.metrics['queue_wait_times'] else None,
                        'median': statistics.median(self.metrics['queue_wait_times']) if self.metrics['queue_wait_times'] else None,
                        'min': min(self.metrics['queue_wait_times']) if self.metrics['queue_wait_times'] else None,
                        'max': max(self.metrics['queue_wait_times']) if self.metrics['queue_wait_times'] else None,
                    }
                },
                'errors': self.metrics['errors'],
                'detailed_results': self.results
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, default=str, ensure_ascii=False)
            print(f"📄 รายงานบันทึกไว้ที่: {output_file}")
            
            # Create HTML monitor link
            if task_ids:
                monitor_url = f"static/concurrency-monitor.html?task_ids={','.join(task_ids)}&json_file={output_file}"
                print(f"🌐 เปิดหน้า Monitor ที่: {monitor_url}")
                print(f"   หรือเข้าไปที่: {self.api_url}/{monitor_url}")


async def main():
    parser = argparse.ArgumentParser(
        description='ทดสอบ 50 Concurrency สำหรับ Transcription Service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน:

  # ใช้ file_path (ไฟล์ที่อยู่ใน server)
  python test-50-concurrency.py \\
    --api-url http://80.15.7.37:8010 \\
    --file-path uploads/test-video-10min.mp4 \\
    --file-name "test-video-10min.mp4" \\
    --num-concurrent 50

  # ใช้ file_url (URL จาก FileService)
  python test-50-concurrency.py \\
    --api-url http://80.15.7.37:8010 \\
    --file-url "http://10.200.22.62/fileservice/api/files/abc123" \\
    --file-name "test-video-10min.mp4" \\
    --num-concurrent 50 \\
    --model-size medium
        """
    )
    
    parser.add_argument('--api-url', required=True, help='Transcription Service API URL (เช่น http://80.15.7.37:8010)')
    parser.add_argument('--num-concurrent', type=int, default=5, help='จำนวน concurrent requests (default: 5)')
    parser.add_argument('--file-path', help='Path ของไฟล์วิดีโอใน server (เช่น uploads/test.mp4)')
    parser.add_argument('--file-url', help='URL ของไฟล์วิดีโอ (เช่น http://...)')
    parser.add_argument('--file-name', help='ชื่อไฟล์ (default: test-video-10min.mp4)')
    parser.add_argument('--language', default='th', help='ภาษา (default: th)')
    parser.add_argument('--model-size', default='medium', help='ขนาดโมเดล (default: medium)')
    parser.add_argument('--poll-interval', type=int, default=5, help='ช่วงเวลาการตรวจสอบสถานะ (วินาที, default: 5)')
    parser.add_argument('--output', help='ไฟล์รายงาน JSON (default: concurrency_report_TIMESTAMP.json)')
    
    args = parser.parse_args()
    
    if not args.file_path and not args.file_url:
        parser.error("ต้องระบุ --file-path หรือ --file-url อย่างใดอย่างหนึ่ง")
    
    # แสดงข้อมูลก่อนเริ่มทดสอบ
    print("="*80)
    print("📋 Test Configuration")
    print("="*80)
    print(f"API URL: {args.api_url}")
    print(f"Concurrent Requests: {args.num_concurrent}")
    if args.file_path:
        print(f"File Path: {args.file_path}")
        print("⚠️  หมายเหตุ: file_path ต้องมีอยู่บน server")
        print("   ตรวจสอบไฟล์ด้วย: bash scripts/test/check-file-before-test.sh " + args.file_path)
    if args.file_url:
        print(f"File URL: {args.file_url}")
    print(f"Language: {args.language}")
    print(f"Model Size: {args.model_size}")
    print(f"Poll Interval: {args.poll_interval}s")
    print("="*80)
    print("")
    
    # Create test instance
    test = ConcurrencyTest(
        api_url=args.api_url,
        num_concurrent=args.num_concurrent,
        file_path=args.file_path,
        file_url=args.file_url,
        file_name=args.file_name,
        language=args.language,
        model_size=args.model_size,
        poll_interval=args.poll_interval
    )
    
    # Run test
    await test.run_concurrent_test()
    
    # Generate report
    output_file = args.output or f"concurrency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    test.generate_report(output_file)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  การทดสอบถูกยกเลิกโดยผู้ใช้")
    except Exception as e:
        print(f"❌ การทดสอบล้มเหลว: {e}")
        import traceback
        traceback.print_exc()

