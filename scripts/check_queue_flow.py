#!/usr/bin/env python3
"""
สคริปต์ตรวจสอบ Flow ทั้งหมดที่เกี่ยวข้องกับ Queue Limits
"""
import os
import sys
from pathlib import Path

# Load env.runpod
env_file = Path(__file__).parent.parent / "env.runpod"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

print("=" * 80)
print("🔍 ตรวจสอบ Queue Flow และ Limits")
print("=" * 80)
print()

# 1. Environment Variables
print("1️⃣ Environment Variables (จาก env.runpod):")
print("-" * 80)
print(f"  MAX_QUEUE_REQUEST = {os.getenv('MAX_QUEUE_REQUEST', 'NOT SET')}")
print(f"  MAX_QUEUE_EXTRACTION = {os.getenv('MAX_QUEUE_EXTRACTION', 'NOT SET')}")
print(f"  MAX_QUEUE_TRANSCRIBE = {os.getenv('MAX_QUEUE_TRANSCRIBE', 'NOT SET')}")
print(f"  ADMISSION_CONTROL_MODE = {os.getenv('ADMISSION_CONTROL_MODE', 'NOT SET')}")
print(f"  USE_3QUEUE_ARCHITECTURE = {os.getenv('USE_3QUEUE_ARCHITECTURE', 'NOT SET')}")
print()

# 2. Config Files
print("2️⃣ Config Files Default Values:")
print("-" * 80)
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.worker_config import (
        MAX_QUEUE_REQUEST,
        MAX_QUEUE_EXTRACTION,
        MAX_QUEUE_TRANSCRIBE
    )
    print(f"  config/worker_config.py:")
    print(f"    MAX_QUEUE_REQUEST = {MAX_QUEUE_REQUEST}")
    print(f"    MAX_QUEUE_EXTRACTION = {MAX_QUEUE_EXTRACTION}")
    print(f"    MAX_QUEUE_TRANSCRIBE = {MAX_QUEUE_TRANSCRIBE}")
except Exception as e:
    print(f"  ❌ Error loading config: {e}")
print()

# 3. Flow Analysis
print("3️⃣ Flow Analysis:")
print("-" * 80)
print("  📍 API Request Flow:")
print("    1. API receives request → TranscriptionService.start_transcription()")
print("    2. Admission Control Check:")
admission_mode = os.getenv('ADMISSION_CONTROL_MODE', 'rabbitmq').lower()
if admission_mode == 'api':
    print(f"       ✅ Mode: 'api' - API checks queue size BEFORE accepting")
    print(f"       ⚠️  If queue size >= MAX_QUEUE_REQUEST → Reject with 503")
elif admission_mode == 'rabbitmq':
    print(f"       ✅ Mode: 'rabbitmq' - API accepts all, RabbitMQ rejects when full")
    print(f"       ⚠️  RabbitMQ queue has max-length with x-overflow=reject-publish")
else:
    print(f"       ⚠️  Mode: '{admission_mode}' - No admission control")
print()
print("    3. RabbitMQ Service → send_transcription_request_task()")
print("    4. Queue Declaration:")
print(f"       - transcription_request_queue: max-length = {os.getenv('MAX_QUEUE_REQUEST', '51')}")
print(f"       - audio_extraction_queue: max-length = {os.getenv('MAX_QUEUE_EXTRACTION', '80')}")
print(f"       - transcription_queue: max-length = {os.getenv('MAX_QUEUE_TRANSCRIBE', '30')}")
print()
print("    5. Worker Consumes:")
print(f"       - TRANSCRIPTION_REQUEST_PREFETCH_COUNT = {os.getenv('TRANSCRIPTION_REQUEST_PREFETCH_COUNT', '1')}")
print(f"       - AUDIO_EXTRACTION_PREFETCH_COUNT = {os.getenv('AUDIO_EXTRACTION_PREFETCH_COUNT', '1')}")
print(f"       - TRANSCRIPTION_PREFETCH_COUNT = {os.getenv('TRANSCRIPTION_PREFETCH_COUNT', '1')}")
print()

# 4. Potential Issues
print("4️⃣ Potential Issues:")
print("-" * 80)
issues = []

if os.getenv('MAX_QUEUE_TRANSCRIBE', '30') != '30':
    issues.append(f"  ⚠️  MAX_QUEUE_TRANSCRIBE = {os.getenv('MAX_QUEUE_TRANSCRIBE')} (should be 30)")

if os.getenv('ADMISSION_CONTROL_MODE', 'rabbitmq').lower() == 'api':
    issues.append("  ⚠️  ADMISSION_CONTROL_MODE=api - API checks queue size (may reject early)")

if int(os.getenv('TRANSCRIPTION_REQUEST_PREFETCH_COUNT', '1')) < 25:
    issues.append(f"  ⚠️  TRANSCRIPTION_REQUEST_PREFETCH_COUNT = {os.getenv('TRANSCRIPTION_REQUEST_PREFETCH_COUNT', '1')} (should be 25)")

if int(os.getenv('AUDIO_EXTRACTION_PREFETCH_COUNT', '1')) < 25:
    issues.append(f"  ⚠️  AUDIO_EXTRACTION_PREFETCH_COUNT = {os.getenv('AUDIO_EXTRACTION_PREFETCH_COUNT', '1')} (should be 25)")

if issues:
    for issue in issues:
        print(issue)
else:
    print("  ✅ No obvious issues found")
print()

# 5. Recommendations
print("5️⃣ Recommendations:")
print("-" * 80)
print("  ✅ Check actual RabbitMQ queue max-length:")
print("     - Connect to RabbitMQ Management UI")
print("     - Check queue 'transcription_request_queue' arguments")
print("     - Look for 'x-max-length' value")
print()
print("  ✅ If queue has max-length=3:")
print("     - Delete old queue: rabbitmqadmin delete queue name=transcription_request_queue")
print("     - Restart service to recreate queue with new max-length")
print()
print("  ✅ Verify environment variables are loaded:")
print("     - Check service logs for queue declaration messages")
print("     - Should see: 'Created transcription_request_queue (max: 51)'")
print()

