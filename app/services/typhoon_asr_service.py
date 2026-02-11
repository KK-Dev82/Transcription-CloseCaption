"""
TyPhoon ASR Service สำหรับ FE Live Caption
ใช้ typhoon-asr (NeMo FastConformer) สำหรับภาษาไทยโดยเฉพาะ
รองรับการสลับกับ faster-whisper ผ่าน FE_CC_PROVIDER
"""

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_TYPHOON_AVAILABLE = False
try:
    from typhoon_asr import transcribe as typhoon_transcribe

    _TYPHOON_AVAILABLE = True
except ImportError:
    logger.warning(
        "typhoon-asr not installed. FE Live Caption with TyPhoon will be unavailable. "
        "Install: pip install typhoon-asr"
    )


def is_typhoon_available() -> bool:
    """ตรวจสอบว่า typhoon-asr พร้อมใช้งานหรือไม่"""
    return _TYPHOON_AVAILABLE


def transcribe_audio(
    audio_path: str,
    *,
    with_timestamps: bool = True,
    device: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict:
    """
    แปลงเสียงเป็นข้อความด้วย TyPhoon ASR

    Args:
        audio_path: Path ไปยังไฟล์ audio (WAV, MP3, etc.)
        with_timestamps: สร้าง segments พร้อม timestamps หรือไม่
        device: cuda, cpu หรือ auto (default จาก env)
        model: HuggingFace model ID (default จาก env)

    Returns:
        Dict: {"text": "...", "segments": [{"start": float, "end": float, "text": str}, ...]}
              รูปแบบเดียวกับ whisper_service.transcribe_file สำหรับ compatibility
    """
    if not _TYPHOON_AVAILABLE:
        raise ImportError(
            "typhoon-asr is not installed. Install with: pip install typhoon-asr"
        )

    device = device or os.getenv("FE_CC_TYPHOON_DEVICE", "auto")
    model = model or os.getenv("FE_CC_TYPHOON_MODEL", "typhoon-ai/typhoon-asr-realtime")

    try:
        result = typhoon_transcribe(
            audio_path,
            with_timestamps=with_timestamps,
            device=device,
        )

        text = (result.get("text") or "").strip()
        timestamps = result.get("timestamps") or []

        # แปลง timestamps เป็น segments format (compatible กับ websocket)
        segments: List[Dict] = []
        if with_timestamps and timestamps:
            for ts in timestamps:
                start = float(ts.get("start", 0))
                end = float(ts.get("end", 0))
                word = ts.get("word", "")
                segments.append({"start": start, "end": end, "text": word})
        elif text:
            # ถ้าไม่มี timestamps ให้สร้าง segment เดียว
            segments = [{"start": 0.0, "end": 0.0, "text": text}]

        return {
            "text": text,
            "segments": segments,
            "provider": "typhoon",
            "model": model,
        }
    except Exception as e:
        logger.error(f"[TyPhoon ASR] Transcription failed: {e}")
        raise
