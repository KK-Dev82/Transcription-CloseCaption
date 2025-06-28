import subprocess
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path
import tempfile
import os

logger = logging.getLogger(__name__)

class WhisperService:
    def __init__(self, whisper_cpp_path: str = "whisper.cpp", model_dir: str = "models"):
        self.whisper_cpp_path = Path(whisper_cpp_path)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        # ตรวจสอบว่า whisper.cpp ถูกติดตั้งแล้วหรือไม่
        self._check_whisper_installation()
    
    def _check_whisper_installation(self):
        """ตรวจสอบการติดตั้ง Whisper.cpp"""
        main_executable = self.whisper_cpp_path / "main"
        if not main_executable.exists():
            logger.warning("ไม่พบ Whisper.cpp executable. กรุณาติดตั้งตาม README.md")
    
    def download_model(self, model_size: str = "base") -> str:
        """ดาวน์โหลด Whisper model"""
        model_name = f"ggml-{model_size}.bin"
        model_path = self.model_dir / model_name
        
        if model_path.exists():
            return str(model_path)
        
        # ดาวน์โหลด model
        download_script = self.whisper_cpp_path / "models" / "download-ggml-model.sh"
        if download_script.exists():
            try:
                subprocess.run([
                    str(download_script), model_size
                ], cwd=self.whisper_cpp_path, check=True)
                
                # ย้ายไฟล์ไปยัง model_dir
                source_path = self.whisper_cpp_path / "models" / model_name
                if source_path.exists():
                    import shutil
                    shutil.move(str(source_path), str(model_path))
                    return str(model_path)
            except subprocess.CalledProcessError as e:
                logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลด model: {e}")
        
        raise FileNotFoundError(f"ไม่สามารถดาวน์โหลด model {model_size} ได้")
    
    def transcribe_file(self, audio_path: str, model_size: str = "base", 
                       language: str = "th", output_format: str = "json") -> Dict:
        """แปลงเสียงเป็นข้อความ"""
        model_path = self.download_model(model_size)
        
        # สร้างไฟล์ output ชั่วคราว
        with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            # รัน Whisper.cpp
            cmd = [
                str(self.whisper_cpp_path / "main"),
                "-m", model_path,
                "-f", audio_path,
                "-l", language,
                "-of", output_path,
                "--output-format", output_format
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # อ่านผลลัพธ์
            if output_format == "json":
                with open(output_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                with open(output_path, 'r', encoding='utf-8') as f:
                    return {"text": f.read().strip()}
                    
        except subprocess.CalledProcessError as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงเสียง: {e}")
            logger.error(f"stderr: {e.stderr}")
            raise
        finally:
            # ลบไฟล์ชั่วคราว
            try:
                os.unlink(output_path)
            except:
                pass
    
    def transcribe_chunks(self, chunk_paths: List[str], model_size: str = "base",
                         language: str = "th") -> List[Dict]:
        """แปลงเสียงหลาย chunks"""
        results = []
        
        for i, chunk_path in enumerate(chunk_paths):
            try:
                logger.info(f"กำลังแปลง chunk {i+1}/{len(chunk_paths)}")
                result = self.transcribe_file(chunk_path, model_size, language)
                results.append(result)
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการแปลง chunk {i}: {e}")
                results.append({"error": str(e)})
        
        return results
    
    def merge_transcriptions(self, transcriptions: List[Dict], 
                           chunk_duration: int = 30) -> Dict:
        """รวมผลลัพธ์จากหลาย chunks"""
        merged = {
            "text": "",
            "segments": [],
            "language": "th"
        }
        
        current_time = 0
        
        for i, trans in enumerate(transcriptions):
            if "error" in trans:
                continue
                
            # รวมข้อความ
            if "text" in trans:
                merged["text"] += " " + trans["text"].strip()
            
            # รวม segments
            if "segments" in trans:
                for segment in trans["segments"]:
                    # ปรับเวลาให้ต่อเนื่อง
                    adjusted_segment = segment.copy()
                    adjusted_segment["start"] += current_time
                    adjusted_segment["end"] += current_time
                    merged["segments"].append(adjusted_segment)
            
            current_time += chunk_duration
        
        # ทำความสะอาดข้อความ
        merged["text"] = merged["text"].strip()
        
        return merged
    
    def create_srt_subtitles(self, transcription: Dict) -> str:
        """สร้างไฟล์ SRT subtitle"""
        srt_content = ""
        
        if "segments" not in transcription:
            return srt_content
        
        for i, segment in enumerate(transcription["segments"], 1):
            start_time = self._format_timestamp(segment["start"])
            end_time = self._format_timestamp(segment["end"])
            text = segment.get("text", "").strip()
            
            srt_content += f"{i}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{text}\n\n"
        
        return srt_content
    
    def _format_timestamp(self, seconds: float) -> str:
        """แปลงวินาทีเป็นรูปแบบ timestamp"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}" 