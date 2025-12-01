#!/usr/bin/env python3
"""
Script สำหรับทดสอบ faster-whisper ที่ Local (ไม่ต้องใช้ GPU)
- ใช้ CPU mode
- ทดสอบการแปลงเสียงเป็นภาษาไทย
"""

import sys
import os
import time
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables for CPU mode
os.environ['WHISPER_PROVIDER'] = 'faster-whisper'
os.environ['WHISPER_DEVICE'] = 'cpu'  # ใช้ CPU สำหรับ local testing
os.environ['WHISPER_MODEL'] = 'base'  # ใช้ base model (เล็กกว่า medium) สำหรับ local
os.environ['WHISPER_COMPUTE_TYPE'] = 'float32'  # CPU ใช้ float32

from app.services.whisper_service import WhisperService
from app.services.file_service import FileService
from app.services.video_service import VideoService

async def test_faster_whisper_local(audio_path: str, language: str = "th", model_size: str = "base"):
    """
    ทดสอบ faster-whisper ที่ local (CPU mode)
    
    Args:
        audio_path: Path ไปยังไฟล์ audio/video
        language: ภาษา (default: th)
        model_size: ขนาด model (default: base สำหรับ CPU)
    """
    print("=" * 80)
    print("🧪 Faster-Whisper Local Test (CPU Mode)")
    print("=" * 80)
    print(f"📁 File: {audio_path}")
    print(f"🌍 Language: {language}")
    print(f"📦 Model: {model_size}")
    print(f"🖥️  Device: CPU (local testing)")
    print()
    
    audio_path_obj = Path(audio_path)
    if not audio_path_obj.exists():
        print(f"❌ File not found: {audio_path}")
        return None
    
    # Initialize services
    file_service = FileService()
    video_service = VideoService()
    whisper_service = WhisperService()
    
    start_time = time.time()
    
    try:
        # Step 1: Extract audio (ถ้าเป็น video)
        print("🎬 Step 1: Checking file type...")
        is_video = file_service.is_video_file(str(audio_path_obj))
        
        if is_video:
            print("   📹 File is video - extracting audio...")
            audio_extract_start = time.time()
            audio_path = video_service.extract_audio(
                str(audio_path_obj),
                output_path=str(audio_path_obj.parent / f"{audio_path_obj.stem}_test_audio.wav")
            )
            audio_extract_time = time.time() - audio_extract_start
            print(f"✅ Audio extracted in {audio_extract_time:.2f}s")
            print(f"   Output: {audio_path}")
        else:
            audio_path = str(audio_path_obj)
            print(f"✅ File is already audio: {audio_path}")
            audio_extract_time = 0
        
        print()
        
        # Step 2: Direct Transcription with faster-whisper
        print("🎯 Step 2: Starting transcription with faster-whisper...")
        print("   (This may take a while on CPU...)")
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
        print(f"⏱️  Processing Time: {result.get('processing_time', 'N/A')}s")
        print()
        print("=" * 80)
        print("📄 Transcription Result (First 500 chars):")
        print("=" * 80)
        text = result.get('text', '')
        print(text[:500])
        if len(text) > 500:
            print(f"... ({len(text) - 500} more characters)")
        print()
        print("=" * 80)
        print("📦 First 5 Segments:")
        print("=" * 80)
        for i, segment in enumerate(result.get('segments', [])[:5], 1):
            print(f"{i}. [{segment.get('start', 0):.2f}s - {segment.get('end', 0):.2f}s]: {segment.get('text', '')[:80]}")
        if len(result.get('segments', [])) > 5:
            print(f"... and {len(result.get('segments', [])) - 5} more segments")
        print()
        
        # Cleanup
        if is_video and Path(audio_path).exists() and audio_path != str(audio_path_obj):
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
        print("Usage: python3 test-faster-whisper-local.py <audio/video_path> [language] [model_size]")
        print("Example: python3 test-faster-whisper-local.py uploads/test.mp4 th base")
        print()
        print("Note: For local testing, use 'base' model (smaller, faster on CPU)")
        print("      GPU models (medium, large) will be very slow on CPU")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "th"
    model_size = sys.argv[3] if len(sys.argv) > 3 else "base"
    
    # Run async function
    result = asyncio.run(test_faster_whisper_local(audio_path, language, model_size))
    
    if result:
        print("✅ Test completed successfully!")
        sys.exit(0)
    else:
        print("❌ Test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()

