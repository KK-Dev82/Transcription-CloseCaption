"""
Caption Search Service
สำหรับค้นหาข้อความจาก Close Caption และหาเวลาที่บันทึก
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import json
import re

from ...utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class CaptionSearchService:
    """Service สำหรับค้นหาข้อความจาก Close Caption"""
    
    def __init__(self):
        self.json_storage = JSONStorage()
    
    def search_captions(self, query: str, stream_id: Optional[str] = None, 
                      case_sensitive: bool = False) -> List[Dict]:
        """
        ค้นหาข้อความจาก captions
        
        Args:
            query: ข้อความที่ต้องการค้นหา
            stream_id: ID ของ stream (ถ้าไม่ระบุจะค้นหาทั้งหมด)
            case_sensitive: ระบุว่าต้องการค้นหาแบบ case-sensitive หรือไม่
        
        Returns:
            List of matches with timestamp information
        """
        results = []
        
        try:
            # ถ้าระบุ stream_id ให้ค้นหาเฉพาะ stream นั้น
            if stream_id:
                caption_data = self.json_storage.load_caption(stream_id)
                if caption_data:
                    matches = self._search_in_caption(caption_data, query, stream_id, case_sensitive)
                    results.extend(matches)
            else:
                # ค้นหาทั้งหมด (ต้องมี method สำหรับ list all captions)
                # สำหรับตอนนี้จะค้นหาเฉพาะ stream_id ที่ระบุ
                pass
            
            # เรียงตามเวลา
            results.sort(key=lambda x: x.get("start_time", 0))
            
            logger.info(f"🔍 Found {len(results)} matches for query: '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error searching captions: {e}")
            return []
    
    def _search_in_caption(self, caption_data: Dict, query: str, 
                          stream_id: str, case_sensitive: bool) -> List[Dict]:
        """ค้นหาใน caption data"""
        matches = []
        
        # ดึง segments
        segments = caption_data.get("segments", [])
        
        # สร้าง regex pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(query), flags)
        
        # ค้นหาในแต่ละ segment
        for segment in segments:
            text = segment.get("text", "")
            
            # ค้นหาว่ามี query ใน text หรือไม่
            if pattern.search(text):
                match_info = {
                    "stream_id": stream_id,
                    "start_time": segment.get("start", 0),
                    "end_time": segment.get("end", 0),
                    "text": text,
                    "matched_text": query,
                    "timestamp_formatted": self._format_timestamp(segment.get("start", 0)),
                    "duration": segment.get("end", 0) - segment.get("start", 0)
                }
                matches.append(match_info)
        
        return matches
    
    def search_by_time_range(self, stream_id: str, start_time: float, 
                            end_time: float) -> List[Dict]:
        """
        ค้นหา captions ในช่วงเวลาที่กำหนด
        
        Args:
            stream_id: ID ของ stream
            start_time: เวลาเริ่มต้น (วินาที)
            end_time: เวลาสิ้นสุด (วินาที)
        
        Returns:
            List of segments in the time range
        """
        try:
            caption_data = self.json_storage.load_caption(stream_id)
            if not caption_data:
                return []
            
            segments = caption_data.get("segments", [])
            
            # กรอง segments ที่อยู่ในช่วงเวลา
            matching_segments = []
            for segment in segments:
                seg_start = segment.get("start", 0)
                seg_end = segment.get("end", 0)
                
                # ตรวจสอบว่ามี overlap กับช่วงเวลาที่กำหนดหรือไม่
                if not (seg_end < start_time or seg_start > end_time):
                    matching_segments.append({
                        "stream_id": stream_id,
                        "start_time": seg_start,
                        "end_time": seg_end,
                        "text": segment.get("text", ""),
                        "timestamp_formatted": self._format_timestamp(seg_start),
                        "duration": seg_end - seg_start
                    })
            
            return matching_segments
            
        except Exception as e:
            logger.error(f"❌ Error searching by time range: {e}")
            return []
    
    def get_caption_timeline(self, stream_id: str) -> List[Dict]:
        """
        ดึง timeline ของ captions
        
        Args:
            stream_id: ID ของ stream
        
        Returns:
            List of all segments with timeline information
        """
        try:
            caption_data = self.json_storage.load_caption(stream_id)
            if not caption_data:
                return []
            
            segments = caption_data.get("segments", [])
            
            timeline = []
            for segment in segments:
                timeline.append({
                    "start_time": segment.get("start", 0),
                    "end_time": segment.get("end", 0),
                    "text": segment.get("text", ""),
                    "timestamp_formatted": self._format_timestamp(segment.get("start", 0)),
                    "duration": segment.get("end", 0) - segment.get("start", 0)
                })
            
            return timeline
            
        except Exception as e:
            logger.error(f"❌ Error getting caption timeline: {e}")
            return []
    
    def _format_timestamp(self, seconds: float) -> str:
        """แปลงวินาทีเป็นรูปแบบ timestamp (HH:MM:SS)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"

