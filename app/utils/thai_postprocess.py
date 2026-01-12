"""
Thai Text Postprocessing
สำหรับปรับปรุงข้อความภาษาไทยหลัง transcription
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Mapping table สำหรับคำเพี้ยนยอดฮิต (domain-specific)
# Format: {คำเพี้ยน: คำที่ถูกต้อง}
THAI_WORD_FIXES = {
    # คำราชการ/ศัพท์เฉพาะ
    "จุม": "จดจำ",
    "แห่งร้างพระเม": "แห่งราชการ",
    "รอบอสติ": "รับผิดชอบ",
    "พูด้วย": "พร้อมด้วย",
    "พร้อร": "พร้อม",
    "ความรับ": "ความรับผิดชอบ",
    # เพิ่มเติมตามความต้องการ
}

def normalize_thai_text(text: str) -> str:
    """
    Normalize ข้อความภาษาไทย
    - ลบช่องว่างซ้ำ
    - normalize วรรณยุกต์/สระ
    - แปลงอักขระแปลกให้เป็นมาตรฐาน
    """
    if not text:
        return text
    
    # ลบช่องว่างซ้ำ
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Normalize วรรณยุกต์/สระ (ถ้ามีปัญหา)
    # TODO: เพิ่ม logic สำหรับ normalize วรรณยุกต์ถ้าจำเป็น
    
    return text


def fix_common_words(text: str, word_fixes: Optional[Dict[str, str]] = None) -> str:
    """
    แก้คำเพี้ยนยอดฮิตด้วย mapping table
    
    Args:
        text: ข้อความที่ต้องการแก้
        word_fixes: Dictionary ของ {คำเพี้ยน: คำที่ถูกต้อง}
    
    Returns:
        ข้อความที่แก้แล้ว
    """
    if not text or not word_fixes:
        return text
    
    # รวม word_fixes ที่ส่งมา + default fixes
    all_fixes = {**THAI_WORD_FIXES, **(word_fixes or {})}
    
    # แก้คำทีละคำ (ใช้ word boundary เพื่อไม่ให้แก้ผิด)
    for wrong_word, correct_word in all_fixes.items():
        # ใช้ word boundary เพื่อไม่ให้แก้คำที่อยู่ในคำอื่น
        pattern = r'\b' + re.escape(wrong_word) + r'\b'
        if re.search(pattern, text):
            text = re.sub(pattern, correct_word, text)
            logger.debug(f"🔧 Fixed word: '{wrong_word}' → '{correct_word}'")
    
    return text


def segment_thai_text(text: str) -> str:
    """
    ตัดคำภาษาไทยด้วย PyThaiNLP (ถ้ามี)
    
    Args:
        text: ข้อความที่ต้องการตัดคำ
    
    Returns:
        ข้อความที่ตัดคำแล้ว (หรือข้อความเดิมถ้าไม่มี PyThaiNLP)
    """
    try:
        from pythainlp import word_tokenize
        from pythainlp.tokenize import Tokenizer
        
        # ใช้ newmm tokenizer
        tokens = word_tokenize(text, engine="newmm")
        
        # รวม tokens ด้วยช่องว่าง
        segmented = " ".join(tokens)
        
        logger.debug(f"🔤 Thai word segmentation: {len(tokens)} tokens")
        return segmented
        
    except ImportError:
        # ไม่มี PyThaiNLP → return ข้อความเดิม
        logger.debug("⚠️ PyThaiNLP not available, skipping word segmentation")
        return text
    except Exception as e:
        logger.warning(f"⚠️ Error in Thai word segmentation: {e}")
        return text


def postprocess_thai_text(
    text: str,
    normalize: bool = True,
    fix_words: bool = True,
    word_segmentation: bool = False,
    word_fixes: Optional[Dict[str, str]] = None
) -> str:
    """
    Postprocess ข้อความภาษาไทย (รวมทุกขั้นตอน)
    
    Args:
        text: ข้อความที่ต้องการ postprocess
        normalize: เปิด normalize (ลบช่องว่างซ้ำ, etc.)
        fix_words: เปิดการแก้คำเพี้ยน
        word_segmentation: เปิดการตัดคำ (ต้องมี PyThaiNLP)
        word_fixes: Dictionary สำหรับแก้คำเพิ่มเติม
    
    Returns:
        ข้อความที่ postprocess แล้ว
    """
    if not text:
        return text
    
    result = text
    
    # 1. Normalize
    if normalize:
        result = normalize_thai_text(result)
    
    # 2. Fix common words
    if fix_words:
        result = fix_common_words(result, word_fixes)
    
    # 3. Word segmentation (optional)
    if word_segmentation:
        result = segment_thai_text(result)
    
    return result
