"""
NeMo Typhoon ASR Provider
ใช้ typhoon-asr (NeMo FastConformer) สำหรับ Transcription จากไฟล์
รองรับการสลับกับ faster-whisper ผ่าน WHISPER_PROVIDER

- WHISPER_PROVIDER=nemo-typhoon → ใช้ NeMo Typhoon ASR
- WHISPER_PROVIDER=faster-whisper → ใช้ faster-whisper (เดิม)
"""

import os
import logging
import asyncio
import time
from typing import Dict, Optional

from .base_provider import WhisperProvider, TranscriptionResult

logger = logging.getLogger(__name__)

# Lazy import - typhoon-asr อาจไม่ได้ติดตั้ง
_TYPHOON_AVAILABLE = False
try:
    from app.services.typhoon_asr_service import transcribe_audio, is_typhoon_available
    _TYPHOON_AVAILABLE = is_typhoon_available()
except ImportError:
    pass


def _looks_like_typhoon_model(model_name: str) -> bool:
    """ตรวจสอบว่า model name เป็น NeMo/Typhoon (ไม่ใช่ whisper)"""
    if not model_name:
        return False
    m = model_name.lower()
    return "typhoon" in m or "nemo" in m or "fastconformer" in m


class NeMoTyphoonProvider(WhisperProvider):
    """
    NeMo Typhoon ASR Provider
    ใช้ typhoon-asr (NeMo FastConformer) สำหรับภาษาไทย — เหมาะสำหรับ Transcription จากไฟล์
    """

    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.provider_name = "nemo-typhoon"

        if not _TYPHOON_AVAILABLE:
            raise ImportError(
                "typhoon-asr / NeMo is not installed. "
                "Install with: pip install typhoon-asr (or use requirements.txt)"
            )

        # Config สำหรับ file transcription (แยกจาก FE Live Caption)
        self.default_model = (
            (config or {}).get("model")
            or os.getenv("TRANSCRIPTION_TYPHOON_MODEL")
            or os.getenv("FE_CC_TYPHOON_MODEL", "typhoon-ai/typhoon-asr-realtime")
        )
        self.device = (
            (config or {}).get("device")
            or os.getenv("TRANSCRIPTION_TYPHOON_DEVICE")
            or os.getenv("FE_CC_TYPHOON_DEVICE", "auto")
        )

        logger.info(
            f"✅ NeMoTyphoonProvider initialized (model: {self.default_model}, device: {self.device})"
        )

    async def transcribe(
        self,
        audio_path: str,
        language: str = "th",
        model_size: str = None,
        initial_prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio file using NeMo Typhoon ASR.

        Args:
            audio_path: Path to audio file
            language: Language (Typhoon เน้นภาษาไทย — ค่าใช้สำหรับ logging)
            model_size: Model name (ถ้าเป็น whisper model จะใช้ default แทน)
            initial_prompt: Not supported by Typhoon — ignored

        Returns:
            TranscriptionResult
        """
        # ใช้ model_size เฉพาะเมื่อเป็น typhoon/nemo model — มิฉะนั้นใช้ default (จาก env)
        # ป้องกันการส่ง whisper model name เข้ามาเมื่อ API ใช้ WHISPER_MODEL เป็น default
        model = self.default_model
        if model_size and _looks_like_typhoon_model(model_size):
            model = model_size
        start_time = time.time()

        # typhoon_asr_service.transcribe_audio เป็น sync — รันใน thread pool
        def _run_transcribe():
            return transcribe_audio(
                audio_path,
                with_timestamps=True,
                device=self.device,
                model=model,
            )

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _run_transcribe)

        processing_time = time.time() - start_time

        text = (result.get("text") or "").strip()
        raw_segments = result.get("segments") or []

        # ปรับ format segments ให้ตรงกับ TranscriptionResult (start/end เป็น float หรือ string)
        segments = []
        for seg in raw_segments:
            start_val = seg.get("start", 0)
            end_val = seg.get("end", 0)
            seg_text = seg.get("text", "").strip()
            if seg_text:
                segments.append(
                    {"start": float(start_val), "end": float(end_val), "text": seg_text}
                )

        if not segments and text:
            # fallback: ใช้ text ทั้งก้อนเป็น segment เดียว
            segments = [{"start": 0.0, "end": 0.0, "text": text}]

        return TranscriptionResult(
            text=text,
            segments=segments,
            language=language,
            provider="nemo-typhoon",
            model=model,
            processing_time=processing_time,
        )

    def health_check(self) -> bool:
        """ตรวจสอบว่า Typhoon ASR พร้อมใช้งาน"""
        if not _TYPHOON_AVAILABLE:
            return False
        try:
            return is_typhoon_available()
        except Exception:
            return False
