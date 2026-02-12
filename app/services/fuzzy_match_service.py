"""
Fuzzy Match Service
ใช้สำหรับแก้ไขชื่อคนและคำศัพท์ที่ ASR สะกดผิด (post-processing)
"""

import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Default paths (relative to project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_NAMES_PATH = _PROJECT_ROOT / "data" / "fuzzy_match" / "names.txt"
_DEFAULT_VOCABULARY_PATH = _PROJECT_ROOT / "data" / "fuzzy_match" / "vocabulary.txt"
_DEFAULT_PREFIXES_PATH = _PROJECT_ROOT / "data" / "fuzzy_match" / "name_prefixes.txt"


def _load_word_list(path: Path, desc: str) -> List[str]:
    """โหลดรายการคำจากไฟล์ (UTF-8, ข้าม comment และบรรทัดว่าง)"""
    if not path or not path.exists():
        return []
    words = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Normalize ช่องว่างซ้ำ
                line = re.sub(r"\s+", " ", line)
                if line:
                    words.append(line)
        logger.info(f"📚 {desc}: loaded {len(words)} items from {path}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to load {path}: {e}")
    return words


class FuzzyMatchService:
    """
    Fuzzy Match สำหรับแก้ชื่อคนและคำศัพท์ที่ ASR สะกดผิด
    - ชื่อ: ใช้ Jaro-Winkler (เหมาะกับชื่อคน)
    - คำศัพท์: ใช้ Levenshtein ratio
    """

    def __init__(
        self,
        names_path: Optional[Path] = None,
        vocabulary_path: Optional[Path] = None,
        prefixes_path: Optional[Path] = None,
        name_threshold: float = 0.85,
        vocab_threshold: float = 0.85,
    ):
        """
        Args:
            names_path: path to names.txt
            vocabulary_path: path to vocabulary.txt
            prefixes_path: path to name_prefixes.txt
            name_threshold: คะแนนต่ำสุดสำหรับ match ชื่อ (0-1)
            vocab_threshold: คะแนนต่ำสุดสำหรับ match คำศัพท์ (0-1)
        """
        self.names_path = Path(names_path) if names_path else _DEFAULT_NAMES_PATH
        self.vocabulary_path = Path(vocabulary_path) if vocabulary_path else _DEFAULT_VOCABULARY_PATH
        self.prefixes_path = Path(prefixes_path) if prefixes_path else _DEFAULT_PREFIXES_PATH
        self.name_threshold = name_threshold
        self.vocab_threshold = vocab_threshold

        self._names: List[str] = []
        self._vocabulary: List[str] = []
        self._prefixes: Set[str] = set()
        self._reload()

    def _reload(self) -> None:
        """โหลดข้อมูลจากไฟล์"""
        self._names = _load_word_list(self.names_path, "Names")
        self._vocabulary = _load_word_list(self.vocabulary_path, "Vocabulary")
        prefixes_raw = _load_word_list(self.prefixes_path, "Name prefixes")
        self._prefixes = {p.strip() for p in prefixes_raw if p.strip()}

    def apply(self, text: str) -> str:
        """
        แก้ไขข้อความด้วย Fuzzy Match
        - แก้คำศัพท์ (vocabulary) ก่อน
        - แก้ชื่อคน (names) ตาม

        Args:
            text: ข้อความจาก ASR

        Returns:
            ข้อความที่แก้แล้ว
        """
        if not text or not text.strip():
            return text
        if not self._names and not self._vocabulary:
            return text

        try:
            from rapidfuzz import fuzz
            from rapidfuzz.distance import JaroWinkler
            jaro_winkler = JaroWinkler
        except ImportError:
            logger.warning("⚠️ rapidfuzz not installed, skipping fuzzy match")
            return text

        result = text
        # 1. แก้คำศัพท์: ใช้ sliding window หา substring ที่ match vocabulary
        result = self._apply_vocabulary_replacements(result, fuzz)
        # 2. แก้ชื่อ: ใช้ Jaro-Winkler + tokenize (เหมาะกับชื่อคน)
        result = self._apply_name_replacements(result, fuzz, jaro_winkler)

        return result

    def _apply_vocabulary_replacements(self, text: str, fuzz) -> str:
        """แทนที่คำศัพท์ที่สะกดผิดด้วย sliding window"""
        if not self._vocabulary:
            return text
        vocab_sorted = sorted([v for v in self._vocabulary if len(v) >= 2], key=len, reverse=True)
        result = text
        for correct_word in vocab_sorted:
            replaced = True
            while replaced:
                replaced = False
                # ลองเฉพาะ window ที่ความยาวใกล้เคียงคำที่ถูก (ลดจำนวน iteration)
                lo = max(2, len(correct_word) - 2)
                hi = min(len(result), len(correct_word) + 2)
                for wlen in range(hi, lo - 1, -1):
                    for start in range(len(result) - wlen + 1):
                        sub = result[start : start + wlen]
                        if not sub.strip():
                            continue
                        score = fuzz.ratio(sub, correct_word) / 100.0
                        if score >= self.vocab_threshold:
                            result = result[:start] + correct_word + result[start + wlen :]
                            replaced = True
                            break
                    if replaced:
                        break
        return result

    def _apply_name_replacements(self, text: str, fuzz, jaro_winkler=None) -> str:
        """แทนที่ชื่อที่สะกดผิด (ใช้ tokenize)"""
        if not self._names:
            return text
        tokens = self._tokenize(text)
        if not tokens:
            return text

        corrected = []
        i = 0
        max_ngram = 4

        while i < len(tokens):
            best_match: Optional[str] = None
            best_len = 0
            for n in range(min(max_ngram, len(tokens) - i), 0, -1):
                ngram = " ".join(tokens[i : i + n])
                m = self._fuzzy_match_name(ngram, fuzz, jaro_winkler)
                if m:
                    best_match = m
                    best_len = n
                    break

            if best_match and best_len > 0:
                corrected.append(best_match)
                i += best_len
            else:
                corrected.append(tokens[i])
                i += 1

        return " ".join(corrected)

    def _tokenize(self, text: str) -> List[str]:
        """แยกคำจากข้อความ"""
        try:
            from pythainlp import word_tokenize
            return word_tokenize(text, engine="newmm")
        except ImportError:
            return text.split()

    def _strip_prefix(self, text: str) -> Tuple[str, Optional[str]]:
        """strip คำนำหน้า ถ้ามี → (ชื่อที่ strip แล้ว, prefix ที่ strip ออก)"""
        for prefix in sorted(self._prefixes, key=len, reverse=True):
            if text.startswith(prefix) and len(text) > len(prefix):
                rest = text[len(prefix):].strip()
                if rest:
                    return rest, prefix
        return text, None

    def _fuzzy_match_name(self, token: str, fuzz, jaro_winkler=None) -> Optional[str]:
        """Fuzzy match ชื่อ (ใช้ Jaro-Winkler - เหมาะกับชื่อคน เพราะให้ความสำคัญตัวอักษรต้นคำ)"""
        if not self._names or not token or len(token) < 2:
            return None

        # Strip prefix ก่อน match
        to_match, _ = self._strip_prefix(token)
        if not to_match:
            return None

        best_score = 0.0
        best_match: Optional[str] = None

        for name in self._names:
            if not name:
                continue
            # Jaro-Winkler: ให้ความสำคัญกับ prefix (สมชาย vs สมไชย, Korrakang vs Korakarn)
            if jaro_winkler is not None:
                score = jaro_winkler.similarity(to_match, name)
            else:
                score = fuzz.ratio(to_match, name) / 100.0
            if score >= self.name_threshold and score > best_score:
                best_score = score
                best_match = name

        return best_match

    def _fuzzy_match_vocab(self, token: str, fuzz) -> Optional[str]:
        """Fuzzy match คำศัพท์ (ใช้ ratio)"""
        if not self._vocabulary or not token or len(token) < 2:
            return None

        best_score = 0.0
        best_match: Optional[str] = None

        for vocab in self._vocabulary:
            if not vocab:
                continue
            score = fuzz.ratio(token, vocab) / 100.0
            if score >= self.vocab_threshold and score > best_score:
                best_score = score
                best_match = vocab

        return best_match


# Singleton สำหรับลดการโหลดซ้ำ
_fuzzy_match_service: Optional[FuzzyMatchService] = None


def get_fuzzy_match_service() -> FuzzyMatchService:
    """คืนค่า singleton FuzzyMatchService"""
    global _fuzzy_match_service
    if _fuzzy_match_service is None:
        names_path = os.getenv("FUZZY_MATCH_NAMES_PATH")
        vocab_path = os.getenv("FUZZY_MATCH_VOCABULARY_PATH")
        prefixes_path = os.getenv("FUZZY_MATCH_NAME_PREFIXES_PATH")

        def _resolve(p: str) -> Path:
            path = Path(p)
            if not path.is_absolute():
                path = _PROJECT_ROOT / path
            return path

        _fuzzy_match_service = FuzzyMatchService(
            names_path=_resolve(names_path) if names_path else None,
            vocabulary_path=_resolve(vocab_path) if vocab_path else None,
            prefixes_path=_resolve(prefixes_path) if prefixes_path else None,
            name_threshold=float(os.getenv("FUZZY_MATCH_NAME_THRESHOLD", "0.85")),
            vocab_threshold=float(os.getenv("FUZZY_MATCH_VOCAB_THRESHOLD", "0.85")),
        )
    return _fuzzy_match_service


# จำกัดความยาวต่อ chunk เพื่อไม่ให้ Fuzzy ช้าเกินไปสำหรับข้อความยาวมาก (เช่น 20+ chunks)
_FUZZY_MAX_CHARS_PER_CHUNK = int(os.getenv("FUZZY_MATCH_MAX_CHARS_PER_CHUNK", "8000"))


def apply_fuzzy_match(text: str) -> str:
    """
    ฟังก์ชัน helper สำหรับ apply fuzzy match
    ใช้เมื่อ fuzzy match เปิดใช้งาน
    สำหรับข้อความยาว (>8000 chars) จะแบ่งประมวลผลเป็น chunks เพื่อความเร็ว
    """
    if not text or not text.strip():
        return text
    try:
        svc = get_fuzzy_match_service()
        if len(text) <= _FUZZY_MAX_CHARS_PER_CHUNK:
            return svc.apply(text)
        # ข้อความยาว: แบ่ง chunk เพื่อลดเวลาประมวลผล (vocabulary sliding window ช้าสำหรับข้อความยาวมาก)
        result_parts = []
        pos = 0
        while pos < len(text):
            end = min(pos + _FUZZY_MAX_CHARS_PER_CHUNK, len(text))
            chunk = text[pos:end]
            corrected = svc.apply(chunk)
            result_parts.append(corrected)
            pos = end
        return "".join(result_parts)
    except Exception as e:
        logger.warning(f"⚠️ Fuzzy match error: {e}")
        return text
