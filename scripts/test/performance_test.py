#!/usr/bin/env python3
"""
Performance Testing Script สำหรับ Transcription Service

ทดสอบการรองรับ 80-120 users พร้อมกัน กับวีดิโอความยาว 1 ชั่วโมง
"""

import asyncio
import aiohttp
import json
import time
import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import statistics
from collections import defaultdict
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TranscriptionPerformanceTest:
    def __init__(
        self,
        backend_url: str,
        num_users: int = 100,
        video_file_path: Optional[str] = None,
        auth_token: Optional[str] = None,
        language: str = "th",
        model_size: str = "base"
    ):
        self.backend_url = backend_url.rstrip('/')
        self.num_users = num_users
        self.video_file_path = video_file_path
        self.auth_token = auth_token
        self.language = language
        self.model_size = model_size
        
        # Results storage
        self.results: List[Dict] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        # Metrics
        self.metrics = {
            'upload_times': [],
            'start_times': [],
            'total_times': [],
            'queue_wait_times': [],
            'processing_times': [],
            'errors': []
        }
    
    async def upload_video(
        self,
        session: aiohttp.ClientSession,
        user_id: int,
        video_file_path: str
    ) -> Dict:
        """อัปโหลดวีดิโอไปยัง Backend"""
        upload_start = time.time()
        
        try:
            headers = {
                'X-File-Name': os.path.basename(video_file_path),
                'X-File-Size': str(Path(video_file_path).stat().st_size),
                'X-File-Type': 'video/mp4'
            }
            
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
            
            with open(video_file_path, 'rb') as f:
                async with session.post(
                    f'{self.backend_url}/api/transcription/upload/stream',
                    headers=headers,
                    data=f
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Upload failed: {response.status} - {error_text}")
                    
                    result = await response.json()
                    upload_time = time.time() - upload_start
                    
                    logger.info(f"User {user_id}: Upload completed in {upload_time:.2f}s")
                    
                    return {
                        'user_id': user_id,
                        'file_id': result.get('fileId') or result.get('FileId'),
                        'file_name': result.get('fileName') or result.get('FileName'),
                        'upload_time': upload_time,
                        'success': True
                    }
        except Exception as e:
            upload_time = time.time() - upload_start
            logger.error(f"User {user_id}: Upload failed - {e}")
            return {
                'user_id': user_id,
                'upload_time': upload_time,
                'success': False,
                'error': str(e)
            }
    
    async def start_transcription(
        self,
        session: aiohttp.ClientSession,
        user_id: int,
        file_id: str,
        file_name: str
    ) -> Dict:
        """เริ่มการ transcription"""
        start_transcription_time = time.time()
        
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
            
            payload = {
                'fileId': file_id,
                'fileName': file_name,
                'language': self.language,
                'modelSize': self.model_size
            }
            
            async with session.post(
                f'{self.backend_url}/api/transcription/start',
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Start transcription failed: {response.status} - {error_text}")
                
                result = await response.json()
                start_time = time.time() - start_transcription_time
                
                logger.info(f"User {user_id}: Transcription started - Job ID: {result.get('job_id')}")
                
                return {
                    'user_id': user_id,
                    'job_id': result.get('job_id'),
                    'status': result.get('status', 'queued'),
                    'start_time': start_time,
                    'success': True,
                    'started_at': time.time()
                }
        except Exception as e:
            start_time = time.time() - start_transcription_time
            logger.error(f"User {user_id}: Start transcription failed - {e}")
            return {
                'user_id': user_id,
                'start_time': start_time,
                'success': False,
                'error': str(e)
            }
    
    async def check_status(
        self,
        session: aiohttp.ClientSession,
        user_id: int,
        job_id: int
    ) -> Dict:
        """ตรวจสอบสถานะของ transcription job"""
        try:
            headers = {}
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
            
            async with session.get(
                f'{self.backend_url}/api/transcription/{job_id}',
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        'job_id': job_id,
                        'status': result.get('status'),
                        'progress': result.get('progress', 0),
                        'started_at': result.get('startedAt'),
                        'completed_at': result.get('completedAt'),
                        'duration_seconds': result.get('durationSeconds')
                    }
                else:
                    return {'status': 'error', 'error': f'HTTP {response.status}'}
        except Exception as e:
            logger.error(f"User {user_id}: Status check failed - {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def wait_for_completion(
        self,
        session: aiohttp.ClientSession,
        user_id: int,
        job_id: int,
        max_wait_time: int = 3600,  # 1 hour
        check_interval: int = 10  # 10 seconds
    ) -> Dict:
        """รอให้ transcription เสร็จสิ้น"""
        start_wait = time.time()
        last_status = None
        
        while True:
            elapsed = time.time() - start_wait
            
            if elapsed > max_wait_time:
                return {
                    'job_id': job_id,
                    'status': 'timeout',
                    'elapsed_time': elapsed,
                    'last_status': last_status
                }
            
            status_info = await self.check_status(session, user_id, job_id)
            current_status = status_info.get('status')
            
            if current_status != last_status:
                logger.info(
                    f"User {user_id}: Job {job_id} - Status: {current_status}, "
                    f"Progress: {status_info.get('progress', 0)}%, "
                    f"Elapsed: {elapsed:.1f}s"
                )
                last_status = current_status
            
            if current_status == 'completed':
                completed_at = status_info.get('completed_at')
                started_at = status_info.get('started_at')
                
                total_time = elapsed
                processing_time = status_info.get('duration_seconds')
                
                if started_at and completed_at:
                    try:
                        from dateutil import parser
                        start_dt = parser.parse(started_at)
                        complete_dt = parser.parse(completed_at)
                        processing_time = (complete_dt - start_dt).total_seconds()
                    except:
                        pass
                
                return {
                    'job_id': job_id,
                    'status': 'completed',
                    'total_time': total_time,
                    'processing_time': processing_time,
                    'progress': 100,
                    'elapsed_time': elapsed
                }
            elif current_status in ['failed', 'cancelled', 'error']:
                return {
                    'job_id': job_id,
                    'status': current_status,
                    'elapsed_time': elapsed,
                    'error': status_info.get('error')
                }
            
            await asyncio.sleep(check_interval)
    
    async def run_user_test(self, session: aiohttp.ClientSession, user_id: int) -> Dict:
        """รันการทดสอบสำหรับ 1 user"""
        user_start = time.time()
        result = {
            'user_id': user_id,
            'upload_result': None,
            'start_result': None,
            'completion_result': None,
            'total_time': None,
            'success': False,
            'errors': []
        }
        
        try:
            # Step 1: Upload video
            if not self.video_file_path:
                raise Exception("Video file path not provided")
            
            upload_result = await self.upload_video(session, user_id, self.video_file_path)
            result['upload_result'] = upload_result
            
            if not upload_result.get('success'):
                result['errors'].append(f"Upload failed: {upload_result.get('error')}")
                return result
            
            # Step 2: Start transcription
            file_id = upload_result['file_id']
            file_name = upload_result['file_name']
            
            start_result = await self.start_transcription(session, user_id, file_id, file_name)
            result['start_result'] = start_result
            
            if not start_result.get('success'):
                result['errors'].append(f"Start transcription failed: {start_result.get('error')}")
                return result
            
            job_id = start_result['job_id']
            queue_start_time = start_result['started_at']
            
            # Step 3: Wait for completion
            completion_result = await self.wait_for_completion(session, user_id, job_id)
            result['completion_result'] = completion_result
            
            # Calculate metrics
            total_time = time.time() - user_start
            result['total_time'] = total_time
            
            if completion_result.get('status') == 'completed':
                result['success'] = True
                
                # Record metrics
                self.metrics['upload_times'].append(upload_result['upload_time'])
                self.metrics['start_times'].append(start_result['start_time'])
                self.metrics['total_times'].append(total_time)
                
                processing_time = completion_result.get('processing_time') or completion_result.get('elapsed_time', 0)
                self.metrics['processing_times'].append(processing_time)
                
                if queue_start_time and completion_result.get('processing_time'):
                    queue_wait_time = (completion_result.get('processing_time', 0) - (time.time() - queue_start_time))
                    if queue_wait_time > 0:
                        self.metrics['queue_wait_times'].append(queue_wait_time)
                
                logger.info(
                    f"✅ User {user_id}: Completed in {total_time:.2f}s "
                    f"(Processing: {processing_time:.2f}s)"
                )
            else:
                error_msg = completion_result.get('error', f"Status: {completion_result.get('status')}")
                result['errors'].append(f"Completion failed: {error_msg}")
                self.metrics['errors'].append({
                    'user_id': user_id,
                    'error': error_msg
                })
                logger.error(f"❌ User {user_id}: Failed - {error_msg}")
        
        except Exception as e:
            result['errors'].append(str(e))
            self.metrics['errors'].append({
                'user_id': user_id,
                'error': str(e)
            })
            logger.error(f"❌ User {user_id}: Exception - {e}")
        
        return result
    
    async def run_concurrent_test(self, max_concurrent: int = 10):
        """รันการทดสอบพร้อมกันหลาย users"""
        logger.info(f"🚀 Starting performance test: {self.num_users} users, max {max_concurrent} concurrent")
        self.start_time = time.time()
        
        connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=max_concurrent)
        timeout = aiohttp.ClientTimeout(total=7200)  # 2 hours timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def run_with_semaphore(user_id: int):
                async with semaphore:
                    return await self.run_user_test(session, user_id)
            
            # Create tasks for all users
            tasks = [run_with_semaphore(i + 1) for i in range(self.num_users)]
            
            # Run all tasks concurrently
            self.results = await asyncio.gather(*tasks)
        
        self.end_time = time.time()
        
        logger.info(f"✅ Test completed in {self.end_time - self.start_time:.2f}s")
    
    def generate_report(self, output_file: Optional[str] = None):
        """สร้างรายงานผลการทดสอบ"""
        if not self.results:
            logger.warning("No results to report")
            return
        
        total_time = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        # Calculate statistics
        successful_results = [r for r in self.results if r.get('success')]
        failed_results = [r for r in self.results if not r.get('success')]
        
        report = {
            'test_summary': {
                'total_users': self.num_users,
                'successful': len(successful_results),
                'failed': len(failed_results),
                'success_rate': len(successful_results) / self.num_users * 100 if self.num_users > 0 else 0,
                'total_test_time': total_time
            },
            'metrics': {}
        }
        
        # Upload times
        if self.metrics['upload_times']:
            report['metrics']['upload'] = {
                'mean': statistics.mean(self.metrics['upload_times']),
                'median': statistics.median(self.metrics['upload_times']),
                'min': min(self.metrics['upload_times']),
                'max': max(self.metrics['upload_times']),
                'stddev': statistics.stdev(self.metrics['upload_times']) if len(self.metrics['upload_times']) > 1 else 0
            }
        
        # Start times
        if self.metrics['start_times']:
            report['metrics']['start_transcription'] = {
                'mean': statistics.mean(self.metrics['start_times']),
                'median': statistics.median(self.metrics['start_times']),
                'min': min(self.metrics['start_times']),
                'max': max(self.metrics['start_times']),
                'stddev': statistics.stdev(self.metrics['start_times']) if len(self.metrics['start_times']) > 1 else 0
            }
        
        # Total times
        if self.metrics['total_times']:
            report['metrics']['total_processing'] = {
                'mean': statistics.mean(self.metrics['total_times']),
                'median': statistics.median(self.metrics['total_times']),
                'min': min(self.metrics['total_times']),
                'max': max(self.metrics['total_times']),
                'stddev': statistics.stdev(self.metrics['total_times']) if len(self.metrics['total_times']) > 1 else 0,
                'p95': self._percentile(self.metrics['total_times'], 95),
                'p99': self._percentile(self.metrics['total_times'], 99)
            }
        
        # Processing times
        if self.metrics['processing_times']:
            report['metrics']['transcription_processing'] = {
                'mean': statistics.mean(self.metrics['processing_times']),
                'median': statistics.median(self.metrics['processing_times']),
                'min': min(self.metrics['processing_times']),
                'max': max(self.metrics['processing_times']),
                'stddev': statistics.stdev(self.metrics['processing_times']) if len(self.metrics['processing_times']) > 1 else 0
            }
        
        # Queue wait times
        if self.metrics['queue_wait_times']:
            report['metrics']['queue_wait'] = {
                'mean': statistics.mean(self.metrics['queue_wait_times']),
                'median': statistics.median(self.metrics['queue_wait_times']),
                'min': min(self.metrics['queue_wait_times']),
                'max': max(self.metrics['queue_wait_times'])
            }
        
        # Errors
        report['errors'] = self.metrics['errors']
        
        # Throughput
        if total_time > 0:
            report['throughput'] = {
                'jobs_per_minute': len(successful_results) / (total_time / 60),
                'jobs_per_hour': len(successful_results) / (total_time / 3600)
            }
        
        # Print report
        print("\n" + "="*80)
        print("📊 PERFORMANCE TEST REPORT")
        print("="*80)
        print(f"\nTest Summary:")
        print(f"  Total Users: {report['test_summary']['total_users']}")
        print(f"  Successful: {report['test_summary']['successful']}")
        print(f"  Failed: {report['test_summary']['failed']}")
        print(f"  Success Rate: {report['test_summary']['success_rate']:.2f}%")
        print(f"  Total Test Time: {total_time/60:.2f} minutes")
        
        if 'throughput' in report:
            print(f"\nThroughput:")
            print(f"  Jobs per Minute: {report['throughput']['jobs_per_minute']:.2f}")
            print(f"  Jobs per Hour: {report['throughput']['jobs_per_hour']:.2f}")
        
        if report['metrics']:
            print(f"\nMetrics:")
            for metric_name, metric_data in report['metrics'].items():
                print(f"  {metric_name.replace('_', ' ').title()}:")
                for key, value in metric_data.items():
                    if isinstance(value, float):
                        print(f"    {key}: {value:.2f}s" if 'time' in key.lower() or 'wait' in key.lower() else f"    {key}: {value:.2f}")
                    else:
                        print(f"    {key}: {value}")
        
        if report['errors']:
            print(f"\nErrors ({len(report['errors'])}):")
            for error in report['errors'][:10]:  # Show first 10 errors
                print(f"  User {error.get('user_id')}: {error.get('error')}")
            if len(report['errors']) > 10:
                print(f"  ... and {len(report['errors']) - 10} more errors")
        
        print("="*80 + "\n")
        
        # Save to file
        if output_file:
            with open(output_file, 'w') as f:
                json.dump({
                    'report': report,
                    'detailed_results': self.results
                }, f, indent=2, default=str)
            logger.info(f"📄 Report saved to {output_file}")
        
        return report
    
    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """คำนวณ percentile"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


async def main():
    parser = argparse.ArgumentParser(description='Transcription Service Performance Test')
    parser.add_argument('--backend-url', required=True, help='Backend API URL')
    parser.add_argument('--num-users', type=int, default=100, help='Number of concurrent users (default: 100)')
    parser.add_argument('--video-file', required=True, help='Path to test video file')
    parser.add_argument('--auth-token', help='Authentication token (optional)')
    parser.add_argument('--language', default='th', help='Language for transcription (default: th)')
    parser.add_argument('--model-size', default='base', help='Model size (default: base)')
    parser.add_argument('--max-concurrent', type=int, default=10, help='Max concurrent requests (default: 10)')
    parser.add_argument('--output', help='Output JSON report file path')
    
    args = parser.parse_args()
    
    # Check if video file exists
    if not os.path.exists(args.video_file):
        logger.error(f"Video file not found: {args.video_file}")
        return
    
    # Create test instance
    test = TranscriptionPerformanceTest(
        backend_url=args.backend_url,
        num_users=args.num_users,
        video_file_path=args.video_file,
        auth_token=args.auth_token,
        language=args.language,
        model_size=args.model_size
    )
    
    # Run test
    await test.run_concurrent_test(max_concurrent=args.max_concurrent)
    
    # Generate report
    output_file = args.output or f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    test.generate_report(output_file)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)

