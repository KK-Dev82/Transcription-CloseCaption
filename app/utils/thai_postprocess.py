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


def add_spacing_around_numbers(text: str) -> str:
    """
    เพิ่มเว้นวรรคระหว่างตัวเลขกับข้อความ
    
    ตัวอย่าง:
    - "ราคา100บาท" → "ราคา 100 บาท"
    - "วันที่15มกราคม" → "วันที่ 15 มกราคม"
    """
    if not text:
        return text
    
    # เพิ่มเว้นวรรคก่อนตัวเลข (ถ้ายังไม่มี)
    # Pattern: ตัวอักษรไทย/อังกฤษ + ตัวเลข
    text = re.sub(r'([ก-๙a-zA-Z])(\d)', r'\1 \2', text)
    
    # เพิ่มเว้นวรรคหลังตัวเลข (ถ้ายังไม่มี)
    # Pattern: ตัวเลข + ตัวอักษรไทย/อังกฤษ
    text = re.sub(r'(\d)([ก-๙a-zA-Z])', r'\1 \2', text)
    
    return text


def add_spacing_for_names(text: str) -> str:
    """
    เพิ่มเว้นวรรคระหว่างชื่อจริงกับนามสกุล
    
    ใช้ pattern ที่ระมัดระวังมาก:
    - ชื่อ: 3-5 ตัวอักษร, นามสกุล: 3-6 ตัวอักษร
    - ต้องอยู่ที่จุดเริ่มต้นของข้อความเท่านั้น (เพื่อหลีกเลี่ยงการ match คำอื่น)
    - ตรวจสอบว่าไม่ใช่คำที่รู้จัก
    
    ตัวอย่าง:
    - "สมชายใจดี" → "สมชาย ใจดี"
    - "มานะมีสุข" → "มานะ มีสุข"
    
    หมายเหตุ: ฟังก์ชันนี้จะทำงานเฉพาะกรณีที่ชัดเจนมากๆ เท่านั้น
    เพื่อหลีกเลี่ยงการเว้นวรรคผิด (เช่น "วันที่" ไม่ควรเป็น "วัน ที่")
    """
    if not text:
        return text
    
    # คำที่รู้จักที่ไม่ควรเว้นวรรค
    # ถ้ามีคำเหล่านี้อยู่แล้ว → ไม่ต้องเว้นวรรค
    common_words = [
        "วันที่", "เวลา", "ราคา", "จำนวน", "สวัสดี", "ขอบคุณ",
        "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
        "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
    ]
    
    # Pattern สำหรับชื่อ-นามสกุลภาษาไทย
    # ใช้เฉพาะเมื่อ:
    # 1. อยู่ที่จุดเริ่มต้นของข้อความเท่านั้น (^) เพื่อหลีกเลี่ยงการ match คำอื่น
    # 2. ชื่อ: 3-4 ตัวอักษร (เช่น สมชาย, มานะ, วิไล) - ใช้ non-greedy เพื่อ match น้อยที่สุด
    # 3. นามสกุล: 3-6 ตัวอักษร (เช่น ใจดี, มีสุข, วัฒนา)
    # 4. ตามด้วยช่องว่าง, จุดสิ้นสุด, หรืออักขระที่ไม่ใช่ตัวอักษรไทย
    
    # Pattern: ^ = เริ่มต้นข้อความเท่านั้น
    #          ([ก-๙]{3,4}?) = ชื่อ 3-4 ตัว (non-greedy: match น้อยที่สุด)
    #          ([ก-๙]{3,6}) = นามสกุล 3-6 ตัว
    #          (?=\s|$|[^ก-๙]) = ตามด้วยช่องว่าง/จุดสิ้นสุด/อักขระอื่น
    
    def replace_name(match):
        name = match.group(1)    # ชื่อ
        surname = match.group(2)  # นามสกุล
        full_name = name + surname
        
        # ตรวจสอบว่าไม่ใช่คำที่รู้จัก
        for word in common_words:
            if word in full_name or full_name in word:
                # ถ้าเป็นคำที่รู้จัก → ไม่เว้นวรรค
                return match.group(0)
        
        # ตรวจสอบว่าไม่ใช่คำที่รู้จักในส่วนของชื่อหรือนามสกุล
        # เช่น "มกราคม" ไม่ควรถูกตัดเป็น "มกร าคม"
        for word in common_words:
            if name in word or surname in word:
                return match.group(0)
        
        # ตรวจสอบว่าไม่ใช่คำที่รู้จักที่เริ่มต้นด้วยชื่อหรือนามสกุล
        # เช่น "มีนาคม" ไม่ควรถูกตัดเป็น "มี นาคม"
        for word in common_words:
            if word.startswith(name) or word.startswith(surname):
                return match.group(0)
        
        return f"{name} {surname}"
    
    # ใช้ pattern ที่ระมัดระวัง: ต้องอยู่ที่จุดเริ่มต้นของข้อความเท่านั้น
    # ใช้ non-greedy matching สำหรับชื่อ (3-4 ตัว) เพื่อ match น้อยที่สุด
    pattern = r'^([ก-๙]{3,4}?)([ก-๙]{3,6})(?=\s|$|[^ก-๙])'
    text = re.sub(pattern, replace_name, text)
    
    return text


def improve_thai_spacing(text: str, use_tokenization: bool = True) -> str:
    """
    ปรับปรุงการเว้นวรรคในข้อความภาษาไทย
    - เพิ่มเว้นวรรคระหว่างตัวเลขกับข้อความ
    - เพิ่มเว้นวรรคระหว่างคำที่ติดกัน (ใช้ PyThaiNLP ถ้ามี)
    
    Args:
        text: ข้อความที่ต้องการปรับปรุง
        use_tokenization: ใช้ PyThaiNLP tokenization หรือไม่ (default: True)
                         ✅ ใช้ tokenization เพื่อเว้นวรรคระหว่างคำที่ติดกัน
    
    Returns:
        ข้อความที่ปรับปรุงแล้ว
    """
    if not text:
        return text
    
    result = text
    
    # 1. เพิ่มเว้นวรรคระหว่างตัวเลขกับข้อความ (ทำก่อน tokenization)
    result = add_spacing_around_numbers(result)
    
    # 2. ใช้ PyThaiNLP เพื่อตัดคำและเพิ่มเว้นวรรค (ถ้ามีและเปิดใช้งาน)
    # ✅ ใช้ tokenization เพื่อเว้นวรรคระหว่างคำที่ติดกัน (เช่น "สมชายใจดี" → "สมชาย ใจดี")
    if use_tokenization:
        try:
            from pythainlp import word_tokenize
            
            # Tokenize เพื่อแยกคำ
            # ใช้ engine="newmm" ซึ่งเป็น default และแม่นยำ
            tokens = word_tokenize(result, engine="newmm")
            
            # รวม tokens ด้วยช่องว่าง
            result = " ".join(tokens)
            
            logger.debug(f"🔤 Improved spacing with tokenization: {len(tokens)} tokens")
            
        except ImportError:
            # ไม่มี PyThaiNLP → ใช้ regex pattern แทน (เฉพาะตัวเลข)
            logger.debug("⚠️ PyThaiNLP not available, using regex for spacing (numbers only)")
            
        except Exception as e:
            logger.warning(f"⚠️ Error in tokenization: {e}")
            # ถ้าเกิด error → ใช้ผลลัพธ์จากขั้นตอนก่อนหน้า
    
    return result


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
    improve_spacing: bool = True,  # ✅ เพิ่ม option สำหรับปรับปรุงการเว้นวรรค
    word_fixes: Optional[Dict[str, str]] = None,
    fuzzy_match: bool = False,
) -> str:
    """
    Postprocess ข้อความภาษาไทย (รวมทุกขั้นตอน)
    
    Args:
        text: ข้อความที่ต้องการ postprocess
        normalize: เปิด normalize (ลบช่องว่างซ้ำ, etc.)
        fix_words: เปิดการแก้คำเพี้ยน
        word_segmentation: เปิดการตัดคำ (ต้องมี PyThaiNLP)
        improve_spacing: เปิดการปรับปรุงการเว้นวรรค (ตัวเลข, ชื่อ-นามสกุล, คำติดกัน)
        word_fixes: Dictionary สำหรับแก้คำเพิ่มเติม
        fuzzy_match: เปิด Fuzzy Match (ชื่อคน + คำศัพท์จาก data/fuzzy_match/)
    
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
    
    # 2.5. Fuzzy Match (ชื่อคน + คำศัพท์)
    if fuzzy_match:
        try:
            from app.services.fuzzy_match_service import apply_fuzzy_match
            result = apply_fuzzy_match(result)
        except Exception as e:
            logger.warning(f"⚠️ Fuzzy match error: {e}")
    
    # 3. Improve spacing (ตัวเลข, คำติดกัน)
    if improve_spacing:
        # ✅ ใช้ tokenization เพื่อเว้นวรรคระหว่างคำที่ติดกัน
        # tokenization จะช่วยเว้นวรรคชื่อ-นามสกุลและคำอื่นๆ อัตโนมัติ
        use_tokenization = True  # ใช้ tokenization เสมอเมื่อ improve_spacing เปิดอยู่
        result = improve_thai_spacing(result, use_tokenization=use_tokenization)
        # Normalize อีกครั้งหลังปรับ spacing (ลบช่องว่างซ้ำ)
        if normalize:
            result = normalize_thai_text(result)
    
    # 4. Word segmentation (optional - ถ้าไม่ได้ใช้ improve_spacing)
    if word_segmentation and not improve_spacing:
        result = segment_thai_text(result)
    
    return result
