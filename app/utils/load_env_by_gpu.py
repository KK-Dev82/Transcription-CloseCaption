"""
โหลด env ตามจำนวน GPU อัตโนมัติ เพื่อป้องกัน OOM
- .env.runpod = 2 GPU config ล่าสุด (รวม Diarization)
- 1 GPU → .env.runpod แล้ว override ด้วย .env.runpod-1GPU
- 2+ GPUs → .env.runpod เท่านั้น
"""
import os
import subprocess
from pathlib import Path


def _detect_gpu_count() -> int:
    try:
        r = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},
        )
        if r.returncode == 0 and r.stdout:
            return len([l for l in r.stdout.strip().split("\n") if l.strip()])
    except Exception:
        pass
    try:
        import torch
        return torch.cuda.device_count()
    except Exception:
        pass
    return 1


def load_env_by_gpu(project_root: Path | None = None) -> str | None:
    """
    โหลด .env.runpod (2 GPU config) แล้วถ้า 1 GPU ให้ override ด้วย .env.runpod-1GPU
    Returns: โปรไฟล์ที่โหลด (1GPU/2GPU) หรือ None
    """
    from dotenv import load_dotenv

    root = project_root or Path(__file__).resolve().parent.parent.parent
    base_env = root / ".env.runpod"
    if not base_env.exists():
        return None

    load_dotenv(base_env)

    profile = os.getenv("ENV_PROFILE", "").lower()
    if profile in ("1gpu", "2gpu"):
        profile = f"{profile[0].upper()}GPU"
    elif not profile:
        n = _detect_gpu_count()
        profile = "1GPU" if n == 1 else "2GPU"

    os.environ["ENV_LOADED_PROFILE"] = profile

    # 1 GPU เท่านั้น: override ด้วย .env.runpod-1GPU (ลด workers ป้องกัน OOM)
    if profile == "1GPU":
        specific = root / ".env.runpod-1GPU"
        if specific.exists():
            load_dotenv(specific)
    return profile
