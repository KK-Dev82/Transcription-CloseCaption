#!/usr/bin/env python3
"""
Quick Load Test Script สำหรับ Transcription Service

ทดสอบแบบเร็ว - ส่ง transcription requests ไปแล้วไม่รอผลลัพธ์
เหมาะสำหรับทดสอบว่า API รองรับ load ได้หรือไม่
"""

import asyncio
import aiohttp
import json
import time
import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class QuickLoadTest:
    def __init__(
        self,
        backend_url: str,
        num_users: int,
        video_file_path: str,
        auth_token: str = None,
        language: str = "th",
        model_size: str = "base"
    ):
        self.backend_url = backend_url.rstrip('/')
        self.num_users = num_users
        self.video_file_path = video_file_path
        self.auth_token = auth_token
        self.language = language
        self.model_size = model_size
        self.results: List[Dict] = []
    
    async def upload_and_start(self, session: aiohttp.ClientSession, user_id: int) -> Dict:
        """อัปโหลดและเริ่ม transcription (ไม่รอ completion)"""
        start_time = time.time()
        result = {
            'user_id': user_id,
            'upload_success': False,
            'start_success': False,
            'file_id': None,
            'job_id': None,
            'total_time': None,
            'error': None
        }
        
        try:
            # Step 1: Upload
            headers = {
                'X-File-Name': os.path.basename(self.video_file_path),
                'X-File-Size': str(Path(self.video_file_path).stat().st_size),
                'X-File-Type': 'video/mp4'
            }
            
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
            
            with open(self.video_file_path, 'rb') as f:
                async with session.post(
                    f'{self.backend_url}/api/transcription/upload/stream',
                    headers=headers,
                    data=f
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Upload failed: {response.status} - {error_text}")
                    
                    upload_result = await response.json()
                    result['upload_success'] = True
                    result['file_id'] = upload_result.get('fileId') or upload_result.get('FileId')
                    logger.info(f"User {user_id}: Upload successful")
            
            # Step 2: Start transcription
            headers = {'Content-Type': 'application/json'}
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
            
            payload = {
                'fileId': result['file_id'],
                'fileName': upload_result.get('fileName') or upload_result.get('FileName'),
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
                    raise Exception(f"Start failed: {response.status} - {error_text}")
                
                start_result = await response.json()
                result['start_success'] = True
                result['job_id'] = start_result.get('job_id')
                logger.info(f"User {user_id}: Transcription started - Job ID: {result['job_id']}")
            
            result['total_time'] = time.time() - start_time
            
        except Exception as e:
            result['error'] = str(e)
            result['total_time'] = time.time() - start_time
            logger.error(f"User {user_id}: Failed - {e}")
        
        return result
    
    async def run_test(self, max_concurrent: int = 10):
        """รันการทดสอบแบบ concurrent"""
        logger.info(f"🚀 Starting quick load test: {self.num_users} users, max {max_concurrent} concurrent")
        start_time = time.time()
        
        connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=max_concurrent)
        timeout = aiohttp.ClientTimeout(total=600)  # 10 minutes timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def run_with_semaphore(user_id: int):
                async with semaphore:
                    return await self.upload_and_start(session, user_id)
            
            tasks = [run_with_semaphore(i + 1) for i in range(self.num_users)]
            self.results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Summary
        successful = sum(1 for r in self.results if r.get('start_success'))
        failed = self.num_users - successful
        
        logger.info(f"✅ Test completed in {total_time:.2f}s")
        logger.info(f"   Successful: {successful}/{self.num_users}")
        logger.info(f"   Failed: {failed}/{self.num_users}")
        logger.info(f"   Success Rate: {successful/self.num_users*100:.2f}%")
        
        return {
            'total_time': total_time,
            'successful': successful,
            'failed': failed,
            'success_rate': successful / self.num_users * 100,
            'results': self.results
        }


async def main():
    parser = argparse.ArgumentParser(description='Quick Load Test for Transcription Service')
    parser.add_argument('--backend-url', required=True, help='Backend API URL')
    parser.add_argument('--num-users', type=int, default=100, help='Number of concurrent users')
    parser.add_argument('--video-file', required=True, help='Path to test video file')
    parser.add_argument('--auth-token', help='Authentication token')
    parser.add_argument('--language', default='th', help='Language for transcription')
    parser.add_argument('--model-size', default='base', help='Model size')
    parser.add_argument('--max-concurrent', type=int, default=10, help='Max concurrent requests')
    parser.add_argument('--output', help='Output JSON file path')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.video_file):
        logger.error(f"Video file not found: {args.video_file}")
        return
    
    test = QuickLoadTest(
        backend_url=args.backend_url,
        num_users=args.num_users,
        video_file_path=args.video_file,
        auth_token=args.auth_token,
        language=args.language,
        model_size=args.model_size
    )
    
    summary = await test.run_test(max_concurrent=args.max_concurrent)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"📄 Results saved to {args.output}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)

