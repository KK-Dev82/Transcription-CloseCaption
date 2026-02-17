#!/bin/bash
# โหลด env ตามจำนวน GPU อัตโนมัติ เพื่อป้องกัน OOM
# - .env.runpod = config ล่าสุดสำหรับ 2 GPU (รวม Diarization)
# - 1 GPU → .env.runpod แล้ว override ด้วย .env.runpod-1GPU (ลด workers, chunk limits)
# - 2+ GPUs → .env.runpod เท่านั้น (ไม่ต้องโหลด .env.runpod-2GPU)
#
# ใช้: source scripts/utility/load-env-by-gpu.sh
# Override: ENV_PROFILE=1gpu หรือ 2gpu เพื่อบังคับใช้โปรไฟล์นั้น

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# 1) โหลด base (.env.runpod = 2 GPU config ล่าสุด)
if [ -f "$PROJECT_ROOT/.env.runpod" ]; then
    set -a
    source "$PROJECT_ROOT/.env.runpod"
    set +a
fi

# 2) กำหนดโปรไฟล์ตาม GPU (หรือ ENV_PROFILE)
PROFILE=""
if [ -n "${ENV_PROFILE:-}" ]; then
    case "${ENV_PROFILE}" in
        1gpu|1GPU) PROFILE="1GPU" ;;
        2gpu|2GPU) PROFILE="2GPU" ;;
        *) PROFILE="" ;;
    esac
fi

if [ -z "$PROFILE" ] && command -v nvidia-smi &> /dev/null; then
    DETECTED=$(nvidia-smi -L 2>/dev/null | wc -l)
    DETECTED=${DETECTED:-1}
    if [ "$DETECTED" -eq 1 ]; then
        PROFILE="1GPU"
    else
        PROFILE="2GPU"
    fi
fi

# 3) 1 GPU เท่านั้น: โหลด .env.runpod-1GPU เพื่อ override (ลด workers ป้องกัน OOM)
#    2 GPUs: ใช้ค่าจาก .env.runpod อยู่แล้ว ไม่ต้องโหลด .env.runpod-2GPU
if [ "$PROFILE" = "1GPU" ]; then
    ENV_SPECIFIC="$PROJECT_ROOT/.env.runpod-1GPU"
    if [ -f "$ENV_SPECIFIC" ]; then
        set -a
        source "$ENV_SPECIFIC"
        set +a
    fi
    export ENV_LOADED_PROFILE="1GPU"
else
    export ENV_LOADED_PROFILE="2GPU"
fi
