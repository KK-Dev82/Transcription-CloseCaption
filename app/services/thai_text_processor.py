"""
Thai Text Post-Processor
สำหรับแก้ไขและปรับปรุงความแม่นยำของข้อความภาษาไทยจาก Whisper
"""

import re
import logging
from typing import Dict, List, Tuple
from pythainlp import word_tokenize, spell
from pythainlp.corpus import thai_words
from pythainlp.spell import correct
from pythainlp.util import normalize
from pythainlp.tokenize import word_tokenize as thai_word_tokenize
import requests

logger = logging.getLogger(__name__)

class ThaiTextProcessor:
    def __init__(self):
        # โหลดพจนานุกรมภาษาไทย
        self.thai_words_set = set(thai_words())
        
        # คำที่มักจะแปลงผิด (Common mistakes from Whisper)
        self.common_corrections = {
            # คำที่เสียงคล้าย
            "ลูก": "ฟัง",
            "โงสาก": "โลก", 
            "ชิ้ง": "สิ่ง",
            "ตาน": "ต่าง",
            "สีก": "ซึ่ง",
            "ยอก": "ยาก",
            "งสา": "โลก",
            "ท้องงสา": "โลก",
            "เพียงสำจุด": "เพียงแค่",
            
            # คำผิดทั่วไป
            "ครับว่า": "ครับ ว่า",
            "ไม่ครับ": "ไหม ครับ",
            "ได้นะครับ": "ได้ นะครับ",
            "มากมากเลย": "มาก ๆ เลย",
            "เลยนะครับ": "เลย นะครับ",
            
            # คำที่ต่อกันผิด
            "อย่างไม่": "อย่าง ไม่",
            "ที่อย่าง": "ที่ อย่าง",
            "ว่าอย่าง": "ว่า อย่าง",
            "แล้วก็": "แล้ว ก็",
            "เพราะว่า": "เพราะ ว่า",
            
            # การออกเสียงที่คล้าย
            "เขาเรา": "เขา เรา",
            "ไปมา": "ไป มา", 
            "ดีแล้ว": "ดี แล้ว",
            "จริงจริง": "จริง ๆ",
            "นั้นนะ": "นั้น นะ",
            
            # เพิ่มคำที่พบในตัวอย่าง
            "กลับเรียน": "กลับ เรียน",
            "ทั้น": "นั้น",
            "รอบ": "รอบ",
            "สวัง": "สวัสดี",
            "มาชิคกู": "มาชิก",
        }
        
        # รูปแบบ regex สำหรับแก้ไข
        self.patterns = [
            # แก้คำซ้ำที่ไม่จำเป็น
            (r'\b(\w+)\s+\1\b', r'\1'),  # คำซ้ำ เช่น "ที่ ที่" → "ที่"
            
            # แก้การเว้นวรรคผิด
            (r'([ก-ฮ])([ก-ฮ]{2,})', r'\1 \2'),  # คำต่อกันยาวเกินไป
            
            # แก้ปัญหาคำไม่มีเสียงวรรณยุกต์
            (r'([ก-ฮ])([่-๋])([ก-ฮ])', r'\1\2 \3'),
            
            # แก้คำอุทาน
            (r'\bอ๋อ\b', 'อ่อ'),
            (r'\bเอ่อ\b', 'เอ่อ'),
            (r'\bอืม\b', 'อืม'),
        ]
        
        logger.info("Thai Text Processor initialized with dictionary")
    
    def correct_text(self, text: str) -> str:
        """แก้ไขข้อความภาษาไทย"""
        if not text or not text.strip():
            return text
            
        # ขั้นตอนที่ 0: ปรับปรุงข้อความให้เป็นมาตรฐาน
        corrected = normalize(text)
        
        # ขั้นตอนที่ 1: แทนที่คำที่ผิดทั่วไป
        for wrong, correct_word in self.common_corrections.items():
            corrected = corrected.replace(wrong, correct_word)
        
        # ขั้นตอนที่ 2: ใช้ regex patterns
        for pattern, replacement in self.patterns:
            corrected = re.sub(pattern, replacement, corrected)
        
        # ขั้นตอนที่ 3: ตรวจสอบคำผิดด้วย PyThaiNLP
        corrected = self._spell_check(corrected)
        
        # ขั้นตอนที่ 4: ปรับปรุงการเว้นวรรค
        corrected = self._fix_spacing(corrected)
        
        # ขั้นตอนที่ 5: ใช้ word tokenization เพื่อปรับปรุงการแยกคำ
        corrected = self._improve_word_segmentation(corrected)
        
        return corrected.strip()
    
    def _spell_check(self, text: str) -> str:
        """ตรวจสอบการสะกดด้วย PyThaiNLP"""
        try:
            # แยกคำด้วย PyThaiNLP
            tokens = thai_word_tokenize(text, engine='newmm')
            corrected_tokens = []
            
            for token in tokens:
                if len(token.strip()) > 1 and token not in self.thai_words_set:
                    # ลองแก้ไขคำผิด
                    corrected_word = correct(token)
                    if corrected_word != token:
                        logger.debug(f"Spell correction: {token} → {corrected_word}")
                        corrected_tokens.append(corrected_word)
                    else:
                        corrected_tokens.append(token)
                else:
                    corrected_tokens.append(token)
            
            return ''.join(corrected_tokens)
            
        except Exception as e:
            logger.error(f"Spell check error: {e}")
            return text
    
    def _fix_spacing(self, text: str) -> str:
        """ปรับปรุงการเว้นวรรค"""
        # เว้นวรรคหลังเครื่องหมายวรรคตอน
        text = re.sub(r'([.!?])([ก-ฮ])', r'\1 \2', text)
        
        # เว้นวรรคก่อนคำอุทาน
        text = re.sub(r'([ก-ฮ])(ครับ|ค่ะ|นะ|หรือ)', r'\1 \2', text)
        
        # ลบช่องว่างเกิน
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def _improve_word_segmentation(self, text: str) -> str:
        """ปรับปรุงการแยกคำด้วย PyThaiNLP"""
        try:
            # ใช้ PyThaiNLP word tokenization
            tokens = thai_word_tokenize(text, engine='newmm')
            
            # รวมคำที่แยกแล้วด้วยช่องว่าง
            improved_text = ' '.join(tokens)
            
            # ปรับปรุงการเว้นวรรค
            improved_text = re.sub(r'\s+', ' ', improved_text)
            
            return improved_text
            
        except Exception as e:
            logger.error(f"Word segmentation error: {e}")
            return text
    
    def get_confidence_score(self, original: str, corrected: str) -> float:
        """คำนวณคะแนนความมั่นใจในการแก้ไข"""
        if original == corrected:
            return 1.0
            
        # นับจำนวนคำที่ถูกต้องในพจนานุกรม
        original_tokens = thai_word_tokenize(original, engine='newmm')
        corrected_tokens = thai_word_tokenize(corrected, engine='newmm')
        
        original_correct = sum(1 for token in original_tokens if token in self.thai_words_set)
        corrected_correct = sum(1 for token in corrected_tokens if token in self.thai_words_set)
        
        if len(corrected_tokens) == 0:
            return 0.0
            
        improvement = (corrected_correct - original_correct) / len(corrected_tokens)
        base_score = corrected_correct / len(corrected_tokens)
        
        return min(1.0, base_score + improvement * 0.1)
    
    def process_transcription_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """ประมวลผล chunks ทั้งหมด"""
        processed_chunks = []
        
        for chunk in chunks:
            if 'text' in chunk and chunk['text']:
                original_text = chunk['text']
                corrected_text = self.correct_text(original_text)
                confidence = self.get_confidence_score(original_text, corrected_text)
                
                processed_chunk = chunk.copy()
                processed_chunk['text'] = str(corrected_text) if corrected_text is not None else ""
                processed_chunk['original_text'] = original_text
                processed_chunk['correction_confidence'] = confidence
                processed_chunk['was_corrected'] = (original_text != corrected_text)
                
                if processed_chunk['was_corrected']:
                    logger.info(f"Text correction: '{original_text}' → '{corrected_text}' (confidence: {confidence:.3f})")
                
                processed_chunks.append(processed_chunk)
            else:
                processed_chunks.append(chunk)
        
        return processed_chunks
    
    def add_custom_corrections(self, corrections: Dict[str, str]):
        """เพิ่มการแก้ไขแบบกำหนดเอง"""
        self.common_corrections.update(corrections)
        logger.info(f"Added {len(corrections)} custom corrections")
    
    def get_statistics(self, chunks: List[Dict]) -> Dict:
        """สถิติการแก้ไข"""
        total_chunks = len(chunks)
        corrected_chunks = sum(1 for chunk in chunks if chunk.get('was_corrected', False))
        avg_confidence = sum(chunk.get('correction_confidence', 1.0) for chunk in chunks) / max(1, total_chunks)
        
        return {
            'total_chunks': total_chunks,
            'corrected_chunks': corrected_chunks,
            'correction_rate': corrected_chunks / max(1, total_chunks),
            'average_confidence': avg_confidence
        }


# Factory function
def create_thai_processor() -> ThaiTextProcessor:
    """สร้าง Thai Text Processor instance"""
    return ThaiTextProcessor()
