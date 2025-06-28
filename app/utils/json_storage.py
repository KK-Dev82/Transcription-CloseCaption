import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class JSONStorage:
    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
        # สร้างโฟลเดอร์ย่อย
        (self.storage_dir / "transcriptions").mkdir(exist_ok=True)
        (self.storage_dir / "captions").mkdir(exist_ok=True)
        (self.storage_dir / "videos").mkdir(exist_ok=True)
        (self.storage_dir / "metadata").mkdir(exist_ok=True)
    
    def save_transcription(self, task_id: str, transcription_data: Dict) -> str:
        """บันทึกข้อมูล transcription"""
        file_path = self.storage_dir / "transcriptions" / f"{task_id}.json"
        
        # เพิ่ม metadata
        data = {
            "task_id": task_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "file_path": transcription_data.get("file_path"),
            "language": transcription_data.get("language"),
            "total_duration": transcription_data.get("total_duration"),
            "chunks": transcription_data.get("chunks", []),
            "full_text": transcription_data.get("full_text", ""),
            "status": transcription_data.get("status", "completed")
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"บันทึก transcription: {file_path}")
        return str(file_path)
    
    def save_caption(self, task_id: str, caption_data: Dict) -> str:
        """บันทึกข้อมูล caption"""
        file_path = self.storage_dir / "captions" / f"{task_id}.json"
        
        # เพิ่ม metadata
        data = {
            "task_id": task_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "file_path": caption_data.get("file_path"),
            "language": caption_data.get("language"),
            "subtitle_format": caption_data.get("subtitle_format"),
            "segments": caption_data.get("segments", []),
            "subtitle_content": caption_data.get("subtitle_content", ""),
            "status": caption_data.get("status", "completed")
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"บันทึก caption: {file_path}")
        return str(file_path)
    
    def save_video_task(self, task_id: str, video_data: Dict) -> str:
        """บันทึกข้อมูล video task"""
        file_path = self.storage_dir / "videos" / f"{task_id}.json"
        
        # เพิ่ม metadata
        data = {
            "task_id": task_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "type": video_data.get("type"),
            "status": video_data.get("status"),
            "input_file": video_data.get("input_file"),
            "input_files": video_data.get("input_files"),
            "output_file": video_data.get("output_file"),
            "output_format": video_data.get("output_format"),
            "quality": video_data.get("quality"),
            "start_time": video_data.get("start_time"),
            "end_time": video_data.get("end_time"),
            "width": video_data.get("width"),
            "height": video_data.get("height"),
            "operations": video_data.get("operations"),
            "results": video_data.get("results"),
            "error_message": video_data.get("error_message"),
            "completed_at": video_data.get("completed_at")
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"บันทึก video task: {file_path}")
        return str(file_path)
    
    def load_transcription(self, task_id: str) -> Optional[Dict]:
        """โหลดข้อมูล transcription"""
        file_path = self.storage_dir / "transcriptions" / f"{task_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการโหลด transcription {task_id}: {e}")
            return None
    
    def load_caption(self, task_id: str) -> Optional[Dict]:
        """โหลดข้อมูล caption"""
        file_path = self.storage_dir / "captions" / f"{task_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการโหลด caption {task_id}: {e}")
            return None
    
    def load_video_task(self, task_id: str) -> Optional[Dict]:
        """โหลดข้อมูล video task"""
        file_path = self.storage_dir / "videos" / f"{task_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการโหลด video task {task_id}: {e}")
            return None
    
    def search_transcription(self, task_id: str, query: str, 
                           case_sensitive: bool = False) -> List[Dict]:
        """ค้นหาข้อความใน transcription"""
        transcription = self.load_transcription(task_id)
        if not transcription:
            return []
        
        results = []
        query_pattern = query if case_sensitive else query.lower()
        
        for chunk in transcription.get("chunks", []):
            chunk_text = chunk.get("text", "")
            search_text = chunk_text if case_sensitive else chunk_text.lower()
            
            if query_pattern in search_text:
                # หาตำแหน่งของคำค้นหา
                matches = []
                if case_sensitive:
                    start_pos = 0
                    while True:
                        pos = search_text.find(query_pattern, start_pos)
                        if pos == -1:
                            break
                        matches.append(pos)
                        start_pos = pos + 1
                else:
                    start_pos = 0
                    while True:
                        pos = search_text.find(query_pattern, start_pos)
                        if pos == -1:
                            break
                        matches.append(pos)
                        start_pos = pos + 1
                
                result = {
                    "start_time": chunk.get("start_time"),
                    "end_time": chunk.get("end_time"),
                    "text": chunk_text,
                    "confidence": chunk.get("confidence"),
                    "query": query,
                    "match_positions": matches,
                    "highlighted_text": self._highlight_text(chunk_text, query, matches)
                }
                results.append(result)
        
        return results
    
    def search_all_transcriptions(self, query: str, 
                                case_sensitive: bool = False) -> List[Dict]:
        """ค้นหาข้อความใน transcription ทั้งหมด"""
        all_results = []
        
        # หาไฟล์ transcription ทั้งหมด
        transcription_dir = self.storage_dir / "transcriptions"
        for json_file in transcription_dir.glob("*.json"):
            task_id = json_file.stem
            results = self.search_transcription(task_id, query, case_sensitive)
            
            for result in results:
                result["task_id"] = task_id
                all_results.append(result)
        
        return all_results
    
    def _highlight_text(self, text: str, query: str, positions: List[int]) -> str:
        """ไฮไลท์ข้อความที่ตรงกับคำค้นหา"""
        if not positions:
            return text
        
        # เรียงลำดับตำแหน่งจากมากไปน้อย เพื่อไม่ให้ index ผิดพลาด
        positions.sort(reverse=True)
        
        highlighted = text
        for pos in positions:
            start = pos
            end = pos + len(query)
            highlighted = (
                highlighted[:start] + 
                f"**{highlighted[start:end]}**" + 
                highlighted[end:]
            )
        
        return highlighted
    
    def get_transcription_stats(self, task_id: str) -> Dict:
        """ดึงสถิติของ transcription"""
        transcription = self.load_transcription(task_id)
        if not transcription:
            return {}
        
        chunks = transcription.get("chunks", [])
        total_words = sum(len(chunk.get("text", "").split()) for chunk in chunks)
        total_chars = sum(len(chunk.get("text", "")) for chunk in chunks)
        
        return {
            "task_id": task_id,
            "total_chunks": len(chunks),
            "total_words": total_words,
            "total_characters": total_chars,
            "total_duration": transcription.get("total_duration"),
            "language": transcription.get("language"),
            "average_confidence": sum(
                chunk.get("confidence", 0) for chunk in chunks
            ) / len(chunks) if chunks else 0
        }
    
    def get_video_task_stats(self, task_id: str) -> Dict:
        """ดึงสถิติของ video task"""
        video_task = self.load_video_task(task_id)
        if not video_task:
            return {}
        
        return {
            "task_id": task_id,
            "type": video_task.get("type"),
            "status": video_task.get("status"),
            "input_file": video_task.get("input_file"),
            "output_file": video_task.get("output_file"),
            "output_format": video_task.get("output_format"),
            "quality": video_task.get("quality"),
            "created_at": video_task.get("created_at"),
            "completed_at": video_task.get("completed_at"),
            "error_message": video_task.get("error_message")
        }
    
    def list_all_transcriptions(self) -> List[Dict]:
        """ดึงรายการ transcription ทั้งหมด"""
        transcriptions = []
        transcription_dir = self.storage_dir / "transcriptions"
        
        for json_file in transcription_dir.glob("*.json"):
            task_id = json_file.stem
            stats = self.get_transcription_stats(task_id)
            if stats:
                transcriptions.append(stats)
        
        return transcriptions
    
    def list_all_video_tasks(self) -> List[Dict]:
        """ดึงรายการ video tasks ทั้งหมด"""
        video_tasks = []
        video_dir = self.storage_dir / "videos"
        
        for json_file in video_dir.glob("*.json"):
            task_id = json_file.stem
            stats = self.get_video_task_stats(task_id)
            if stats:
                video_tasks.append(stats)
        
        return video_tasks
    
    def delete_transcription(self, task_id: str) -> bool:
        """ลบ transcription"""
        file_path = self.storage_dir / "transcriptions" / f"{task_id}.json"
        
        if file_path.exists():
            file_path.unlink()
            logger.info(f"ลบ transcription: {task_id}")
            return True
        
        return False
    
    def delete_video_task(self, task_id: str) -> bool:
        """ลบ video task"""
        file_path = self.storage_dir / "videos" / f"{task_id}.json"
        
        if file_path.exists():
            file_path.unlink()
            logger.info(f"ลบ video task: {task_id}")
            return True
        
        return False
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """ลบไฟล์เก่า"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        # ลบ transcription เก่า
        transcription_dir = self.storage_dir / "transcriptions"
        for json_file in transcription_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    created_at = datetime.fromisoformat(data.get("created_at", "1970-01-01T00:00:00"))
                    if created_at.timestamp() < cutoff_time:
                        json_file.unlink()
                        logger.info(f"ลบ transcription เก่า: {json_file.stem}")
            except:
                continue
        
        # ลบ video tasks เก่า
        video_dir = self.storage_dir / "videos"
        for json_file in video_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    created_at = datetime.fromisoformat(data.get("created_at", "1970-01-01T00:00:00"))
                    if created_at.timestamp() < cutoff_time:
                        json_file.unlink()
                        logger.info(f"ลบ video task เก่า: {json_file.stem}")
            except:
                continue 