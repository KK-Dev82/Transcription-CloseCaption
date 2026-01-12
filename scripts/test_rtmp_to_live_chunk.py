#!/usr/bin/env python3
"""
สคริปต์ทดสอบการส่ง audio chunks จาก RTMP stream ไปยัง /api/transcription/realtime/live-chunk

Flow:
RTMP Stream → FFmpeg (extract audio) → Chunks (96,000 bytes = 3 seconds) → POST /api/transcription/realtime/live-chunk

Usage:
    python scripts/test_rtmp_to_live_chunk.py \
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
from typing import Optional
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE_BYTES = 96000  # 3 seconds of audio at 16kHz mono PCM16 (16kHz * 2 bytes * 3 seconds)
SAMPLE_RATE = 16000
CHANNELS = 1
AUDIO_FORMAT = "s16le"  # PCM16 little-endian
CHUNK_DURATION = 3.0  # seconds


def extract_audio_chunk_from_rtmp(rtmp_url: str, start_time: float, duration: float) -> Optional[bytes]:
    """
    ใช้ FFmpeg แยกเสียงจาก RTMP stream เป็น chunk
    
    Args:
        rtmp_url: RTMP stream URL
        start_time: เวลาเริ่มต้น (วินาที)
        duration: ระยะเวลา (วินาที)
    
    Returns:
        bytes: Raw PCM16 audio data (หรือ None ถ้า error)
    """
    try:
        # FFmpeg command: อ่าน RTMP stream → แยกเสียง → PCM16 16kHz mono
        cmd = [
            'ffmpeg',
            '-i', rtmp_url,
            '-ss', str(start_time),  # Seek to start time
            '-t', str(duration),  # Duration
            '-ac', str(CHANNELS),  # Mono
            '-ar', str(SAMPLE_RATE),  # 16kHz
            '-acodec', 'pcm_s16le',  # PCM16 little-endian
            '-f', 's16le',  # Raw PCM format
            '-'  # Output to stdout
        ]
        
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        # Run FFmpeg
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=duration + 5  # Timeout = duration + 5 seconds
        )
        
        if process.returncode != 0:
            error_msg = process.stderr.decode('utf-8', errors='ignore')
            logger.error(f"❌ FFmpeg error: {error_msg}")
            return None
        
        audio_data = process.stdout
        logger.info(f"✅ Extracted {len(audio_data)} bytes of audio (expected: {CHUNK_SIZE_BYTES})")
        
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
    """
    ส่ง audio chunk ไปยัง Transcription Service
    
    Args:
        transcription_url: Base URL ของ Transcription Service
        meeting_id: Meeting ID
        chunk_index: Chunk index
        start_time: Start time (seconds)
        duration: Duration (seconds)
        audio_data: Raw PCM16 audio data
    
    Returns:
        bool: True ถ้าส่งสำเร็จ
    """
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
        
        logger.info(
            f"📤 Sending chunk {chunk_index} to {endpoint} "
            f"(MeetingId={meeting_id}, StartTime={start_time}s, Duration={duration}s, Size={len(audio_data)} bytes)"
        )
        
        response = requests.post(
            endpoint,
            headers=headers,
            data=audio_data,
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 202:
            result = response.json()
            logger.info(f"✅ Chunk {chunk_index} sent successfully: {result.get('status', 'unknown')}")
            logger.debug(f"Response: {result}")
            return True
        else:
            logger.error(f"❌ Failed to send chunk {chunk_index}: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Request error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending chunk: {e}")
        return False


def test_rtmp_to_live_chunk(
    rtmp_url: str,
    transcription_url: str,
    meeting_id: str,
    duration: float = 30.0
):
    """
    ทดสอบการส่ง audio chunks จาก RTMP stream ไปยัง Transcription Service
    
    Args:
        rtmp_url: RTMP stream URL
        transcription_url: Base URL ของ Transcription Service
        meeting_id: Meeting ID
        duration: ระยะเวลาทดสอบ (วินาที)
    """
    logger.info("🚀 Starting RTMP to Live Chunk test")
    logger.info(f"   RTMP URL: {rtmp_url}")
    logger.info(f"   Transcription URL: {transcription_url}")
    logger.info(f"   Meeting ID: {meeting_id}")
    logger.info(f"   Duration: {duration} seconds")
    logger.info(f"   Chunk size: {CHUNK_SIZE_BYTES} bytes ({CHUNK_DURATION} seconds)")
    
    # คำนวณจำนวน chunks
    num_chunks = int(duration / CHUNK_DURATION)
    logger.info(f"   Number of chunks: {num_chunks}")
    
    success_count = 0
    error_count = 0
    
    for chunk_index in range(num_chunks):
        start_time = chunk_index * CHUNK_DURATION
        
        logger.info(f"\n📦 Processing chunk {chunk_index + 1}/{num_chunks} (start_time={start_time}s)")
        
        # แยกเสียงจาก RTMP stream
        audio_data = extract_audio_chunk_from_rtmp(rtmp_url, start_time, CHUNK_DURATION)
        
        if audio_data is None:
            logger.error(f"❌ Failed to extract audio for chunk {chunk_index}")
            error_count += 1
            continue
        
        # ตรวจสอบขนาด audio data
        if len(audio_data) < CHUNK_SIZE_BYTES * 0.9:  # อนุญาตให้มี error 10%
            logger.warning(
                f"⚠️ Audio data size mismatch: got {len(audio_data)} bytes, "
                f"expected ~{CHUNK_SIZE_BYTES} bytes"
            )
        
        # ส่งไปยัง Transcription Service
        success = send_chunk_to_transcription_service(
            transcription_url=transcription_url,
            meeting_id=meeting_id,
            chunk_index=chunk_index,
            start_time=start_time,
            duration=CHUNK_DURATION,
            audio_data=audio_data
        )
        
        if success:
            success_count += 1
        else:
            error_count += 1
        
        # รอสักครู่ก่อนส่ง chunk ถัดไป (เพื่อไม่ให้ overload)
        if chunk_index < num_chunks - 1:
            time.sleep(0.5)  # รอ 0.5 วินาที
    
    # สรุปผล
    logger.info("\n" + "="*60)
    logger.info("📊 Test Summary")
    logger.info(f"   Total chunks: {num_chunks}")
    logger.info(f"   ✅ Success: {success_count}")
    logger.info(f"   ❌ Errors: {error_count}")
    logger.info(f"   Success rate: {success_count/num_chunks*100:.1f}%")
    logger.info("="*60)
    
    if error_count == 0:
        logger.info("✅ All chunks sent successfully!")
        logger.info(f"💡 Check WebSocket connection for meeting_id='{meeting_id}' to see transcription results")
    else:
        logger.warning(f"⚠️ {error_count} chunks failed. Check logs above for details.")


def main():
    parser = argparse.ArgumentParser(
        description="Test RTMP stream to /api/transcription/realtime/live-chunk"
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
        default="test-meeting-001",
        help="Meeting ID"
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
    
    # ตรวจสอบว่า FFmpeg มีอยู่หรือไม่
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ FFmpeg not found. Please install FFmpeg first.")
        sys.exit(1)
    
    # ตรวจสอบว่า Transcription Service ทำงานอยู่หรือไม่
    try:
        response = requests.get(f"{args.transcription_url}/health", timeout=5)
        if response.status_code != 200:
            logger.warning(f"⚠️ Transcription Service health check failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ Cannot connect to Transcription Service: {e}")
        logger.warning("   Continuing anyway...")
    
    # เริ่มทดสอบ
    test_rtmp_to_live_chunk(
        rtmp_url=args.rtmp_url,
        transcription_url=args.transcription_url,
        meeting_id=args.meeting_id,
        duration=args.duration
    )


if __name__ == "__main__":
    main()
