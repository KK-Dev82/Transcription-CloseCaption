#!/usr/bin/env python3
"""
สคริปต์ทดสอบการส่ง audio chunks จาก RTMP stream ไปยัง /api/transcription/realtime/live-chunk
พร้อม WebSocket listener เพื่อรับ transcription results

Usage:
    python scripts/test_rtmp_to_live_chunk_with_websocket.py \
        --rtmp-url rtmp://143.198.77.135:1935/live/channel1 \
        --transcription-url http://localhost:8010 \
        --meeting-id test-meeting-001 \
        --duration 30
"""

import argparse
import subprocess
import requests
import time
import logging
import asyncio
import websockets
import json
from typing import Optional, Dict, List
import sys
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE_BYTES = 96000  # 3 seconds of audio at 16kHz mono PCM16
SAMPLE_RATE = 16000
CHANNELS = 1
AUDIO_FORMAT = "s16le"
CHUNK_DURATION = 3.0

# Store transcription results
transcription_results: List[Dict] = []


def extract_audio_chunk_from_rtmp_realtime(rtmp_url: str, duration: float) -> Optional[bytes]:
    """ใช้ FFmpeg อ่าน RTMP stream แบบ real-time และแยกเสียงเป็น chunk"""
    try:
        # อ่าน stream แบบ real-time (ไม่ใช้ -ss เพราะ RTMP stream ไม่สามารถ seek ได้)
        cmd = [
            'ffmpeg',
            '-i', rtmp_url,
            '-t', str(duration),  # อ่านแค่ duration วินาที
            '-ac', str(CHANNELS),
            '-ar', str(SAMPLE_RATE),
            '-acodec', 'pcm_s16le',
            '-f', 's16le',
            '-'
        ]
        
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=duration + 5
        )
        
        if process.returncode != 0:
            error_msg = process.stderr.decode('utf-8', errors='ignore')
            logger.error(f"❌ FFmpeg error: {error_msg}")
            return None
        
        audio_data = process.stdout
        logger.info(f"✅ Extracted {len(audio_data)} bytes of audio")
        return audio_data
        
    except subprocess.TimeoutExpired:
        logger.error(f"❌ FFmpeg timeout after {duration + 5} seconds")
        return None
    except Exception as e:
        logger.error(f"❌ Error extracting audio: {e}")
        return None


def send_chunk_to_transcription_service(
    transcription_url: str,
    meeting_id: str,
    chunk_index: int,
    start_time: float,
    duration: float,
    audio_data: bytes
) -> bool:
    """ส่ง audio chunk ไปยัง Transcription Service"""
    try:
        endpoint = f"{transcription_url}/api/transcription/realtime/live-chunk"
        
        headers = {
            "X-Meeting-Id": meeting_id,
            "X-Chunk-Index": str(chunk_index),
            "X-Start-Time": str(start_time),
            "X-Duration": str(duration),
            "X-Audio-Format": AUDIO_FORMAT,
            "X-Sample-Rate": str(SAMPLE_RATE),
            "X-Channels": str(CHANNELS),
            "Content-Type": "application/octet-stream"
        }
        
        logger.info(f"📤 Sending chunk {chunk_index} (start_time={start_time}s, size={len(audio_data)} bytes)")
        
        response = requests.post(
            endpoint,
            headers=headers,
            data=audio_data,
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 202:
            result = response.json()
            logger.info(f"✅ Chunk {chunk_index} accepted: {result.get('status', 'unknown')}")
            return True
        else:
            logger.error(f"❌ Failed to send chunk {chunk_index}: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error sending chunk: {e}")
        return False


async def websocket_listener(transcription_url: str, meeting_id: str, duration: float):
    """Listen to WebSocket เพื่อรับ transcription results"""
    try:
        # แปลง HTTP URL เป็น WebSocket URL
        ws_url = transcription_url.replace('http://', 'ws://').replace('https://', 'wss://')
        ws_endpoint = f"{ws_url}/api/ws/captions?meeting_id={meeting_id}"
        
        logger.info(f"🔌 Connecting to WebSocket: {ws_endpoint}")
        
        async with websockets.connect(ws_endpoint) as websocket:
            logger.info("✅ WebSocket connected")
            
            # Subscribe to meeting
            subscribe_msg = {
                "type": "subscribe",
                "meeting_id": meeting_id
            }
            await websocket.send(json.dumps(subscribe_msg))
            logger.info(f"📡 Subscribed to meeting_id: {meeting_id}")
            
            # Listen for messages
            timeout = duration + 30  # Wait for all chunks + buffer
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    
                    if data.get('type') == 'final':
                        chunk_index = data.get('chunk_index', -1)
                        text = data.get('text', '')
                        segments = data.get('segments', [])
                        
                        result = {
                            'chunk_index': chunk_index,
                            'text': text,
                            'segments': segments,
                            'timestamp': datetime.now().isoformat(),
                            'raw_data': data  # เก็บข้อมูลเต็มเพื่อ debug
                        }
                        transcription_results.append(result)
                        
                        logger.info("="*60)
                        logger.info(f"📝 Chunk {chunk_index} Transcription Result:")
                        logger.info(f"   Text: {text}")
                        if segments:
                            logger.info(f"   Segments: {len(segments)} segments")
                            for i, seg in enumerate(segments[:3]):  # แสดง 3 segments แรก
                                seg_text = seg.get('text', '')
                                t0_ms = seg.get('t0_ms', 0)
                                t1_ms = seg.get('t1_ms', 0)
                                logger.info(f"      [{i+1}] [{t0_ms}ms-{t1_ms}ms] {seg_text[:50]}...")
                        logger.info("="*60)
                        
                    elif data.get('type') == 'pong':
                        logger.debug("🏓 Received pong")
                    elif data.get('type') == 'sync':
                        logger.info(f"🔄 Received sync event: {data.get('meeting_id', 'unknown')}")
                    elif data.get('type') == 'status':
                        logger.info(f"📊 Received status event: {data.get('status', 'unknown')}")
                    elif data.get('type') == 'heartbeat':
                        logger.debug("💓 Received heartbeat")
                    else:
                        logger.info(f"📨 Received message: type={data.get('type', 'unknown')}, data={json.dumps(data, ensure_ascii=False)[:200]}")
                        
                except asyncio.TimeoutError:
                    # No message received, continue waiting
                    continue
                except Exception as e:
                    logger.error(f"❌ Error receiving message: {e}")
                    break
                    
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")


async def test_rtmp_to_live_chunk_async(
    rtmp_url: str,
    transcription_url: str,
    meeting_id: str,
    duration: float
):
    """ทดสอบการส่ง audio chunks พร้อม WebSocket listener"""
    
    # เริ่ม WebSocket listener ใน background
    ws_task = asyncio.create_task(
        websocket_listener(transcription_url, meeting_id, duration)
    )
    
    # รอสักครู่ให้ WebSocket เชื่อมต่อ
    await asyncio.sleep(2)
    
    # คำนวณจำนวน chunks
    num_chunks = int(duration / CHUNK_DURATION)
    logger.info(f"\n🚀 Starting test: {num_chunks} chunks (duration: {duration}s)")
    
    # เริ่มจับเวลา
    test_start_time = time.time()
    chunk_times = []
    
    success_count = 0
    error_count = 0
    
    for chunk_index in range(num_chunks):
        start_time = chunk_index * CHUNK_DURATION
        chunk_start_time = time.time()
        
        logger.info(f"\n📦 Processing chunk {chunk_index + 1}/{num_chunks} (start_time={start_time}s)")
        
        # แยกเสียงจาก RTMP stream แบบ real-time (run in executor เพื่อไม่ block)
        # หมายเหตุ: RTMP stream ไม่สามารถ seek ได้ ต้องอ่านแบบ real-time
        loop = asyncio.get_event_loop()
        audio_data = await loop.run_in_executor(
            None,
            extract_audio_chunk_from_rtmp_realtime,
            rtmp_url,
            CHUNK_DURATION
        )
        
        if audio_data is None:
            logger.error(f"❌ Failed to extract audio for chunk {chunk_index}")
            error_count += 1
            continue
        
        # ส่งไปยัง Transcription Service
        success = await loop.run_in_executor(
            None,
            send_chunk_to_transcription_service,
            transcription_url,
            meeting_id,
            chunk_index,
            start_time,
            CHUNK_DURATION,
            audio_data
        )
        
        chunk_end_time = time.time()
        chunk_duration = chunk_end_time - chunk_start_time
        chunk_times.append(chunk_duration)
        
        if success:
            success_count += 1
            logger.info(f"   ⏱️  Chunk {chunk_index} took {chunk_duration:.2f}s")
        else:
            error_count += 1
        
        # รอก่อนส่ง chunk ถัดไป
        if chunk_index < num_chunks - 1:
            await asyncio.sleep(0.5)
    
    # จับเวลาสิ้นสุดการส่ง chunks
    chunks_end_time = time.time()
    chunks_total_time = chunks_end_time - test_start_time
    
    # รอให้ WebSocket รับผลลัพธ์ทั้งหมด
    logger.info("\n⏳ Waiting for transcription results...")
    wait_start_time = time.time()
    await asyncio.sleep(30)  # รอ 30 วินาทีให้ transcription เสร็จ (เพิ่มเวลาเพราะอาจใช้เวลานานขึ้น)
    wait_end_time = time.time()
    wait_duration = wait_end_time - wait_start_time
    
    # Cancel WebSocket task
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass
    
    # จับเวลาสิ้นสุดทั้งหมด
    test_end_time = time.time()
    test_total_time = test_end_time - test_start_time
    
    # สรุปผล
    logger.info("\n" + "="*60)
    logger.info("📊 Test Summary")
    logger.info(f"   Total chunks sent: {num_chunks}")
    logger.info(f"   ✅ Success: {success_count}")
    logger.info(f"   ❌ Errors: {error_count}")
    logger.info(f"   📝 Transcription results received: {len(transcription_results)}")
    logger.info("")
    logger.info("⏱️  Timing:")
    if chunk_times:
        avg_chunk_time = sum(chunk_times) / len(chunk_times)
        min_chunk_time = min(chunk_times)
        max_chunk_time = max(chunk_times)
        logger.info(f"   Chunk processing:")
        logger.info(f"      - Average: {avg_chunk_time:.2f}s")
        logger.info(f"      - Min: {min_chunk_time:.2f}s")
        logger.info(f"      - Max: {max_chunk_time:.2f}s")
    logger.info(f"   Total chunks send time: {chunks_total_time:.2f}s")
    logger.info(f"   Wait for results time: {wait_duration:.2f}s")
    logger.info(f"   Total test time: {test_total_time:.2f}s")
    logger.info("="*60)
    
    # แสดง transcription results
    if transcription_results:
        logger.info("\n📝 Transcription Results (ทุก 3 วินาที):")
        logger.info("="*60)
        for i, result in enumerate(transcription_results, 1):
            chunk_idx = result.get('chunk_index', -1)
            text = result.get('text', '')
            timestamp = result.get('timestamp', '')
            
            logger.info(f"\n[{i}] Chunk {chunk_idx} ({timestamp}):")
            logger.info(f"    Text: {text}")
            
            segments = result.get('segments', [])
            if segments:
                logger.info(f"    Segments ({len(segments)}):")
                for j, seg in enumerate(segments, 1):
                    seg_text = seg.get('text', '')
                    t0_ms = seg.get('t0_ms', 0)
                    t1_ms = seg.get('t1_ms', 0)
                    logger.info(f"      [{j}] [{t0_ms}ms-{t1_ms}ms] {seg_text}")
        logger.info("="*60)
    else:
        logger.warning("⚠️ No transcription results received. Check WebSocket connection and logs.")


def main():
    parser = argparse.ArgumentParser(
        description="Test RTMP stream to /api/transcription/realtime/live-chunk with WebSocket listener"
    )
    parser.add_argument(
        "--rtmp-url",
        type=str,
        default="rtmp://143.198.77.135:1935/live/channel1",
        help="RTMP stream URL"
    )
    parser.add_argument(
        "--transcription-url",
        type=str,
        default="http://localhost:8010",
        help="Transcription Service base URL"
    )
    parser.add_argument(
        "--meeting-id",
        type=str,
        default="test-live-chunk-fixed-room",
        help="Meeting ID (ใช้ fixed meeting_id เพื่อทดสอบ)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Test duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # ตรวจสอบ dependencies
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ FFmpeg not found. Please install FFmpeg first.")
        sys.exit(1)
    
    try:
        import websockets
    except ImportError:
        logger.error("❌ websockets library not found. Please install: pip install websockets")
        sys.exit(1)
    
    # ตรวจสอบ Transcription Service
    try:
        response = requests.get(f"{args.transcription_url}/health", timeout=5)
        if response.status_code != 200:
            logger.warning(f"⚠️ Transcription Service health check failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ Cannot connect to Transcription Service: {e}")
        logger.warning("   Continuing anyway...")
    
    # เริ่มทดสอบ
    asyncio.run(test_rtmp_to_live_chunk_async(
        rtmp_url=args.rtmp_url,
        transcription_url=args.transcription_url,
        meeting_id=args.meeting_id,
        duration=args.duration
    ))


if __name__ == "__main__":
    main()
