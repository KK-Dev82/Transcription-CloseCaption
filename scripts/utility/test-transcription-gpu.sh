#!/bin/bash
# Test Transcription with GPU
# ทดสอบ transcription ด้วยไฟล์ audio และตรวจสอบว่าใช้ GPU จริงหรือไม่

set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo "================================================================================"
    echo -e "${BLUE}$1${NC}"
    echo "================================================================================"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# ตรวจสอบ arguments
if [ $# -eq 0 ]; then
    print_error "Usage: $0 <audio_file_path> [model_size]"
    print_info "Example: $0 uploads/test.wav tiny"
    exit 1
fi

AUDIO_FILE="$1"
MODEL_SIZE="${2:-tiny}"

# แปลงเป็น absolute path ถ้าเป็น relative path
if [[ "$AUDIO_FILE" != /* ]]; then
    # ถ้าเป็น relative path ให้แปลงเป็น absolute path จาก PROJECT_ROOT
    AUDIO_FILE="$PROJECT_ROOT/$AUDIO_FILE"
fi

if [ ! -f "$AUDIO_FILE" ]; then
    print_error "Audio file not found: $AUDIO_FILE"
    print_info "Current directory: $(pwd)"
    print_info "Looking for: $AUDIO_FILE"
    exit 1
fi

print_header "🧪 Testing Transcription with GPU"
print_info "Audio file: $AUDIO_FILE"
print_info "Model size: $MODEL_SIZE"
echo ""

# ตั้งค่า LD_LIBRARY_PATH
CUDNN_LIB_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
SYSTEM_PATH="/usr/lib/x86_64-linux-gnu"
CUDA_LIB_PATH="/usr/local/cuda-12.1/lib64"
CTRANSLATE2_LIB_PATH="/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"

NEW_LD_PATH=""
for path in "$CUDNN_LIB_PATH" "$SYSTEM_PATH" "$CUDA_LIB_PATH" "$CTRANSLATE2_LIB_PATH"; do
    if [ -d "$path" ]; then
        if [ -z "$NEW_LD_PATH" ]; then
            NEW_LD_PATH="$path"
        else
            NEW_LD_PATH="$NEW_LD_PATH:$path"
        fi
    fi
done

if [ -n "$NEW_LD_PATH" ]; then
    export LD_LIBRARY_PATH="$NEW_LD_PATH:${LD_LIBRARY_PATH:-}"
fi

# ตรวจสอบ GPU ก่อน transcription
print_header "1️⃣ Checking GPU Before Transcription"
if command -v nvidia-smi &> /dev/null; then
    print_info "GPU status before transcription:"
    nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader
    echo ""
else
    print_warning "nvidia-smi not found"
fi

# เริ่ม transcription และตรวจสอบ GPU usage
print_header "2️⃣ Starting Transcription"
print_info "This may take a few minutes depending on audio length..."
echo ""

# ใช้ Python script เพื่อ transcription และตรวจสอบ GPU
python3 << PYTHON_SCRIPT
import os
import sys
import time
import subprocess
from datetime import datetime

# ตั้งค่า LD_LIBRARY_PATH
cudnn_path = "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
system_path = "/usr/lib/x86_64-linux-gnu"
cuda_path = "/usr/local/cuda-12.1/lib64"
ctranslate2_path = "/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"

new_ld_path = f"{cudnn_path}:{system_path}:{cuda_path}:{ctranslate2_path}"
os.environ['LD_LIBRARY_PATH'] = new_ld_path

try:
    from faster_whisper import WhisperModel
    import torch
    
    audio_file = "$AUDIO_FILE"
    model_size = "$MODEL_SIZE"
    
    print(f"📁 Loading model: {model_size}")
    print(f"   Device: cuda")
    print(f"   Compute type: float16")
    print("")
    
    # สร้าง model
    start_time = time.time()
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    model_load_time = time.time() - start_time
    
    print(f"✅ Model loaded in {model_load_time:.2f} seconds")
    print(f"   Model device: {model.model.device if hasattr(model, 'model') else 'unknown'}")
    print("")
    
    # ตรวจสอบ GPU memory หลัง load model
    if torch.cuda.is_available():
        memory_allocated = torch.cuda.memory_allocated() / 1024**2  # MB
        memory_reserved = torch.cuda.memory_reserved() / 1024**2  # MB
        print(f"ℹ️  PyTorch GPU memory after model load:")
        print(f"   Allocated: {memory_allocated:.2f} MB")
        print(f"   Reserved: {memory_reserved:.2f} MB")
        print("")
    
    # ตรวจสอบ GPU usage ผ่าน nvidia-smi
    print("🔍 Checking GPU usage via nvidia-smi...")
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            print("✅ GPU processes detected:")
            print(result.stdout)
        else:
            print("ℹ️  No GPU processes detected yet (may appear during transcription)")
    except Exception as e:
        print(f"⚠️  Could not check nvidia-smi: {e}")
    print("")
    
    # เริ่ม transcription
    print(f"🎙️  Starting transcription...")
    print(f"   Audio file: {audio_file}")
    print("")
    
    transcription_start = time.time()
    
    # Transcribe
    segments, info = model.transcribe(
        audio_file,
        beam_size=1,
        language="th",
        vad_filter=True
    )
    
    # เก็บ segments
    all_segments = []
    for segment in segments:
        all_segments.append({
            'start': segment.start,
            'end': segment.end,
            'text': segment.text
        })
    
    transcription_time = time.time() - transcription_start
    
    # ตรวจสอบ GPU usage หลัง transcription
    print("")
    print("🔍 Checking GPU usage after transcription...")
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            print("✅ GPU processes detected:")
            print(result.stdout)
        else:
            print("ℹ️  No GPU processes in nvidia-smi (CTranslate2 may have released memory)")
    except Exception as e:
        print(f"⚠️  Could not check nvidia-smi: {e}")
    print("")
    
    # สรุปผลลัพธ์
    print("=" * 80)
    print("📊 Transcription Results")
    print("=" * 80)
    print(f"✅ Transcription completed successfully!")
    print(f"   Model: {model_size}")
    print(f"   Device: cuda")
    print(f"   Language: {info.language} (probability: {info.language_probability:.2f})")
    print(f"   Duration: {info.duration:.2f} seconds")
    print(f"   Model load time: {model_load_time:.2f} seconds")
    print(f"   Transcription time: {transcription_time:.2f} seconds")
    print(f"   Speed: {info.duration / transcription_time:.2f}x realtime")
    print(f"   Segments: {len(all_segments)}")
    print("")
    
    # แสดงตัวอย่าง text
    if all_segments:
        print("📝 Sample transcription (first 3 segments):")
        for i, seg in enumerate(all_segments[:3]):
            print(f"   [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text'][:100]}")
        if len(all_segments) > 3:
            print(f"   ... and {len(all_segments) - 3} more segments")
    print("")
    
    # ตรวจสอบ GPU usage สุดท้าย
    if torch.cuda.is_available():
        memory_allocated = torch.cuda.memory_allocated() / 1024**2  # MB
        memory_reserved = torch.cuda.memory_reserved() / 1024**2  # MB
        print(f"ℹ️  Final PyTorch GPU memory:")
        print(f"   Allocated: {memory_allocated:.2f} MB")
        print(f"   Reserved: {memory_reserved:.2f} MB")
    print("")
    
    print("=" * 80)
    print("✅ GPU Transcription Test: PASSED")
    print("=" * 80)
    print("")
    print("💡 Note: CTranslate2 manages CUDA memory separately from PyTorch")
    print("   GPU usage may not show in PyTorch memory stats, but it's working!")
    print("   Check nvidia-smi during transcription to see actual GPU usage.")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_SCRIPT

EXIT_CODE=$?

echo ""
print_header "3️⃣ Final GPU Status"
if command -v nvidia-smi &> /dev/null; then
    print_info "GPU status after transcription:"
    nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader
    echo ""
    
    print_info "GPU compute processes:"
    nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null || echo "No compute processes detected"
else
    print_warning "nvidia-smi not found"
fi

if [ $EXIT_CODE -eq 0 ]; then
    print_success "🎉 Transcription test completed successfully!"
    print_info "GPU is working correctly for transcription!"
else
    print_error "❌ Transcription test failed!"
    exit 1
fi
