#!/usr/bin/env python3
"""
Test Script สำหรับ Real-time Close Caption System
ทดสอบ API endpoints และ WebSocket connections
"""

import asyncio
import json
import websockets
import requests
import time
from typing import Dict, Any

# Configuration
API_BASE = "http://localhost:8001"
WS_BASE = "ws://localhost:8001"
USER_ID = "test_user_123"

class RealtimeCaptionTester:
    def __init__(self):
        self.session_id = None
        self.chunks_received = []
        self.websocket = None
        
    async def test_api_endpoints(self):
        """ทดสอบ API endpoints"""
        print("🧪 Testing API Endpoints...")
        
        # 1. Test health check
        try:
            response = requests.get(f"{API_BASE}/caption/realtime/health")
            print(f"✅ Health check: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"❌ Health check failed: {e}")
        
        # 2. Test stats
        try:
            response = requests.get(f"{API_BASE}/caption/realtime/stats")
            print(f"✅ Stats: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"❌ Stats failed: {e}")
    
    async def test_websocket_connection(self):
        """ทดสอบ WebSocket connection"""
        print("\n🔌 Testing WebSocket Connection...")
        
        try:
            ws_url = f"{WS_BASE}/ws/caption/{USER_ID}"
            self.websocket = await websockets.connect(ws_url)
            print(f"✅ WebSocket connected: {ws_url}")
            
            # Test ping/pong
            await self.websocket.send(json.dumps({"type": "ping", "timestamp": time.time()}))
            response = await self.websocket.recv()
            print(f"✅ Ping/Pong test: {json.loads(response)}")
            
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
    
    async def test_realtime_caption_session(self):
        """ทดสอบ real-time caption session"""
        print("\n🎬 Testing Real-time Caption Session...")
        
        # 1. Start session
        try:
            payload = {
                "user_id": USER_ID,
                "file_path": "uploads/test_video.mp4",  # ใช้ไฟล์ทดสอบที่มีอยู่
                "language": "th",
                "model_size": "base",
                "chunk_duration": 10,
                "delay_seconds": 0.0
            }
            
            response = requests.post(f"{API_BASE}/caption/realtime/start", json=payload)
            if response.status_code == 200:
                data = response.json()
                self.session_id = data["session_id"]
                print(f"✅ Session started: {self.session_id}")
                print(f"   WebSocket URL: {data['websocket_url']}")
            else:
                print(f"❌ Failed to start session: {response.status_code}")
                print(f"   Error: {response.text}")
                return
                
        except Exception as e:
            print(f"❌ Session start failed: {e}")
            return
        
        # 2. Subscribe to WebSocket
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    "type": "subscribe",
                    "session_id": self.session_id
                }))
                print(f"✅ Subscribed to session: {self.session_id}")
            except Exception as e:
                print(f"❌ Subscription failed: {e}")
        
        # 3. Listen for messages
        print("👂 Listening for real-time messages...")
        try:
            # Listen for 30 seconds
            timeout = 30
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    await self.handle_websocket_message(data)
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"❌ Error receiving message: {e}")
                    break
            
            print(f"⏰ Timeout reached ({timeout}s)")
            
        except Exception as e:
            print(f"❌ Message listening failed: {e}")
        
        # 4. Test delay update
        if self.session_id:
            try:
                delay_payload = {"delay_seconds": 5.0}
                response = requests.put(
                    f"{API_BASE}/caption/realtime/delay/{self.session_id}",
                    json=delay_payload
                )
                if response.status_code == 200:
                    print(f"✅ Delay updated: {response.json()}")
                else:
                    print(f"❌ Delay update failed: {response.status_code}")
            except Exception as e:
                print(f"❌ Delay update error: {e}")
        
        # 5. Stop session
        if self.session_id:
            try:
                response = requests.post(f"{API_BASE}/caption/realtime/stop/{self.session_id}")
                if response.status_code == 200:
                    print(f"✅ Session stopped: {response.json()}")
                else:
                    print(f"❌ Session stop failed: {response.status_code}")
            except Exception as e:
                print(f"❌ Session stop error: {e}")
    
    async def handle_websocket_message(self, data: Dict[str, Any]):
        """จัดการข้อความจาก WebSocket"""
        message_type = data.get("type")
        
        if message_type == "caption.started":
            print(f"🎬 Caption started: {data}")
            
        elif message_type == "caption.chunk":
            chunk_data = data.get("chunk_data", {})
            self.chunks_received.append(chunk_data)
            print(f"📝 Chunk {data.get('chunk_index', '?')}: {chunk_data.get('text', '')[:50]}...")
            
        elif message_type == "caption.progress":
            progress = data.get("progress", 0)
            print(f"📊 Progress: {progress}%")
            
        elif message_type == "caption.completed":
            print(f"✅ Caption completed: {data}")
            
        elif message_type == "caption.error":
            print(f"❌ Caption error: {data}")
            
        elif message_type == "caption.delay_updated":
            print(f"⏱️ Delay updated: {data}")
            
        else:
            print(f"📨 Message: {message_type} - {data}")
    
    async def test_session_management(self):
        """ทดสอบการจัดการ sessions"""
        print("\n📋 Testing Session Management...")
        
        try:
            # Get user sessions
            response = requests.get(f"{API_BASE}/caption/realtime/user/{USER_ID}/sessions")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ User sessions: {data}")
            else:
                print(f"❌ Failed to get user sessions: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Session management error: {e}")
    
    async def cleanup(self):
        """ทำความสะอาด"""
        if self.websocket:
            await self.websocket.close()
            print("🧹 WebSocket connection closed")
    
    async def run_all_tests(self):
        """รันการทดสอบทั้งหมด"""
        print("🚀 Starting Real-time Caption System Tests")
        print("=" * 50)
        
        try:
            # Test API endpoints
            await self.test_api_endpoints()
            
            # Test WebSocket connection
            await self.test_websocket_connection()
            
            # Test real-time caption session
            await self.test_realtime_caption_session()
            
            # Test session management
            await self.test_session_management()
            
            # Summary
            print("\n📊 Test Summary")
            print("=" * 50)
            print(f"✅ Chunks received: {len(self.chunks_received)}")
            print(f"✅ Session ID: {self.session_id}")
            
            if self.chunks_received:
                print("\n📝 Sample chunks:")
                for i, chunk in enumerate(self.chunks_received[:3]):
                    print(f"   {i+1}. {chunk.get('text', '')[:100]}...")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
        
        finally:
            await self.cleanup()

async def main():
    """Main function"""
    tester = RealtimeCaptionTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    print("🎬 Real-time Close Caption System Test")
    print("Make sure the API server is running on http://localhost:8001")
    print("Press Ctrl+C to cancel")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Test cancelled by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
