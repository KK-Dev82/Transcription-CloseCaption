"""
Thai Text Processing API
สำหรับทดสอบและปรับปรุงความแม่นยำของข้อความภาษาไทย
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging

from ..services.thai_text_processor import create_thai_processor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/thai", tags=["thai-processing"])

class TextCorrectionRequest(BaseModel):
    text: str
    custom_corrections: Optional[Dict[str, str]] = None

class TextCorrectionResponse(BaseModel):
    original_text: str
    corrected_text: str
    was_corrected: bool
    confidence: float
    corrections_applied: List[Dict[str, str]]

class ChunkProcessingRequest(BaseModel):
    chunks: List[Dict]
    custom_corrections: Optional[Dict[str, str]] = None

class ChunkProcessingResponse(BaseModel):
    processed_chunks: List[Dict]
    statistics: Dict
    total_corrections: int

@router.post("/correct-text", response_model=TextCorrectionResponse)
async def correct_thai_text(request: TextCorrectionRequest):
    """แก้ไขข้อความภาษาไทยเดี่ยว"""
    try:
        processor = create_thai_processor()
        
        # เพิ่มการแก้ไขแบบกำหนดเอง
        if request.custom_corrections:
            processor.add_custom_corrections(request.custom_corrections)
        
        original = request.text
        corrected = processor.correct_text(original)
        confidence = processor.get_confidence_score(original, corrected)
        
        # หาคำที่ถูกแก้ไข
        corrections_applied = []
        for wrong, right in processor.common_corrections.items():
            if wrong in original and right in corrected:
                corrections_applied.append({"from": wrong, "to": right})
        
        return TextCorrectionResponse(
            original_text=original,
            corrected_text=corrected,
            was_corrected=(original != corrected),
            confidence=confidence,
            corrections_applied=corrections_applied
        )
        
    except Exception as e:
        logger.error(f"Text correction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-chunks", response_model=ChunkProcessingResponse)
async def process_transcription_chunks(request: ChunkProcessingRequest):
    """ประมวลผล chunks จาก transcription"""
    try:
        processor = create_thai_processor()
        
        # เพิ่มการแก้ไขแบบกำหนดเอง
        if request.custom_corrections:
            processor.add_custom_corrections(request.custom_corrections)
        
        # ประมวลผล chunks
        processed_chunks = processor.process_transcription_chunks(request.chunks)
        statistics = processor.get_statistics(processed_chunks)
        
        total_corrections = sum(1 for chunk in processed_chunks if chunk.get('was_corrected', False))
        
        return ChunkProcessingResponse(
            processed_chunks=processed_chunks,
            statistics=statistics,
            total_corrections=total_corrections
        )
        
    except Exception as e:
        logger.error(f"Chunk processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-corrections")
async def test_common_corrections():
    """ทดสอบการแก้ไขคำผิดทั่วไป"""
    try:
        processor = create_thai_processor()
        
        # ตัวอย่างข้อความที่มีปัญหา
        test_cases = [
            "ทุกคนลูกไม่ครับว่า หาก็เปลี่ยนโงสากขึ้นเป็นแค่เล็กหน่อย",
            "เพียงสำจุดท้องงสา อาจจะทำอะไรเป็นจากเอาเลย",
            "ที่กล้องเดินทำไปเดียวยอก เป็นเป็นว่าชิ้งตานดีสีกก็ได้นะครับ",
            "มากมากเลยนะครับ เพราะว่าเตรียมมากมากเลยนะครับ",
            "จริงจริงแล้วว่า อย่างไม่ได้เจอของ",
        ]
        
        results = []
        for test_text in test_cases:
            corrected = processor.correct_text(test_text)
            confidence = processor.get_confidence_score(test_text, corrected)
            
            results.append({
                "original": test_text,
                "corrected": corrected,
                "was_changed": (test_text != corrected),
                "confidence": confidence
            })
        
        return {
            "test_results": results,
            "total_tests": len(test_cases),
            "corrections_made": sum(1 for r in results if r["was_changed"])
        }
        
    except Exception as e:
        logger.error(f"Test corrections error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dictionary-stats")
async def get_dictionary_statistics():
    """สถิติพจนานุกรมภาษาไทย"""
    try:
        processor = create_thai_processor()
        
        return {
            "thai_words_count": len(processor.thai_words_set),
            "common_corrections_count": len(processor.common_corrections),
            "regex_patterns_count": len(processor.patterns),
            "processor_status": "ready"
        }
        
    except Exception as e:
        logger.error(f"Dictionary stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add-corrections")
async def add_custom_corrections(corrections: Dict[str, str]):
    """เพิ่มการแก้ไขแบบกำหนดเอง"""
    try:
        # บันทึกการแก้ไขแบบกำหนดเองลงไฟล์
        import json
        from pathlib import Path
        
        custom_corrections_file = Path("storage/custom_thai_corrections.json")
        custom_corrections_file.parent.mkdir(exist_ok=True)
        
        # โหลดการแก้ไขที่มีอยู่
        existing_corrections = {}
        if custom_corrections_file.exists():
            with open(custom_corrections_file, 'r', encoding='utf-8') as f:
                existing_corrections = json.load(f)
        
        # เพิ่มการแก้ไขใหม่
        existing_corrections.update(corrections)
        
        # บันทึกกลับ
        with open(custom_corrections_file, 'w', encoding='utf-8') as f:
            json.dump(existing_corrections, f, ensure_ascii=False, indent=2)
        
        return {
            "message": f"เพิ่มการแก้ไข {len(corrections)} รายการสำเร็จ",
            "total_corrections": len(existing_corrections),
            "new_corrections": corrections
        }
        
    except Exception as e:
        logger.error(f"Add corrections error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
