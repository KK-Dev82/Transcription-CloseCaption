"""
Text Deduplication Utility
สำหรับตัดข้อความซ้ำจาก overlap chunks
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def dedupe_text(
    new_text: str,
    last_emitted_text: Optional[str] = None,
    max_match_length: int = 80
) -> str:
    """
    ตัดข้อความซ้ำจาก overlap
    
    Args:
        new_text: ข้อความใหม่ที่จะ emit
        last_emitted_text: ข้อความที่ส่งออกล่าสุด
        max_match_length: ความยาวสูงสุดที่ match (ตัวอักษร)
    
    Returns:
        ข้อความใหม่ที่ตัดส่วนซ้ำออกแล้ว
    """
    if not last_emitted_text or not new_text:
        return new_text
    
    # Normalize: ลบช่องว่างซ้ำ, แปลงเป็น lowercase สำหรับ matching
    def normalize_for_match(text: str) -> str:
        # ลบช่องว่างซ้ำ, แปลงเป็น lowercase
        return " ".join(text.lower().split())
    
    normalized_new = normalize_for_match(new_text)
    normalized_last = normalize_for_match(last_emitted_text)
    
    # หาส่วนที่ซ้ำกัน (จากท้ายของ last_emitted_text กับต้นของ new_text)
    # เริ่มจาก match ที่ยาวที่สุด (ไม่เกิน max_match_length)
    best_match_length = 0
    
    # ตรวจสอบทุกความยาวที่เป็นไปได้ (จากสั้นไปยาว)
    for match_len in range(1, min(len(normalized_new), len(normalized_last), max_match_length) + 1):
        # เอา match_len ตัวอักษรสุดท้ายของ last_emitted_text
        last_suffix = normalized_last[-match_len:]
        # เอา match_len ตัวอักษรแรกของ new_text
        new_prefix = normalized_new[:match_len]
        
        if last_suffix == new_prefix:
            best_match_length = match_len
    
    if best_match_length > 0:
        # ตัดส่วนที่ซ้ำออก (best_match_length ตัวอักษรแรก)
        # แต่ต้องคำนึงถึง word boundary ด้วย
        
        # หา word boundary ที่ใกล้ที่สุด
        # เริ่มจาก best_match_length แล้วหา space หรือ word boundary
        original_new = new_text
        for i in range(best_match_length, len(original_new)):
            if i >= len(original_new):
                break
            # ถ้าเจอ space หรือ punctuation → ใช้เป็น boundary
            if original_new[i] in " \n\t.,!?;:":
                # ตัดตั้งแต่ i+1 เป็นต้นไป (ข้าม space/punctuation)
                deduped = original_new[i+1:].lstrip()
                logger.debug(f"🔍 Dedupe: matched {best_match_length} chars, removed '{original_new[:i+1]}', kept '{deduped[:50]}...'")
                return deduped
        
        # ถ้าไม่เจอ word boundary → ตัดตรง best_match_length
        deduped = original_new[best_match_length:].lstrip()
        logger.debug(f"🔍 Dedupe: matched {best_match_length} chars, removed '{original_new[:best_match_length]}', kept '{deduped[:50]}...'")
        return deduped
    
    # ไม่มีส่วนซ้ำ
    return new_text


def dedupe_segments(
    new_segments: list,
    last_emitted_text: Optional[str] = None,
    max_match_length: int = 80
) -> list:
    """
    Dedupe segments โดยตัดส่วนที่ซ้ำกับ last_emitted_text
    
    Args:
        new_segments: List of segments ใหม่
        last_emitted_text: ข้อความที่ส่งออกล่าสุด
        max_match_length: ความยาวสูงสุดที่ match
    
    Returns:
        List of segments ที่ตัดส่วนซ้ำออกแล้ว
    """
    if not new_segments or not last_emitted_text:
        return new_segments
    
    # รวมข้อความจาก segments
    new_text = " ".join(seg.get("text", "") for seg in new_segments)
    
    # Dedupe ข้อความ
    deduped_text = dedupe_text(new_text, last_emitted_text, max_match_length)
    
    if deduped_text == new_text:
        # ไม่มีส่วนซ้ำ → return segments เดิม
        return new_segments
    
    # มีส่วนซ้ำ → ต้องปรับ segments
    # วิธีง่าย: หา segment แรกที่ยังอยู่ใน deduped_text
    # แล้ว return segments ตั้งแต่ segment นั้นเป็นต้นไป
    
    # รวมข้อความจาก segments เพื่อหา index
    accumulated_text = ""
    start_index = 0
    
    for i, seg in enumerate(new_segments):
        seg_text = seg.get("text", "")
        accumulated_text += seg_text + " "
        
        # ตรวจสอบว่า accumulated_text ยังอยู่ใน deduped_text หรือไม่
        if deduped_text.startswith(accumulated_text.strip()):
            # ยังอยู่ใน deduped_text → ยังไม่ต้องตัด
            continue
        else:
            # ไม่อยู่ใน deduped_text → เริ่มจาก segment นี้
            start_index = i
            break
    
    # Return segments ตั้งแต่ start_index
    return new_segments[start_index:]
