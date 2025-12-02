#!/bin/bash
# Script แก้ปัญหา CUDA version mismatch (ทางเลือก)
# 
# ถ้า Option 1 ไม่ได้ผล ลอง Option 2: ใช้ CPU mode หรือ workaround อื่นๆ
#
# วิธีใช้งาน:
#   bash scripts/pod/fix-cuda-mismatch-alternative.sh

set -e

echo "🔧 แก้ปัญหา CUDA Version Mismatch (ทางเลือก)"
echo "============================================="
echo ""

echo "📋 Option A: ใช้ CPU Mode (เสถียรที่สุด)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  CPU mode จะช้ากว่าแต่เสถียรกว่า"
echo "   สามารถทำงานได้โดยไม่ต้องแก้ CUDA"
echo ""
echo "วิธีใช้: ตั้ง environment variable"
echo "  export WHISPER_DEVICE=cpu"
echo "  export CT2_FORCE_CPU=1"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Option B: ตั้ง CUDA Compatibility Mode"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "CUDA 12.1 รองรับ backward compatibility กับ 11.8"
echo "แต่ต้องตั้ง environment variables:"
echo ""

cat << 'EOF'
export CUDA_MODULE_LOADING=LAZY
export CUDA_CACHE_DISABLE=0
export CT2_USE_CUDA_GRAPH=0
export CUDA_LAUNCH_BLOCKING=0

# ลองใช้ compute type อื่น
export CT2_FORCE_CPU=false
export CT2_COMPUTE_TYPE=float32  # แทน float16
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Option C: ตรวจสอบและ Clean CUDA Cache"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "ต้องการลบ CUDA cache และทดสอบใหม่? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🧹 ลบ CUDA cache..."
    
    # ลบ PyTorch cache
    python3 << 'PYEOF'
import torch
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    print("✓ ลบ PyTorch CUDA cache แล้ว")
PYEOF
    
    # ลบ CUDA kernel cache
    rm -rf ~/.nv/ComputeCache 2>/dev/null || true
    rm -rf /root/.nv/ComputeCache 2>/dev/null || true
    echo "✓ ลบ CUDA kernel cache แล้ว"
    
    echo ""
    echo "✅ Clean เสร็จสมบูรณ์!"
    echo ""
    echo "💡 ลองทดสอบ transcription อีกครั้ง"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Option D: ตรวจสอบและ Fix Environment Variables"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cat << 'EOF' > /tmp/fix-env-vars.sh
#!/bin/bash
# ตั้ง environment variables สำหรับ CUDA compatibility

export CT2_USE_CUDA_GRAPH=0
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export CUDA_VISIBLE_DEVICES=0
export CUDA_MODULE_LOADING=LAZY
export CUDA_CACHE_DISABLE=0

echo "✅ Environment variables ตั้งค่าแล้ว"
echo ""
echo "รายการ environment variables:"
env | grep -E 'CUDA|CT2|OMP|MKL'
EOF

chmod +x /tmp/fix-env-vars.sh

echo "📝 สร้างสคริปต์สำหรับตั้ง environment variables: /tmp/fix-env-vars.sh"
echo ""
echo "💡 วิธีใช้:"
echo "   source /tmp/fix-env-vars.sh"
echo "   # หรือ"
echo "   bash /tmp/fix-env-vars.sh"
echo ""

