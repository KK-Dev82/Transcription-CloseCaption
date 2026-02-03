"""
Close Caption Configuration - Profile: TH-CC-RT v1
แยก ENV สำหรับ CloseCaption ออกจาก Transcription ปกติ
"""

import os
from typing import Dict, Optional


def get_default_whisper_model() -> str:
    """คืนค่า default whisper model จาก env (raw: อาจเป็น models--org--name หรือ org/name)"""
    return os.getenv("CC_MODEL_SIZE") or os.getenv("WHISPER_MODEL", "small")


def whisper_model_to_display(raw: str) -> str:
    """แปลงค่า model จาก env เป็นรูปแบบแสดง (org/name) สำหรับ API และ frontend"""
    if not raw:
        return raw
    if raw.startswith("models--"):
        parts = raw.replace("models--", "", 1).split("--", 1)
        if len(parts) == 2:
            return f"{parts[0]}/{parts[1]}"
    return raw


def get_default_whisper_model_display() -> str:
    """คืนค่า default whisper model ในรูปแบบแสดง (org/name) สำหรับ API response และ frontend"""
    return whisper_model_to_display(get_default_whisper_model())


class CloseCaptionConfig:
    """
    Configuration สำหรับ Close Caption (Profile: TH-CC-RT v1)
    
    Profile: Small + Overlap + Dedupe + Postprocess
    - Model: small (เร็วกว่า medium แต่ยังแม่น)
    - Overlap: 0.6s (แก้รอยต่อ)
    - Dedupe: ตัดข้อความซ้ำ
    - Postprocess: ปรับปรุงข้อความภาษาไทย
    """
    
    # Model Configuration (ใช้ WHISPER_MODEL เมื่อ CC_MODEL_SIZE ไม่ได้ตั้ง → โมเดลเดียวทั้ง transcription และ close-caption)
    MODEL_SIZE = get_default_whisper_model()
    DEVICE = os.getenv("CC_DEVICE", os.getenv("WHISPER_DEVICE", "auto"))
    COMPUTE_TYPE = os.getenv("CC_COMPUTE_TYPE", "float16")  # float16 สำหรับ GPU
    
    # Chunking Configuration
    CHUNK_HOP_SECONDS = float(os.getenv("CC_CHUNK_HOP", "3.0"))  # 3 วินาที
    CHUNK_OVERLAP_SECONDS = float(os.getenv("CC_CHUNK_OVERLAP", "0.6"))  # 0.6 วินาที overlap
    CHUNK_WINDOW_SECONDS = CHUNK_HOP_SECONDS + CHUNK_OVERLAP_SECONDS  # 3.6 วินาที
    
    # faster-whisper Parameters (Profile TH-CC-RT v1)
    BEAM_SIZE = int(os.getenv("CC_BEAM_SIZE", "3"))  # 3 สำหรับความแม่น (ไม่ใช่ 1)
    TEMPERATURE = float(os.getenv("CC_TEMPERATURE", "0.0"))  # 0.0 สำหรับความนิ่ง
    VAD_FILTER = os.getenv("CC_VAD_FILTER", "true").lower() == "true"  # เปิด VAD
    CONDITION_ON_PREVIOUS_TEXT = os.getenv("CC_CONDITION_ON_PREVIOUS_TEXT", "false").lower() == "true"  # ปิดสำหรับ chunk-based
    NO_SPEECH_THRESHOLD = float(os.getenv("CC_NO_SPEECH_THRESHOLD", "0.6"))
    LOG_PROB_THRESHOLD = float(os.getenv("CC_LOG_PROB_THRESHOLD", "-1.0"))
    
    # Language
    LANGUAGE = os.getenv("CC_LANGUAGE", "th")
    
    # Dedupe Configuration
    DEDUPE_ENABLED = os.getenv("CC_DEDUPE_ENABLED", "true").lower() == "true"
    DEDUPE_MAX_MATCH_LENGTH = int(os.getenv("CC_DEDUPE_MAX_MATCH", "80"))  # ตัวอักษรสูงสุดที่ match
    
    # Postprocess Configuration
    POSTPROCESS_ENABLED = os.getenv("CC_POSTPROCESS_ENABLED", "true").lower() == "true"
    POSTPROCESS_NORMALIZE = os.getenv("CC_POSTPROCESS_NORMALIZE", "true").lower() == "true"
    POSTPROCESS_WORD_SEGMENTATION = os.getenv("CC_POSTPROCESS_WORD_SEG", "true").lower() == "true"
    
    @classmethod
    def get_whisper_params(cls) -> Dict:
        """Get faster-whisper parameters สำหรับ CloseCaption"""
        return {
            "model_size": cls.MODEL_SIZE,
            "device": cls.DEVICE,
            "compute_type": cls.COMPUTE_TYPE,
            "beam_size": cls.BEAM_SIZE,
            "temperature": cls.TEMPERATURE,
            "vad_filter": cls.VAD_FILTER,
            "condition_on_previous_text": cls.CONDITION_ON_PREVIOUS_TEXT,
            "no_speech_threshold": cls.NO_SPEECH_THRESHOLD,
            "log_prob_threshold": cls.LOG_PROB_THRESHOLD,
            "language": cls.LANGUAGE,
        }
    
    @classmethod
    def get_chunk_config(cls) -> Dict:
        """Get chunking configuration"""
        return {
            "hop_seconds": cls.CHUNK_HOP_SECONDS,
            "overlap_seconds": cls.CHUNK_OVERLAP_SECONDS,
            "window_seconds": cls.CHUNK_WINDOW_SECONDS,
        }
    
    @classmethod
    def is_enabled(cls) -> bool:
        """ตรวจสอบว่า CloseCaption mode เปิดใช้งานหรือไม่"""
        return os.getenv("CC_ENABLED", "false").lower() == "true"
    
    @classmethod
    def get_summary(cls) -> str:
        """Get configuration summary"""
        return f"""
Close Caption Config (TH-CC-RT v1):
  Model: {cls.MODEL_SIZE} ({cls.DEVICE}, {cls.COMPUTE_TYPE})
  Chunk: {cls.CHUNK_HOP_SECONDS}s hop, {cls.CHUNK_OVERLAP_SECONDS}s overlap
  Whisper: beam_size={cls.BEAM_SIZE}, temp={cls.TEMPERATURE}, vad={cls.VAD_FILTER}
  Dedupe: {cls.DEDUPE_ENABLED} (max_match={cls.DEDUPE_MAX_MATCH_LENGTH})
  Postprocess: {cls.POSTPROCESS_ENABLED} (normalize={cls.POSTPROCESS_NORMALIZE}, word_seg={cls.POSTPROCESS_WORD_SEGMENTATION})
"""
