#!/usr/bin/env python3
"""
ทดสอบ Transcription โดยตรง โดยไม่ผ่าน RabbitMQ
"""
import sys
import os
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.whisper_service import WhisperService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_transcription_direct():
    """ทดสอบ transcription โดยตรง"""
    print("=" * 80)
    print("🧪 ทดสอบ Transcription โดยตรง (ไม่ผ่าน RabbitMQ)")
    print("=" * 80)
    
    # Audio file path
    audio_file = "/workspace/transcription-service/uploads/temp/task_1766032691_960629c3-86fa-4c2f-92d5-59c8b5e89ded_v10-1_audio/chunk_0_960629c3-86fa-4c2f-92d5-59c8b5e89ded_v10-1_audio.wav"
    
    # Check if file exists
    if not os.path.exists(audio_file):
        # Try alternative path
        audio_file = "/workspace/transcription-service/uploads/960629c3-86fa-4c2f-92d5-59c8b5e89ded_v10-1.mp4"
        if not os.path.exists(audio_file):
            print(f"❌ File not found: {audio_file}")
            return
    
    print(f"\n📁 Audio file: {audio_file}")
    print(f"📊 File size: {os.path.getsize(audio_file) / 1024 / 1024:.2f} MB")
    
    try:
        # Initialize WhisperService
        print("\n🔧 Initializing WhisperService...")
        whisper_service = WhisperService()
        
        # Test transcription
        print("\n🎯 Starting transcription...")
        print(f"   Language: th")
        print(f"   Model: base")
        
        result = whisper_service.transcribe_file(
            audio_path=audio_file,
            language="th",
            model_size="base"
        )
        
        print("\n" + "=" * 80)
        print("✅ Transcription Completed!")
        print("=" * 80)
        print(f"📝 Text length: {len(result.get('text', ''))} characters")
        print(f"📦 Segments: {len(result.get('segments', []))}")
        print(f"🌍 Language: {result.get('language', 'N/A')}")
        print(f"⏱️  Processing time: {result.get('processing_time', 0):.2f}s")
        
        text = result.get('text', '')
        if text:
            print(f"\n📄 Text preview (first 200 chars):")
            print(text[:200] + "..." if len(text) > 200 else text)
        
        segments = result.get('segments', [])
        if segments:
            print(f"\n📦 First 3 segments:")
            for i, seg in enumerate(segments[:3], 1):
                print(f"   {i}. [{seg.get('start', 0):.2f}s - {seg.get('end', 0):.2f}s] {seg.get('text', '')[:50]}...")
        
        print("=" * 80)
        return result
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = test_transcription_direct()
    if result:
        print("\n✅ Test completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Test failed!")
        sys.exit(1)

