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
        """บันทึกข้อมูล transcription แบบโฟลเดอร์แยก"""
        # สร้างโฟลเดอร์สำหรับ task นี้
        task_dir = self.storage_dir / "transcriptions" / task_id
        task_dir.mkdir(exist_ok=True)
        
        # บันทึกไฟล์หลัก metadata.json
        metadata_path = task_dir / "metadata.json"
        
        # ตรวจสอบไฟล์เดิม เพื่อเก็บข้อมูลเดิมไว้
        existing_data = {}
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except:
                pass
        
        # รวมข้อมูลเดิมกับข้อมูลใหม่
        def _ensure_iso(value):
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, (int, float)):
                try:
                    return datetime.fromtimestamp(value).isoformat()
                except Exception:
                    return None
            return value
        
        # คำนวณ processing_time ถ้ายังไม่มี
        processing_time = transcription_data.get("processing_time") or transcription_data.get("result_time")
        if not processing_time and transcription_data.get("completed_at") and existing_data.get("created_at"):
            try:
                # datetime ถูก import แล้วที่บรรทัด 5 - ไม่ต้อง import ซ้ำ
                created = datetime.fromisoformat(existing_data.get("created_at").replace('Z', '+00:00') if 'Z' in existing_data.get("created_at") else existing_data.get("created_at"))
                completed = datetime.fromisoformat(transcription_data.get("completed_at").replace('Z', '+00:00') if 'Z' in transcription_data.get("completed_at") else transcription_data.get("completed_at"))
                processing_time = (completed - created).total_seconds()
            except Exception:
                processing_time = None
        
        data = {
            "task_id": task_id,
            "created_at": existing_data.get("created_at", datetime.now().isoformat()),
            "start_time": transcription_data.get("start_time") or existing_data.get("start_time") or existing_data.get("created_at", datetime.now().isoformat()),  # Alias
            "updated_at": datetime.now().isoformat(),
            "file_path": transcription_data.get("file_path", existing_data.get("file_path")),
            "file_url": transcription_data.get("file_url", existing_data.get("file_url")),
            "file_name": transcription_data.get("file_name", existing_data.get("file_name")),
            "language": transcription_data.get("language", existing_data.get("language")),
            "total_duration": transcription_data.get("total_duration", existing_data.get("total_duration")),
            "partial_text": transcription_data.get("partial_text", existing_data.get("partial_text")),
            "chunks": transcription_data.get("chunks", existing_data.get("chunks", [])),
            "full_text": transcription_data.get("full_text", existing_data.get("full_text", "")),
            "status": transcription_data.get("status", existing_data.get("status", "pending")),
            "progress": transcription_data.get("progress", existing_data.get("progress", 0)),
            "error_message": transcription_data.get("error_message", existing_data.get("error_message")),
            "completed_at": _ensure_iso(transcription_data.get("completed_at", existing_data.get("completed_at"))),
            "end_time": transcription_data.get("end_time") or _ensure_iso(transcription_data.get("completed_at", existing_data.get("completed_at"))),  # Alias
            "processing_time": processing_time or existing_data.get("processing_time") or existing_data.get("result_time"),  # เวลาที่ใช้ในการประมวลผล (วินาที)
            "result_time": processing_time or existing_data.get("result_time") or existing_data.get("processing_time"),  # Alias
            "job_id": transcription_data.get("job_id", existing_data.get("job_id")),
            "user_id": transcription_data.get("user_id", existing_data.get("user_id")),
            "callback_url": transcription_data.get("callback_url", existing_data.get("callback_url"))
        }
        
        # แปลง progress ให้เป็นตัวเลขเสมอ
        try:
            data["progress"] = int(data.get("progress", 0))
        except Exception:
            data["progress"] = 0
        
        # แปลง total_duration เป็น float ถ้าเป็น string
        total_duration = data.get("total_duration")
        if isinstance(total_duration, str):
            try:
                data["total_duration"] = float(total_duration)
            except ValueError:
                try:
                    data["total_duration"] = float(total_duration.replace(",", "."))
                except ValueError:
                    data["total_duration"] = existing_data.get("total_duration")
        
        # ป้องกันไม่ให้ partial_text เป็น None
        if data.get("partial_text") is None:
            data["partial_text"] = existing_data.get("partial_text")
        
        # บันทึก metadata.json
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # บันทึกไฟล์ข้อความเต็ม (ถ้ามี)
        if data.get("full_text"):
            full_text_path = task_dir / "full_text.txt"
            with open(full_text_path, 'w', encoding='utf-8') as f:
                f.write(data["full_text"])
        
        # บันทึก chunks แยกไฟล์ (ถ้ามี)
        chunks = data.get("chunks", [])
        if chunks:
            chunks_dir = task_dir / "chunks"
            chunks_dir.mkdir(exist_ok=True)
            
            # Filter out None chunks (chunks that haven't been processed yet)
            valid_chunks = [c for c in chunks if c is not None]
            
            # บันทึกไฟล์ full_text.json พร้อม timestamps
            full_json_path = task_dir / "full_text.json"
            with open(full_json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "task_id": task_id,
                    "language": data.get("language"),
                    "total_duration": data.get("total_duration"),
                    "segments": valid_chunks,
                    "full_text": data.get("full_text")
                }, f, ensure_ascii=False, indent=2)
            
            # บันทึกแต่ละ chunk แยกไฟล์ (skip None chunks)
            chunk_file_index = 0
            for i, chunk in enumerate(chunks):
                if chunk is None:
                    continue  # Skip None chunks
                chunk_file_index += 1
                chunk_path = chunks_dir / f"chunk_{chunk_file_index:02d}.json"
                with open(chunk_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "chunk_id": chunk_file_index,
                        "start_time": chunk.get("start_time") if chunk else None,
                        "end_time": chunk.get("end_time") if chunk else None,
                        "text": chunk.get("text", "") if chunk else "",
                        "confidence": chunk.get("confidence") if chunk else None
                    }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"บันทึก transcription: {task_dir}")
        return str(metadata_path)
    
    def save_caption(self, task_id: str, caption_data: Dict) -> str:
        """บันทึกข้อมูล caption แบบโฟลเดอร์แยก"""
        # สร้างโฟลเดอร์สำหรับ task นี้
        task_dir = self.storage_dir / "captions" / task_id
        task_dir.mkdir(exist_ok=True)
        
        # บันทึกไฟล์หลัก metadata.json
        metadata_path = task_dir / "metadata.json"
        
        # ตรวจสอบไฟล์เดิม
        existing_data = {}
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except:
                pass
        
        # รวมข้อมูลเดิมกับข้อมูลใหม่
        data = {
            "task_id": task_id,
            "created_at": existing_data.get("created_at", datetime.now().isoformat()),
            "updated_at": datetime.now().isoformat(),
            "file_path": caption_data.get("file_path", existing_data.get("file_path")),
            "language": caption_data.get("language", existing_data.get("language")),
            "subtitle_format": caption_data.get("subtitle_format", existing_data.get("subtitle_format")),
            "segments": caption_data.get("segments", existing_data.get("segments", [])),
            "subtitle_content": caption_data.get("subtitle_content", existing_data.get("subtitle_content", "")),
            "status": caption_data.get("status", existing_data.get("status", "pending"))
        }
        
        # บันทึก metadata.json
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # บันทึกไฟล์ subtitle ตามรูปแบบ
        subtitle_content = data.get("subtitle_content", "")
        subtitle_format = data.get("subtitle_format", "srt")
        
        if subtitle_content:
            if subtitle_format.lower() == "srt":
                subtitle_path = task_dir / "subtitles.srt"
            elif subtitle_format.lower() == "vtt":
                subtitle_path = task_dir / "subtitles.vtt"
            else:
                subtitle_path = task_dir / f"subtitles.{subtitle_format}"
            
            with open(subtitle_path, 'w', encoding='utf-8') as f:
                f.write(subtitle_content)
        
        # บันทึก segments แยกไฟล์
        segments = data.get("segments", [])
        if segments:
            segments_path = task_dir / "segments.json"
            with open(segments_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "task_id": task_id,
                    "language": data.get("language"),
                    "subtitle_format": data.get("subtitle_format"),
                    "segments": segments
                }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"บันทึก caption: {task_dir}")
        return str(metadata_path)
    
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
        # ลองโหลดจากโฟลเดอร์ใหม่ก่อน
        task_dir = self.storage_dir / "transcriptions" / task_id
        metadata_path = task_dir / "metadata.json"
        
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการโหลด transcription {task_id}: {e}")
        
        # ถ้าไม่มี ลองโหลดจากไฟล์เดิม (backward compatibility)
        old_file_path = self.storage_dir / "transcriptions" / f"{task_id}.json"
        if old_file_path.exists():
            try:
                with open(old_file_path, 'r', encoding='utf-8') as f:
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
    
    def get_transcription(self, task_id: str) -> Optional[Dict]:
        """ดึงข้อมูล transcription แบบเต็ม (รองรับ folder structure)"""
        # วิธีใหม่: อ่านจาก folder structure
        task_dir = self.storage_dir / "transcriptions" / task_id
        metadata_file = task_dir / "metadata.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # เพิ่ม task_id ถ้าไม่มี
                    if 'task_id' not in data:
                        data['task_id'] = task_id
                    return data
            except Exception as e:
                logger.warning(f"ไม่สามารถอ่าน metadata.json สำหรับ {task_id}: {e}")
        
        # วิธีเก่า: อ่านจาก .json file โดยตรง
        file_path = self.storage_dir / "transcriptions" / f"{task_id}.json"
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"ไม่สามารถอ่านไฟล์ {file_path}: {e}")
        
        return None

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
        """ดึงรายการ transcription ทั้งหมด (รองรับ folder structure ใหม่)"""
        transcriptions = []
        transcription_dir = self.storage_dir / "transcriptions"
        
        if not transcription_dir.exists():
            logger.warning(f"Transcription directory does not exist: {transcription_dir}")
            return []
        
        logger.info(f"📂 Listing transcriptions from: {transcription_dir}")
        
        # วิธีใหม่: หา folders แล้วอ่าน metadata.json
        task_folders = [f for f in transcription_dir.iterdir() if f.is_dir()]
        logger.info(f"📁 Found {len(task_folders)} task folders")
        
        for task_folder in task_folders:
            task_id = task_folder.name
            metadata_file = task_folder / "metadata.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # เพิ่ม task_id ถ้าไม่มี
                        if 'task_id' not in data:
                            data['task_id'] = task_id
                        transcriptions.append(data)
                        logger.debug(f"✅ Loaded transcription: {task_id}, status={data.get('status')}, full_text length={len(data.get('full_text', '') or '')}, chunks count={len(data.get('chunks', []) or [])}")
                except Exception as e:
                    logger.warning(f"ไม่สามารถอ่าน metadata.json สำหรับ {task_id}: {e}")
            else:
                logger.debug(f"⚠️  metadata.json not found in {task_folder}")
        
        # วิธีเก่า: หา .json files โดยตรง (สำหรับ backward compatibility)
        json_files = list(transcription_dir.glob("*.json"))
        logger.info(f"📄 Found {len(json_files)} old format JSON files")
        for json_file in json_files:
            task_id = json_file.stem
            stats = self.get_transcription_stats(task_id)
            if stats:
                transcriptions.append(stats)
                logger.debug(f"✅ Loaded old format transcription: {task_id}")
        
        logger.info(f"📊 Total transcriptions found: {len(transcriptions)}")
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
        """ลบ transcription (รองรับ folder structure ใหม่)"""
        transcription_dir = self.storage_dir / "transcriptions"
        
        # วิธีใหม่: ลบ folder ทั้งหมด
        task_folder = transcription_dir / task_id
        if task_folder.exists() and task_folder.is_dir():
            import shutil
            shutil.rmtree(task_folder)
            logger.info(f"ลบ transcription folder: {task_id}")
            return True
        
        # วิธีเก่า: ลบไฟล์เดียว (backward compatibility)
        file_path = transcription_dir / f"{task_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"ลบ transcription file: {task_id}")
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