#!/usr/bin/env python3
"""
ทดสอบ Thai Text Processing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.thai_text_processor import ThaiTextProcessor

def test_thai_processing():
    """ทดสอบการประมวลผลข้อความไทย"""
    
    # สร้าง processor
    processor = ThaiTextProcessor()
    
    # ข้อความทดสอบ
    test_cases = [
        "กลับเรียนครับทั้น ที่ก็รอบครับ สวังไทย สวังกัน สวังมาชิคกูที่สวัง",
        "ลูกฟังโงสากชิ้งตานสีกยอก",
        "ครับว่าไม่ครับได้นะครับมากมากเลย",
        "อย่างไม่ที่อย่างว่าอย่างแล้วก็เพราะว่า",
        "เขาเราไปมาดีแล้วจริงจริงนั้นนะ",
    ]
    
    print("🧪 ทดสอบ Thai Text Processing")
    print("=" * 50)
    
    for i, text in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}:")
        print(f"Original: {text}")
        
        # ประมวลผล
        corrected = processor.correct_text(text)
        confidence = processor.get_confidence_score(text, corrected)
        
        print(f"Corrected: {corrected}")
        print(f"Confidence: {confidence:.3f}")
        print(f"Changed: {'Yes' if text != corrected else 'No'}")
        print("-" * 30)

if __name__ == "__main__":
    test_thai_processing()
