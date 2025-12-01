#!/usr/bin/env python3
"""
Script สำหรับทดสอบ Direct Transcription (ไม่ผ่าน RabbitMQ)
- Extract audio จาก video (ถ้าเป็น video)
- ส่งให้ faster-whisper แปลงเลย
- ดู GPU utilization และผลลัพธ์
"""

import sys
import os
import time
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.video_service import VideoService
from app.services.whisper_service import WhisperService
from app.services.file_service import FileService

async def test_direct_transcription(video_path: str, language: str = "th", model_size: str = "medium"):
    """
    ทดสอบ Direct Transcription
    
    Args:
        video_path: Path ไปยังไฟล์ video/audio
        language: ภาษา (default: th)
        model_size: ขนาด model (default: medium)
    """
    print("=" * 80)
    print("🧪 Direct Transcription Test (Bypass RabbitMQ)")
    print("=" * 80)
    print(f"📁 File: {video_path}")
    print(f"🌍 Language: {language}")
    print(f"📦 Model: {model_size}")
    print()
    
    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        print(f"❌ File not found: {video_path}")
        return
    
    # Initialize services
    file_service = FileService()
    video_service = VideoService()
    whisper_service = WhisperService()
    
    start_time = time.time()
    
    try:
        # Step 1: Extract audio (ถ้าเป็น video)
        print("🎬 Step 1: Extracting audio...")
        audio_extract_start = time.time()
        
        is_video = file_service.is_video_file(str(video_path_obj))
        if is_video:
            # Extract audio
            audio_path = video_service.extract_audio(
                str(video_path_obj),
                output_path=str(video_path_obj.parent / f"{video_path_obj.stem}_direct_audio.wav")
            )
            audio_extract_time = time.time() - audio_extract_start
            print(f"✅ Audio extracted in {audio_extract_time:.2f}s")
            print(f"   Output: {audio_path}")
        else:
            audio_path = str(video_path_obj)
            print(f"✅ File is already audio: {audio_path}")
            audio_extract_time = 0
        
        print()
        
        # Step 2: Direct Transcription with faster-whisper
        print("🎯 Step 2: Direct Transcription with faster-whisper...")
        transcription_start = time.time()
        
        result = await whisper_service.transcribe_file(
            audio_path,
            language=language,
            model_size=model_size
        )
        
        transcription_time = time.time() - transcription_start
        total_time = time.time() - start_time
        
        print()
        print("=" * 80)
        print("✅ Transcription Completed!")
        print("=" * 80)
        print(f"⏱️  Audio Extraction: {audio_extract_time:.2f}s")
        print(f"⏱️  Transcription: {transcription_time:.2f}s")
        print(f"⏱️  Total Time: {total_time:.2f}s")
        print()
        print(f"📝 Text Length: {len(result.get('text', ''))} characters")
        print(f"📦 Segments: {len(result.get('segments', []))}")
        print(f"🌍 Language: {result.get('language', 'N/A')}")
        print(f"🔧 Provider: {result.get('provider', 'N/A')}")
        print(f"📦 Model: {result.get('model', 'N/A')}")
        print()
        print("=" * 80)
        print("📄 Transcription Result:")
        print("=" * 80)
        print(result.get('text', ''))
        print()
        print("=" * 80)
        print("📦 Segments:")
        print("=" * 80)
        for i, segment in enumerate(result.get('segments', [])[:10], 1):  # Show first 10 segments
            print(f"{i}. [{segment.get('start', 0):.2f}s - {segment.get('end', 0):.2f}s]: {segment.get('text', '')[:80]}")
        if len(result.get('segments', [])) > 10:
            print(f"... and {len(result.get('segments', [])) - 10} more segments")
        print()
        
        # Cleanup
        if is_video and Path(audio_path).exists() and audio_path != str(video_path_obj):
            try:
                Path(audio_path).unlink()
                print(f"🧹 Cleaned up temporary audio file: {audio_path}")
            except Exception as e:
                print(f"⚠️  Could not delete temporary file: {e}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python3 test-direct-transcription.py <video_path> [language] [model_size]")
        print("Example: python3 test-direct-transcription.py uploads/v05-1.mp4 th medium")
        sys.exit(1)
    
    video_path = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "th"
    model_size = sys.argv[3] if len(sys.argv) > 3 else "medium"
    
    # Run async function
    result = asyncio.run(test_direct_transcription(video_path, language, model_size))
    
    if result:
        print("✅ Test completed successfully!")
        sys.exit(0)
    else:
        print("❌ Test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()

