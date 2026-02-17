"""
Diarization Service - pyannote Speaker Diarization (Offline-first)
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    os.environ.setdefault("PYANNOTE_METRICS_ENABLED", "0")

    # PyTorch 2.6+: torch.load ใช้ weights_only=True โดยค่าเริ่มต้น ทำให้โหลด pyannote checkpoint เก่าไม่ได้
    # Monkey-patch lightning_fabric._load ให้ใช้ weights_only=False เมื่อโหลดจาก trusted source
    try:
        import lightning_fabric.utilities.cloud_io as _cloud_io
        _orig_load = _cloud_io._load

        def _patched_load(path_or_url, map_location=None, weights_only=None):
            if weights_only is None:
                weights_only = False
            return _orig_load(path_or_url, map_location=map_location, weights_only=weights_only)

        _cloud_io._load = _patched_load
    except Exception:
        pass

    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as e:
        logger.error(f"pyannote.audio not installed: {e}")
        raise ImportError("pyannote.audio required. pip install pyannote.audio==3.3.2") from e

    hf_token = (os.getenv("PYANNOTE_HF_TOKEN") or os.getenv("HF_PYANNOTE_TOKEN") or "").strip()
    model_dir = os.getenv("PYANNOTE_MODEL_DIR", "").strip()

    # โหลดจาก local config.yaml ได้ (config ยังอ้าง segmentation/embedding จาก HF — ต้องมี token)
    config_path = None
    if model_dir:
        p = Path(model_dir)
        if p.is_dir():
            yaml_path = p / "config.yaml"
        else:
            yaml_path = p
        if yaml_path.exists():
            config_path = str(yaml_path)

    if config_path and hf_token:
        logger.info(f"Loading pyannote from local config: {config_path}")
        _pipeline = Pipeline.from_pretrained(config_path, use_auth_token=hf_token)
    elif hf_token:
        logger.info("Loading pyannote from HuggingFace (speaker-diarization-3.1)")
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
        )
    else:
        raise ValueError(
            "PYANNOTE_HF_TOKEN หรือ HF_PYANNOTE_TOKEN จำเป็นสำหรับ pyannote diarization"
        )

    if torch.cuda.is_available():
        _pipeline.to(torch.device("cuda"))
    return _pipeline


def diarize(audio_path: str, **kwargs) -> List[Dict]:
    """รัน diarization คืนค่า [{"start", "end", "speaker"}, ...]"""
    pipeline = _get_pipeline()
    diarization = pipeline(audio_path, **kwargs)
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({"start": float(turn.start), "end": float(turn.end), "speaker": str(speaker)})
    logger.info(f"Diarization: {len(segments)} segments")
    return segments


def get_speaker_for_segment(seg_start: float, seg_end: float, diarization_segments: List[Dict]) -> Optional[str]:
    if not diarization_segments:
        return None
    seg_mid = (seg_start + seg_end) / 2
    best_speaker, best_overlap = None, 0.0
    for d in diarization_segments:
        o_start, o_end = max(seg_start, d["start"]), min(seg_end, d["end"])
        if o_end > o_start and (o_end - o_start) > best_overlap:
            best_overlap = o_end - o_start
            best_speaker = d["speaker"]
    if best_speaker:
        return best_speaker
    for d in diarization_segments:
        if d["start"] <= seg_mid <= d["end"]:
            return d["speaker"]
    return min(diarization_segments, key=lambda x: min(abs(seg_mid - x["start"]), abs(seg_mid - x["end"])))["speaker"]


def build_text_with_speaker_markers(segments: List[Dict], diarization_segments: List[Dict]) -> str:
    if not diarization_segments:
        return " ".join((s.get("text") or "").strip() for s in segments if (s.get("text") or "").strip()).strip()
    result, last_speaker = [], None
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        spk = get_speaker_for_segment(seg.get("start", 0), seg.get("end", 0), diarization_segments)
        if spk and spk != last_speaker:
            if last_speaker is not None:
                result.append(" /newSpeaker ")
            last_speaker = spk
        result.append(text)
    return " ".join(result).strip()
