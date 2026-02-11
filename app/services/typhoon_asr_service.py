"""
TyPhoon ASR Service สำหรับ FE Live Caption
ใช้ typhoon-asr (NeMo FastConformer) สำหรับภาษาไทยโดยเฉพาะ
รองรับการสลับกับ faster-whisper ผ่าน FE_CC_PROVIDER

✅ Model caching: โหลดโมเดลครั้งเดียวแล้ว reuse — ลด latency จาก ~5–7 วินาที/chunk เหลือ ~1–2 วินาที
"""

import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional

from app.utils.cc_temp_storage import ensure_cc_temp_dir

logger = logging.getLogger(__name__)

_TYPHOON_AVAILABLE = False
_USE_LEGACY = False  # fallback to typhoon_asr.transcribe ถ้า NeMo direct ไม่ได้
_typhoon_model = None
_typhoon_model_lock = threading.Lock()
_legacy_cwd_lock = threading.Lock()  # chdir ไม่ thread-safe — ใช้ lock ตอน legacy path

try:
    import nemo.collections.asr as nemo_asr
    import torch
    import librosa
    import soundfile as sf

    _TYPHOON_AVAILABLE = True
except ImportError:
    try:
        from typhoon_asr import transcribe as _typhoon_transcribe_legacy

        _TYPHOON_AVAILABLE = True
        _USE_LEGACY = True
    except ImportError:
        pass
    if not _TYPHOON_AVAILABLE:
        logger.warning(
            "typhoon-asr / nemo not installed. FE Live Caption with TyPhoon will be unavailable. "
            "Install: pip install typhoon-asr"
        )


def is_typhoon_available() -> bool:
    """ตรวจสอบว่า typhoon-asr พร้อมใช้งานหรือไม่"""
    return _TYPHOON_AVAILABLE


def _get_typhoon_model(model_name: str, device: str):
    """โหลดโมเดลครั้งเดียวแล้ว cache (singleton)"""
    global _typhoon_model
    with _typhoon_model_lock:
        if _typhoon_model is not None:
            return _typhoon_model
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[TyPhoon ASR] 🌪️ Loading model (first time): {model_name} on {device}")
        _typhoon_model = nemo_asr.models.ASRModel.from_pretrained(
            model_name=model_name,
            map_location=device,
        )
        if _typhoon_model is None:
            raise RuntimeError("Failed to load Typhoon ASR model")
        logger.info("[TyPhoon ASR] ✅ Model loaded and cached")
        return _typhoon_model


def _prepare_audio(input_path: str, target_sr: int = 16000) -> tuple[str, float]:
    """เตรียม audio: load, resample, normalize — เหมือน typhoon-asr"""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")
    y, sr = librosa.load(str(path), sr=None)
    if y is None:
        raise IOError("Failed to load audio file")
    duration = len(y) / sr
    if sr != target_sr:
        y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
    y = y / (max(abs(y)) + 1e-8)
    temp_dir = ensure_cc_temp_dir()
    fd, out_path = tempfile.mkstemp(suffix=".wav", prefix="typhoon_proc_", dir=str(temp_dir))
    os.close(fd)
    sf.write(out_path, y, target_sr)
    return out_path, duration


def transcribe_audio(
    audio_path: str,
    *,
    with_timestamps: bool = True,
    device: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict:
    """
    แปลงเสียงเป็นข้อความด้วย TyPhoon ASR (ใช้ model cache — เร็วขึ้นมาก)

    Args:
        audio_path: Path ไปยังไฟล์ audio (WAV, MP3, etc.)
        with_timestamps: สร้าง segments พร้อม timestamps หรือไม่
        device: cuda, cpu หรือ auto (default จาก env)
        model: HuggingFace model ID (default จาก env)

    Returns:
        Dict: {"text": "...", "segments": [{"start": float, "end": float, "text": str}, ...]}
    """
    if not _TYPHOON_AVAILABLE:
        raise ImportError(
            "typhoon-asr is not installed. Install with: pip install typhoon-asr"
        )

    device = device or os.getenv("FE_CC_TYPHOON_DEVICE", "auto")
    model_name = model or os.getenv("FE_CC_TYPHOON_MODEL", "typhoon-ai/typhoon-asr-realtime")

    # Fallback: ใช้ typhoon_asr.transcribe ถ้า NeMo direct ไม่ได้ (โหลดโมเดลทุกครั้ง)
    # หมายเหตุ: typhoon-asr package เขียน processed_{stem}.wav ใน cwd — ใช้ ensure_cc_temp_dir แล้ว chdir (พร้อม lock)
    if _USE_LEGACY:
        temp_dir = ensure_cc_temp_dir()
        with _legacy_cwd_lock:
            orig_cwd = os.getcwd()
            try:
                os.chdir(str(temp_dir))
                result = _typhoon_transcribe_legacy(audio_path, model_name=model_name, with_timestamps=with_timestamps, device=device)
            finally:
                os.chdir(orig_cwd)
        text = (result.get("text") or "").strip()
        timestamps = result.get("timestamps") or []
        segments = [{"start": float(t.get("start", 0)), "end": float(t.get("end", 0)), "text": t.get("word", "")} for t in timestamps] if timestamps else ([{"start": 0.0, "end": 0.0, "text": text}] if text else [])
        return {"text": text, "segments": segments, "provider": "typhoon", "model": model_name}

    try:
        # โหลดโมเดลครั้งเดียว (cached)
        asr_model = _get_typhoon_model(model_name, device)

        # เตรียม audio
        processed_path, audio_duration = _prepare_audio(audio_path)

        try:
            if with_timestamps:
                hypotheses = asr_model.transcribe(audio=[processed_path], return_hypotheses=True)
                text = (hypotheses[0].text if hypotheses and len(hypotheses) > 0 and hasattr(hypotheses[0], "text") else "") or ""
            else:
                transcriptions = asr_model.transcribe(audio=[processed_path])
                text = (transcriptions[0] if transcriptions else "") or ""

            text = text.strip()

            # สร้าง timestamps (ประมาณการ)
            timestamps: List[Dict] = []
            if with_timestamps and text and audio_duration > 0:
                words = text.split()
                if words:
                    avg_duration = audio_duration / len(words)
                    for i, word in enumerate(words):
                        timestamps.append({
                            "word": word,
                            "start": i * avg_duration,
                            "end": (i + 1) * avg_duration,
                        })

            segments = [
                {"start": ts["start"], "end": ts["end"], "text": ts["word"]}
                for ts in timestamps
            ] if timestamps else ([{"start": 0.0, "end": 0.0, "text": text}] if text else [])

            return {
                "text": text,
                "segments": segments,
                "provider": "typhoon",
                "model": model_name,
            }
        finally:
            if os.path.exists(processed_path):
                try:
                    os.remove(processed_path)
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"[TyPhoon ASR] Transcription failed: {e}")
        raise
