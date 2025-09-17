#!/usr/bin/env python3
"""
สคริปต์ทดสอบ API Endpoints ทั้งหมด
สำหรับตรวจสอบว่า API พร้อมสำหรับ Staging หรือไม่
"""

import asyncio
import httpx
import json
import time
from pathlib import Path
import logging

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.test_results = {}
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def test_endpoint(self, name: str, method: str, endpoint: str, **kwargs):
        """ทดสอบ endpoint"""
        try:
            logger.info(f"Testing {name}: {method} {endpoint}")
            
            if method.upper() == "GET":
                response = await self.client.get(f"{self.base_url}{endpoint}", **kwargs)
            elif method.upper() == "POST":
                response = await self.client.post(f"{self.base_url}{endpoint}", **kwargs)
            elif method.upper() == "DELETE":
                response = await self.client.delete(f"{self.base_url}{endpoint}", **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            self.test_results[name] = {
                "status": "✅ PASS" if response.status_code < 400 else "❌ FAIL",
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "endpoint": f"{method} {endpoint}",
                "response_size": len(response.content) if response.content else 0
            }
            
            if response.status_code >= 400:
                logger.error(f"❌ {name} failed: {response.status_code} - {response.text[:200]}")
            else:
                logger.info(f"✅ {name} passed: {response.status_code}")
                
            return response
            
        except Exception as e:
            self.test_results[name] = {
                "status": "❌ ERROR",
                "error": str(e),
                "endpoint": f"{method} {endpoint}"
            }
            logger.error(f"❌ {name} error: {e}")
            return None
    
    async def test_basic_endpoints(self):
        """ทดสอบ endpoints พื้นฐาน"""
        logger.info("🔍 Testing Basic Endpoints...")
        
        # Root endpoint
        await self.test_endpoint("Root", "GET", "/")
        
        # Health check
        await self.test_endpoint("Health Check", "GET", "/health")
        
        # Stats
        await self.test_endpoint("System Stats", "GET", "/stats")
        
        # API Documentation
        await self.test_endpoint("API Docs", "GET", "/docs")
    
    async def test_upload_endpoints(self):
        """ทดสอบ upload endpoints"""
        logger.info("📤 Testing Upload Endpoints...")
        
        # สร้างไฟล์ทดสอบ
        test_file_path = Path("test_audio.wav")
        if not test_file_path.exists():
            # สร้างไฟล์ WAV ขนาดเล็กสำหรับทดสอบ
            import wave
            import numpy as np
            
            sample_rate = 16000
            duration = 1  # 1 วินาที
            t = np.linspace(0, duration, sample_rate * duration, False)
            audio_data = np.sin(440 * 2 * np.pi * t) * 0.3  # 440Hz sine wave
            
            with wave.open(str(test_file_path), 'w') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes((audio_data * 32767).astype(np.int16).tobytes())
        
        # ทดสอบ upload
        if test_file_path.exists():
            files = {"file": (test_file_path.name, test_file_path.read_bytes(), "audio/wav")}
            await self.test_endpoint("Upload File", "POST", "/upload", files=files)
    
    async def test_transcription_endpoints(self):
        """ทดสอบ transcription endpoints"""
        logger.info("🎤 Testing Transcription Endpoints...")
        
        # Get all transcriptions
        await self.test_endpoint("Get All Transcriptions", "GET", "/transcribe")
        
        # Search (ต้องมี query parameter)
        await self.test_endpoint("Global Search", "GET", "/transcribe/search/global?query=test")
        
        # List stored transcriptions
        await self.test_endpoint("List Stored Transcriptions", "GET", "/transcribe/list/stored")
    
    async def test_caption_endpoints(self):
        """ทดสอบ caption endpoints"""
        logger.info("📝 Testing Caption Endpoints...")
        
        # Get all captions
        await self.test_endpoint("Get All Captions", "GET", "/caption")
    
    async def test_video_endpoints(self):
        """ทดสอบ video endpoints"""
        logger.info("🎬 Testing Video Endpoints...")
        
        # Get all video tasks
        await self.test_endpoint("Get All Video Tasks", "GET", "/video/tasks")
        
        # Test video info (ใช้ไฟล์ที่ไม่มี - คาดหวัง 404)
        await self.test_endpoint("Get Video Info (404)", "GET", "/video/info/nonexistent.mp4")
    
    async def test_live_streaming_endpoints(self):
        """ทดสอบ live streaming endpoints"""
        logger.info("🔴 Testing Live Streaming Endpoints...")
        
        # Get active streams
        await self.test_endpoint("Get Active Streams", "GET", "/live/active")
        
        # Start live stream
        response = await self.test_endpoint("Start Live Stream", "POST", "/live/start?language=th&model_size=base")
        
        if response and response.status_code == 200:
            try:
                stream_data = response.json()
                stream_id = stream_data.get("stream_id")
                
                if stream_id:
                    # Test stream status
                    await self.test_endpoint("Get Stream Status", "GET", f"/live/status/{stream_id}")
                    
                    # Stop stream
                    await self.test_endpoint("Stop Live Stream", "POST", f"/live/stop/{stream_id}")
            except Exception as e:
                logger.error(f"Error testing live streaming: {e}")
    
    async def test_websocket_connectivity(self):
        """ทดสอบการเชื่อมต่อ WebSocket"""
        logger.info("🔌 Testing WebSocket Connectivity...")
        
        try:
            import websockets
            
            # ทดสอบ main WebSocket
            uri = self.base_url.replace("http", "ws") + "/ws"
            
            async with websockets.connect(uri, timeout=5) as websocket:
                # ส่ง ping
                await websocket.send(json.dumps({"type": "ping"}))
                
                # รอ response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                
                if data.get("type") == "pong":
                    self.test_results["WebSocket Main"] = {
                        "status": "✅ PASS",
                        "endpoint": "WS /ws",
                        "response": "Ping/Pong successful"
                    }
                else:
                    self.test_results["WebSocket Main"] = {
                        "status": "❌ FAIL",
                        "endpoint": "WS /ws",
                        "error": "Invalid ping/pong response"
                    }
                    
        except Exception as e:
            self.test_results["WebSocket Main"] = {
                "status": "❌ ERROR",
                "endpoint": "WS /ws",
                "error": str(e)
            }
    
    async def run_all_tests(self):
        """รันการทดสอบทั้งหมด"""
        logger.info("🚀 Starting API Tests...")
        start_time = time.time()
        
        # รันการทดสอบทั้งหมด
        await self.test_basic_endpoints()
        await self.test_upload_endpoints()
        await self.test_transcription_endpoints()
        await self.test_caption_endpoints()
        await self.test_video_endpoints()
        await self.test_live_streaming_endpoints()
        await self.test_websocket_connectivity()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # สรุปผล
        self.print_results(total_time)
        
        # ลบไฟล์ทดสอบ
        test_file = Path("test_audio.wav")
        if test_file.exists():
            test_file.unlink()
    
    def print_results(self, total_time):
        """แสดงผลการทดสอบ"""
        print("\n" + "="*80)
        print("📊 API TESTING RESULTS")
        print("="*80)
        
        passed = sum(1 for result in self.test_results.values() if result["status"] == "✅ PASS")
        failed = sum(1 for result in self.test_results.values() if result["status"] in ["❌ FAIL", "❌ ERROR"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        print(f"Total Time: {total_time:.2f}s")
        print()
        
        for name, result in self.test_results.items():
            status = result["status"]
            endpoint = result["endpoint"]
            
            if "response_time" in result:
                print(f"{status} {name:30} | {endpoint:25} | {result['response_time']:.3f}s")
            else:
                error = result.get("error", "Unknown error")
                print(f"{status} {name:30} | {endpoint:25} | {error}")
        
        print("\n" + "="*80)
        
        if failed == 0:
            print("🎉 ALL TESTS PASSED! API is ready for staging.")
        else:
            print(f"⚠️  {failed} tests failed. Please fix issues before staging.")
        
        print("="*80)

async def main():
    """เรียกใช้การทดสอบ"""
    async with APITester() as tester:
        await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
