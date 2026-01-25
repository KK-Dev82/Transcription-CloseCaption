#!/usr/bin/env python3
"""
สคริปต์สำหรับตรวจสอบว่า text ที่ส่งผ่าน WebSocket มีการ strip จริงหรือไม่
โดยการตรวจสอบ logs และแสดงตัวอย่าง text ที่ส่งออกไป
"""

import re
import sys
from pathlib import Path

def check_text_stripping_in_logs(log_file: str):
    """ตรวจสอบ logs ว่ามี text ที่มี leading/trailing spaces หรือไม่"""
    
    log_path = Path(log_file)
    if not log_path.exists():
        print(f"❌ Log file not found: {log_file}")
        return
    
    print(f"📋 Checking log file: {log_file}")
    print("=" * 80)
    
    # Patterns สำหรับหา text ใน logs
    patterns = [
        r'Text:\s*"([^"]+)"',
        r'Text:\s*([^\n]+)',
        r'"text":\s*"([^"]+)"',
        r'Text\s*\(stripped\):\s*([^\n]+)',
    ]
    
    lines_with_text = []
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            # หา lines ที่มี "Preparing to send" หรือ "Sent.*final"
            if 'Preparing to send' in line or 'Sent.*final' in line or 'final caption event' in line.lower():
                # เก็บ context (5 lines หลัง)
                context_lines = []
                for i in range(5):
                    try:
                        next_line = f.readline()
                        if next_line:
                            context_lines.append((line_num + i + 1, next_line.strip()))
                    except:
                        break
                
                # ตรวจสอบ text ใน context
                for ctx_line_num, ctx_line in context_lines:
                    for pattern in patterns:
                        matches = re.findall(pattern, ctx_line, re.IGNORECASE)
                        for match in matches:
                            text = match.strip()
                            if text:
                                # ตรวจสอบว่ามี leading/trailing spaces หรือไม่
                                has_leading = text != text.lstrip()
                                has_trailing = text != text.rstrip()
                                
                                if has_leading or has_trailing:
                                    print(f"⚠️  Line {ctx_line_num}: Found text with spaces!")
                                    print(f"   Original: {repr(text)}")
                                    print(f"   Leading spaces: {has_leading}, Trailing spaces: {has_trailing}")
                                    print(f"   Stripped: {repr(text.strip())}")
                                    print()
                                else:
                                    print(f"✅ Line {ctx_line_num}: Text is properly stripped")
                                    print(f"   Text: {repr(text[:50])}..." if len(text) > 50 else f"   Text: {repr(text)}")
                                    print()
                                
                                lines_with_text.append((ctx_line_num, text, has_leading or has_trailing))
    
    if not lines_with_text:
        print("ℹ️  No text found in logs matching the patterns")
        print("   Try running a transcription job first to generate logs")
    else:
        print(f"\n📊 Summary: Found {len(lines_with_text)} text entries")
        unstripped_count = sum(1 for _, _, has_spaces in lines_with_text if has_spaces)
        if unstripped_count > 0:
            print(f"⚠️  {unstripped_count} entries have leading/trailing spaces")
        else:
            print(f"✅ All {len(lines_with_text)} entries are properly stripped")

if __name__ == "__main__":
    # ตรวจสอบ log file ที่ระบุ หรือใช้ default
    log_file = sys.argv[1] if len(sys.argv) > 1 else "logs/transcription.log.2026-01-20"
    
    check_text_stripping_in_logs(log_file)
