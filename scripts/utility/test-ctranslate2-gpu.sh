#!/bin/bash
# Test CTranslate2 GPU Support and GPU Visibility
# ตรวจสอบว่า CTranslate2 ทำงานได้ปกติและมองเห็น GPU

# ใช้ set -e แต่ให้แต่ละขั้นตอนทำงานต่อได้แม้มี error
set +e  # ปิด set -e ชั่วคราว เพื่อให้สคริปต์ทำงานต่อได้แม้มี error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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

# ตัวแปรเก็บผลลัพธ์
TESTS_PASSED=0
TESTS_FAILED=0

print_header "🧪 Testing CTranslate2 GPU Support and GPU Visibility"

# 1. ตรวจสอบ nvidia-smi
print_header "1️⃣ Checking nvidia-smi (GPU Hardware)"
if command -v nvidia-smi &> /dev/null; then
    print_success "nvidia-smi found"
    echo ""
    echo "GPU Information:"
    nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader
    GPU_COUNT=$(nvidia-smi -L | wc -l)
    print_info "Detected $GPU_COUNT GPU(s)"
    ((TESTS_PASSED++))
else
    print_error "nvidia-smi not found - GPU may not be available"
    ((TESTS_FAILED++))
fi

# 2. ตรวจสอบ PyTorch CUDA
print_header "2️⃣ Checking PyTorch CUDA Support"
PYTHON_EXIT_CODE=0
python3 << 'PYTHON'
import sys
try:
    import torch
    print(f"✅ PyTorch version: {torch.__version__}")
    
    if torch.cuda.is_available():
        print(f"✅ CUDA available: Yes")
        print(f"   CUDA version: {torch.version.cuda}")
        print(f"   cuDNN version: {torch.backends.cudnn.version()}")
        print(f"   GPU count: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"   GPU {i}: {torch.cuda.get_device_name(i)}")
            print(f"      Memory: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.2f} GB")
    else:
        print("❌ CUDA available: No")
        sys.exit(1)
except ImportError as e:
    print(f"❌ PyTorch import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON
PYTHON_EXIT_CODE=$?

if [ $PYTHON_EXIT_CODE -eq 0 ]; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

# 3. ตรวจสอบ CTranslate2 Installation
print_header "3️⃣ Checking CTranslate2 Installation"
PYTHON_EXIT_CODE=0
python3 << 'PYTHON'
import sys
import os

# ตั้งค่า LD_LIBRARY_PATH
cudnn_path = "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
system_path = "/usr/lib/x86_64-linux-gnu"
cuda_path = "/usr/local/cuda-12.1/lib64"
ctranslate2_path = "/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"

new_ld_path = f"{cudnn_path}:{system_path}:{cuda_path}:{ctranslate2_path}"
os.environ['LD_LIBRARY_PATH'] = new_ld_path

try:
    import ctranslate2
    print(f"✅ ctranslate2 version: {ctranslate2.__version__}")
    
    # ตรวจสอบว่าเป็น CUDA build หรือไม่
    # หมายเหตุ: CTranslate2 ใช้ dynamic loading ของ CUDA libraries
    # การตรวจสอบ _cuda module อาจไม่แม่นยำ ให้ตรวจสอบจาก get_supported_compute_types แทน
    try:
        import ctranslate2._cuda
        print("✅ CTranslate2 CUDA module found (direct import)")
    except ImportError:
        # ถ้า import _cuda ไม่ได้ ให้ตรวจสอบจาก get_supported_compute_types แทน
        # เพราะ CTranslate2 อาจใช้ dynamic loading
        cuda_types = ctranslate2.get_supported_compute_types("cuda")
        if cuda_types:
            print("⚠️  CTranslate2 CUDA module not directly importable")
            print("   But CUDA support is available (dynamic loading)")
            print("   This is normal - CTranslate2 loads CUDA libraries dynamically")
        else:
            print("❌ CTranslate2 CUDA module NOT found (CPU-only build)")
            sys.exit(1)
except ImportError as e:
    print(f"❌ ctranslate2 import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON
PYTHON_EXIT_CODE=$?

if [ $PYTHON_EXIT_CODE -eq 0 ]; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

# 4. ตรวจสอบ CTranslate2 CUDA Support
print_header "4️⃣ Checking CTranslate2 CUDA Support"
PYTHON_EXIT_CODE=0
python3 << 'PYTHON'
import os
import sys

# ตั้งค่า LD_LIBRARY_PATH
cudnn_path = "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
system_path = "/usr/lib/x86_64-linux-gnu"
cuda_path = "/usr/local/cuda-12.1/lib64"
ctranslate2_path = "/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"

new_ld_path = f"{cudnn_path}:{system_path}:{cuda_path}:{ctranslate2_path}"
os.environ['LD_LIBRARY_PATH'] = new_ld_path

try:
    import ctranslate2
    
    # ตรวจสอบ CUDA compute types
    cuda_types = ctranslate2.get_supported_compute_types("cuda")
    if cuda_types:
        print(f"✅ CUDA support: Available")
        print(f"   Compute types: {', '.join(sorted(cuda_types))}")
    else:
        print("❌ CUDA support: NOT available")
        print("   This means CTranslate2 cannot use GPU")
        sys.exit(1)
    
    # ตรวจสอบ CPU compute types (เพื่อเปรียบเทียบ)
    cpu_types = ctranslate2.get_supported_compute_types("cpu")
    print(f"   CPU compute types: {', '.join(cpu_types) if cpu_types else 'None'}")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON
PYTHON_EXIT_CODE=$?

if [ $PYTHON_EXIT_CODE -eq 0 ]; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

# 5. ตรวจสอบ LD_LIBRARY_PATH
print_header "5️⃣ Checking LD_LIBRARY_PATH"
echo "Current LD_LIBRARY_PATH:"
echo "$LD_LIBRARY_PATH" | tr ':' '\n' | while read path; do
    if [ -n "$path" ]; then
        if [ -d "$path" ]; then
            print_success "  $path"
        else
            print_warning "  $path (not found)"
        fi
    fi
done

# ตรวจสอบ cuDNN libraries
print_info "Checking cuDNN libraries..."
CUDNN_FILES=(
    "libcudnn.so.8"
    "libcudnn_ops_infer.so.8"
    "libcudnn_cnn_infer.so.8"
)

CUDNN_FOUND=0
for file in "${CUDNN_FILES[@]}"; do
    found=false
    for path in "$CUDNN_LIB_PATH" "$SYSTEM_PATH" "$CUDA_LIB_PATH"; do
        if [ -f "$path/$file" ]; then
            print_success "  Found: $path/$file"
            ((CUDNN_FOUND++))
            found=true
            break
        fi
    done
    if [ "$found" = false ]; then
        print_warning "  Not found: $file"
    fi
done

if [ $CUDNN_FOUND -ge 2 ]; then
    print_success "cuDNN libraries found ($CUDNN_FOUND/3)"
    ((TESTS_PASSED++))
else
    print_warning "Some cuDNN libraries missing ($CUDNN_FOUND/3)"
    ((TESTS_FAILED++))
fi

# 6. ทดสอบ WhisperModel กับ CUDA
print_header "6️⃣ Testing WhisperModel with CUDA"
PYTHON_EXIT_CODE=0
python3 << 'PYTHON'
import os
import sys

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
    
    print("🧪 Testing WhisperModel with CUDA...")
    print("   Model: tiny (for quick test)")
    print("   Device: cuda")
    print("   Compute type: float16")
    
    # ลองสร้าง model
    model = WhisperModel("tiny", device="cuda", compute_type="float16")
    print("✅ Model created successfully!")
    
    # ตรวจสอบว่า model ใช้ GPU จริงหรือไม่
    if hasattr(model, 'model') and hasattr(model.model, 'device'):
        device = str(model.model.device)
        print(f"✅ Model device: {device}")
        if 'cuda' in device.lower():
            print("✅ Model is using GPU!")
        else:
            print("⚠️  Model device does not contain 'cuda'")
    else:
        print("⚠️  Cannot determine model device")
    
    # ตรวจสอบ GPU memory usage
    # หมายเหตุ: faster-whisper ใช้ CTranslate2 (C++ backend) ไม่ใช่ PyTorch
    # CTranslate2 จัดการ CUDA memory ผ่าน C++ libraries ไม่ผ่าน PyTorch
    # ดังนั้น torch.cuda.memory_allocated() อาจเป็น 0 แม้ว่า model ใช้ GPU อยู่แล้ว
    if torch.cuda.is_available():
        # ตรวจสอบ PyTorch CUDA memory (อาจเป็น 0 สำหรับ CTranslate2)
        memory_allocated = torch.cuda.memory_allocated() / 1024**2  # MB
        memory_reserved = torch.cuda.memory_reserved() / 1024**2  # MB
        print(f"ℹ️  PyTorch GPU memory allocated: {memory_allocated:.2f} MB")
        print(f"ℹ️  PyTorch GPU memory reserved: {memory_reserved:.2f} MB")
        
        # หมายเหตุ: CTranslate2 ใช้ CUDA memory ผ่าน C++ libraries
        # การตรวจสอบผ่าน PyTorch อาจไม่แม่นยำ
        # ถ้า model device = "cuda" แสดงว่าใช้ GPU อยู่แล้ว
        if 'cuda' in device.lower():
            print("✅ Model is using GPU (CTranslate2 manages CUDA memory separately)")
            print("   Note: GPU memory will be allocated when transcribing audio")
        else:
            print("⚠️  Model device does not indicate GPU usage")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON
PYTHON_EXIT_CODE=$?

if [ $PYTHON_EXIT_CODE -eq 0 ]; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

# 7. ตรวจสอบ GPU Visibility ใน Process
print_header "7️⃣ Checking GPU Visibility in Current Process"
PYTHON_EXIT_CODE=0
python3 << 'PYTHON'
import os
import sys

# ตั้งค่า LD_LIBRARY_PATH
cudnn_path = "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
system_path = "/usr/lib/x86_64-linux-gnu"
cuda_path = "/usr/local/cuda-12.1/lib64"
ctranslate2_path = "/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"

new_ld_path = f"{cudnn_path}:{system_path}:{cuda_path}:{ctranslate2_path}"
os.environ['LD_LIBRARY_PATH'] = new_ld_path

try:
    import torch
    
    print("Checking CUDA_VISIBLE_DEVICES...")
    cuda_visible = os.getenv('CUDA_VISIBLE_DEVICES', 'not set')
    print(f"   CUDA_VISIBLE_DEVICES: {cuda_visible}")
    
    if torch.cuda.is_available():
        print(f"✅ torch.cuda.is_available(): True")
        print(f"✅ torch.cuda.device_count(): {torch.cuda.device_count()}")
        
        for i in range(torch.cuda.device_count()):
            print(f"   GPU {i}: {torch.cuda.get_device_name(i)}")
            props = torch.cuda.get_device_properties(i)
            print(f"      Memory: {props.total_memory / 1024**3:.2f} GB")
            print(f"      Compute Capability: {props.major}.{props.minor}")
    else:
        print("❌ torch.cuda.is_available(): False")
        sys.exit(1)
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON
PYTHON_EXIT_CODE=$?

if [ $PYTHON_EXIT_CODE -eq 0 ]; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

# สรุปผล
print_header "📊 Test Summary"
echo "Tests passed: $TESTS_PASSED"
echo "Tests failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    print_success "🎉 All tests passed! CTranslate2 GPU support is working correctly."
    echo ""
    print_info "Next steps:"
    echo "  1. Start services: bash scripts/pod/start-pod.sh"
    echo "  2. Start RQ workers: bash scripts/pod/start-rq-workers.sh"
    echo "  3. Monitor GPU usage: nvidia-smi --query-compute-apps"
    exit 0
else
    print_error "❌ Some tests failed. Please check the errors above."
    echo ""
    print_info "Troubleshooting:"
    echo "  1. Check LD_LIBRARY_PATH: echo \$LD_LIBRARY_PATH"
    echo "  2. Run fix script: bash scripts/utility/fix-ctranslate2-gpu.sh"
    echo "  3. Reinstall ctranslate2: pip3 uninstall -y ctranslate2 && pip3 install ctranslate2==4.4.0 --no-cache-dir"
    exit 1
fi
