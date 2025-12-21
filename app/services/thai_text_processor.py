"""
Thai Text Post-Processor
สำหรับแก้ไขและปรับปรุงความแม่นยำของข้อความภาษาไทยจาก Whisper
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
import requests
import importlib

logger = logging.getLogger(__name__)

# Optional PyThaiNLP imports (may fail if tzdata is missing)
PYTHAINLP_AVAILABLE = False
_pythainlp_modules = {}

def _try_import_pythainlp():
    """Try to import PyThaiNLP modules lazily"""
    global PYTHAINLP_AVAILABLE, _pythainlp_modules
    
    if PYTHAINLP_AVAILABLE:
        return True
    
    try:
        # Try importing pythainlp module first
        pythainlp = importlib.import_module('pythainlp')
        _pythainlp_modules['pythainlp'] = pythainlp
        
        # Import submodules
        _pythainlp_modules['corpus'] = importlib.import_module('pythainlp.corpus')
        _pythainlp_modules['spell'] = importlib.import_module('pythainlp.spell')
        _pythainlp_modules['util'] = importlib.import_module('pythainlp.util')
        _pythainlp_modules['tokenize'] = importlib.import_module('pythainlp.tokenize')
        
        PYTHAINLP_AVAILABLE = True
        logger.info("✅ PyThaiNLP loaded successfully")
        return True
    except (ImportError, ModuleNotFoundError, Exception) as e:
        logger.warning(f"⚠️ PyThaiNLP not available: {e}. Using fallback mode (basic text processing only).")
        PYTHAINLP_AVAILABLE = False
        return False

# Fallback functions (used when PyThaiNLP is not available)
def normalize(text: str) -> str:
    """Normalize text (fallback: just strip)"""
    if PYTHAINLP_AVAILABLE and 'util' in _pythainlp_modules:
        return _pythainlp_modules['util'].normalize(text)
    return text.strip()

def thai_word_tokenize(text: str, engine: str = 'newmm') -> List[str]:
    """Tokenize Thai text (fallback: split by spaces)"""
    if PYTHAINLP_AVAILABLE and 'tokenize' in _pythainlp_modules:
        return _pythainlp_modules['tokenize'].word_tokenize(text, engine=engine)
    # Simple word tokenization by spaces
    return text.split()

def correct(word: str) -> str:
    """Correct spelling (fallback: return as-is)"""
    if PYTHAINLP_AVAILABLE and 'spell' in _pythainlp_modules:
        return _pythainlp_modules['spell'].correct(word)
    return word

def thai_words() -> List[str]:
    """Get Thai words dictionary (fallback: empty list)"""
    if PYTHAINLP_AVAILABLE and 'corpus' in _pythainlp_modules:
        try:
            return _pythainlp_modules['corpus'].thai_words()
        except:
            return []
    return []

class ThaiTextProcessor:
    def __init__(self):
        # ลอง import PyThaiNLP (lazy import)
        _try_import_pythainlp()
        
        # โหลดพจนานุกรมภาษาไทย (ถ้ามี PyThaiNLP)
        if PYTHAINLP_AVAILABLE:
            try:
                self.thai_words_set = set(thai_words())
            except Exception as e:
                logger.warning(f"⚠️ Failed to load Thai words dictionary: {e}. Using empty set.")
                self.thai_words_set = set()
        else:
            self.thai_words_set = set()
        
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
    
    def _fix_abnormal_repetition(self, text: str) -> str:
        """
        แก้ไขการซ้ำคำผิดปกติ เช่น "การการการ..." → "การ"
        ตรวจจับและลบการซ้ำคำที่มากเกินไป (มากกว่า 3 ครั้งติดกัน)
        """
        if not text or len(text.strip()) < 6:  # ขนาดเล็กเกินไป ไม่น่าจะมีการซ้ำผิดปกติ
            return text
        
        corrected = text
        
        # ขั้นตอนที่ 1: แก้ไขการซ้ำคำที่ไม่มีช่องว่าง (เช่น "การการการการ...")
        # Pattern: จับคำไทย 1-6 ตัวอักษรที่ซ้ำกันติดกัน 4+ ครั้ง
        # ใช้ greedy matching เพื่อจับคำที่ยาวที่สุดก่อน
        pattern_no_space = r'([ก-ฮ]{1,6})\1{3,}'
        
        def replace_repetition_no_space(match):
            repeated_word = match.group(1)
            full_match = match.group(0)
            repeat_count = len(full_match) // len(repeated_word)
            
            # ถ้าซ้ำมากกว่า 10 ครั้ง ถือว่าเป็นความผิดปกติจาก transcription → ลดเหลือ 1 ครั้ง
            if repeat_count > 10:
                logger.warning(
                    f"⚠️ Detected abnormal word repetition (no spaces): "
                    f"'{repeated_word}' repeated {repeat_count} times "
                    f"(length: {len(full_match)} chars). "
                    f"Replacing with single occurrence."
                )
                return repeated_word
            elif repeat_count > 3:
                logger.info(
                    f"ℹ️ Detected word repetition (no spaces): "
                    f"'{repeated_word}' repeated {repeat_count} times. "
                    f"Reducing to 2 occurrences."
                )
                return repeated_word * 2
            else:
                return full_match
        
        # รันหลายรอบเพื่อจับคำซ้ำที่อาจมีหลายกลุ่ม
        max_iterations = 5
        for i in range(max_iterations):
            old_corrected = corrected
            corrected = re.sub(pattern_no_space, replace_repetition_no_space, corrected)
            if corrected == old_corrected:
                break  # ไม่มีการเปลี่ยนแปลงแล้ว
        
        # ขั้นตอนที่ 2: แก้ไขการซ้ำคำที่มีช่องว่าง (เช่น "การ การ การ...")
        # ตรวจสอบว่ามีคำซ้ำติดกันมากเกินไปหรือไม่
        words = corrected.split()
        # ลด threshold จาก 20 เป็น 3 เพื่อตรวจจับคำซ้ำได้เร็วขึ้น
        if len(words) >= 3:
            consecutive_repeats = 0
            prev_word = None
            max_consecutive = 0
            
            for word in words:
                if word == prev_word:
                    consecutive_repeats += 1
                    max_consecutive = max(max_consecutive, consecutive_repeats)
                else:
                    consecutive_repeats = 1
                prev_word = word
            
            # ถ้ามีคำซ้ำติดกันมากกว่า 5 ครั้ง ถือว่าผิดปกติ
            if max_consecutive > 5:
                logger.warning(
                    f"⚠️ Detected abnormal consecutive word repetition: "
                    f"same word repeated {max_consecutive} times consecutively. "
                    f"Text length: {len(corrected)} chars, Word count: {len(words)}"
                )
                # ลดการซ้ำติดกันเหลือ 2 ครั้ง
                deduplicated_words = []
                prev_word = None
                repeat_count = 0
                
                for word in words:
                    if word == prev_word:
                        repeat_count += 1
                        if repeat_count <= 2:  # อนุญาตให้ซ้ำได้ 2 ครั้ง
                            deduplicated_words.append(word)
                    else:
                        repeat_count = 1
                        deduplicated_words.append(word)
                        prev_word = word
                
                corrected = ' '.join(deduplicated_words)
        
        return corrected
    
    def correct_text(self, text: str) -> str:
        """แก้ไขข้อความภาษาไทย"""
        if not text or not text.strip():
            return text
            
        # ขั้นตอนที่ 0: ปรับปรุงข้อความให้เป็นมาตรฐาน
        corrected = normalize(text)
        
        # ขั้นตอนที่ 0.5: แก้ไขการซ้ำคำผิดปกติ (ต้องทำก่อน tokenization)
        corrected = self._fix_abnormal_repetition(corrected)
        
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
        """ตรวจสอบการสะกดด้วย PyThaiNLP (ถ้ามี)"""
        if not PYTHAINLP_AVAILABLE:
            return text  # Skip spell check if PyThaiNLP not available
            
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
        """ปรับปรุงการแยกคำด้วย PyThaiNLP (ถ้ามี)"""
        if not PYTHAINLP_AVAILABLE:
            return text  # Skip word segmentation if PyThaiNLP not available
            
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
        
        if not PYTHAINLP_AVAILABLE:
            # Fallback: simple comparison
            return 0.8 if original != corrected else 1.0
            
        try:
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
        except Exception as e:
            logger.error(f"Confidence score error: {e}")
            return 0.8  # Fallback score
    
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
