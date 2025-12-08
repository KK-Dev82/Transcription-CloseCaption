"""
Prompt Builder - สร้าง initial_prompt จาก Dictionary words
สำหรับส่งให้กับ Whisper เพื่อเพิ่มความแม่นยำ
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Service สำหรับสร้าง initial_prompt จาก Dictionary words
    """
    
    # Common context phrases สำหรับสร้าง prompt
    COMMON_PHRASES = [
        "การประชุม",
        "สมาชิกวุฒิสภา",
        "ประเด็น",
        "การพิจารณา",
        "ร่างกฎหมาย",
        "วาระ",
        "เรื่อง",
        "รายงาน",
        "สรุป",
    ]
    
    # Context templates (สำหรับสร้าง prompt ตัวอย่าง)
    CONTEXT_TEMPLATES = [
        "{words}",
        "การประชุม {words}",
        "{words} ประเด็นการพิจารณา",
        "การประชุม {words} ประเด็น",
    ]
    
    def __init__(self):
        logger.info("📝 PromptBuilder initialized")
    
    def build_initial_prompt(
        self,
        dictionary_words: List[str],
        context: Optional[str] = None,
        max_words: int = 50,
        include_common_phrases: bool = True
    ) -> Optional[str]:
        """
        สร้าง initial_prompt จาก Dictionary words
        
        Args:
            dictionary_words: รายการคำศัพท์จาก Dictionary
            context: Context เพิ่มเติม (optional)
            max_words: จำนวนคำสูงสุดใน prompt (default: 50)
            include_common_phrases: รวม common phrases หรือไม่ (default: True)
        
        Returns:
            Optional[str]: initial_prompt string หรือ None ถ้าไม่มีคำ
        
        Example:
            prompt = prompt_builder.build_initial_prompt(
                dictionary_words=["วุฒิสภา", "สมาชิก", "ร่างกฎหมาย"],
                context="การประชุม",
                max_words=50
            )
            # Result: "การประชุม สมาชิกวุฒิสภา ประเด็น การพิจารณาร่างกฎหมาย..."
        """
        if not dictionary_words:
            logger.debug("⚠️ No dictionary words provided, returning None")
            return None
        
        # จำกัดจำนวนคำ
        words = dictionary_words[:max_words]
        
        # รวม common phrases (ถ้าเปิดใช้งาน)
        if include_common_phrases:
            # เพิ่ม common phrases ที่ยังไม่มีใน words
            for phrase in self.COMMON_PHRASES:
                if phrase not in words:
                    words.insert(0, phrase)
                    if len(words) >= max_words:
                        break
        
        # สร้าง prompt จาก words
        # วิธีที่ 1: ใช้ common phrases + dictionary words
        prompt_parts = []
        
        # เพิ่ม context ถ้ามี
        if context:
            prompt_parts.append(context)
        
        # เพิ่ม words (รวมเป็นประโยคตัวอย่าง)
        # ใช้คำศัพท์เฉพาะ + common phrases เพื่อสร้างตัวอย่างประโยค
        prompt_text = " ".join(words[:max_words])
        
        # ถ้ามี context, รวมเข้าไป
        if context and prompt_text:
            prompt_text = f"{context} {prompt_text}"
        
        # จำกัดความยาว (Whisper ต้องการ prompt สั้นๆ ประมาณ 50-100 คำ)
        # Split และเอาเฉพาะส่วนแรก
        words_list = prompt_text.split()
        if len(words_list) > max_words:
            words_list = words_list[:max_words]
            prompt_text = " ".join(words_list)
        
        logger.info(
            f"📝 Built initial_prompt with {len(words_list)} words "
            f"(from {len(dictionary_words)} dictionary words)"
        )
        
        return prompt_text if prompt_text.strip() else None
    
    def build_simple_prompt(self, dictionary_words: List[str], max_words: int = 30) -> Optional[str]:
        """
        สร้าง prompt แบบง่าย (แค่คำศัพท์ต่อกัน)
        
        Args:
            dictionary_words: รายการคำศัพท์
            max_words: จำนวนคำสูงสุด (default: 30)
        
        Returns:
            Optional[str]: prompt string หรือ None
        """
        if not dictionary_words:
            return None
        
        words = dictionary_words[:max_words]
        prompt = " ".join(words)
        
        logger.debug(f"📝 Built simple prompt with {len(words)} words")
        
        return prompt if prompt.strip() else None
    
    def build_contextual_prompt(
        self,
        dictionary_words: List[str],
        context_type: str = "meeting",
        max_words: int = 50
    ) -> Optional[str]:
        """
        สร้าง prompt แบบมี context (เช่น การประชุม, การบรรยาย)
        
        Args:
            dictionary_words: รายการคำศัพท์
            context_type: ประเภท context ("meeting", "lecture", "discussion", etc.)
            max_words: จำนวนคำสูงสุด (default: 50)
        
        Returns:
            Optional[str]: prompt string หรือ None
        """
        # Context templates ตามประเภท
        context_map = {
            "meeting": "การประชุม",
            "lecture": "การบรรยาย",
            "discussion": "การอภิปราย",
            "session": "การประชุม",
            "conference": "การประชุม",
        }
        
        context = context_map.get(context_type, "การประชุม")
        
        return self.build_initial_prompt(
            dictionary_words=dictionary_words,
            context=context,
            max_words=max_words,
            include_common_phrases=True
        )

