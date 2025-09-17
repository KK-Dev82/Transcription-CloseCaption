import subprocess
import json
import logging
import requests
from typing import List, Dict, Optional
from pathlib import Path
import tempfile
import os

logger = logging.getLogger(__name__)

class WhisperService:
    def __init__(self, use_docker: bool = True, whisper_cpp_path: str = "whisper.cpp", model_dir: str = "models"):
        self.use_docker = use_docker
        self.whisper_cpp_path = Path(whisper_cpp_path)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        # Whisper API URL - ใช้ environment variable
        self.whisper_api_url = os.getenv('WHISPER_API_URL', 'http://localhost:8002')
        
        # ตรวจสอบว่า whisper.cpp ถูกติดตั้งแล้วหรือไม่
        self._check_whisper_installation()
    
    def _check_whisper_installation(self):
        """ตรวจสอบการติดตั้ง Whisper.cpp"""
        if not self.use_docker:
            # เฉพาะเมื่อไม่ใช้ Docker ถึงจะตรวจสอบ local whisper.cpp
            main_executable = self.whisper_cpp_path / "main"
            if not main_executable.exists():
                logger.warning("ไม่พบ Whisper.cpp executable. กรุณาติดตั้งตาม README.md")
        else:
            # ใช้ Docker service - ไม่ต้องตรวจสอบ local installation
            logger.info("ใช้ Whisper Docker service - ไม่ต้องติดตั้ง local whisper.cpp")
    
    def download_model(self, model_size: str = "base") -> str:
        """ดาวน์โหลด Whisper model"""
        model_name = f"ggml-{model_size}.bin"
        model_path = self.model_dir / model_name
        
        if model_path.exists():
            return str(model_path)
        
        if self.use_docker:
            # ใช้ Whisper API Service ในการดาวน์โหลด model
            try:
                request_data = {
                    "model_size": model_size
                }
                
                response = requests.post(
                    f"{self.whisper_api_url}/download-model",
                    json=request_data,
                    timeout=300  # 5 นาที
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result["success"]:
                        logger.info(f"ดาวน์โหลด model {model_size} สำเร็จ")
                        return str(model_path)
                    else:
                        raise Exception(f"Whisper API error: {result['error']}")
                else:
                    raise Exception(f"Whisper API HTTP error: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลด model ด้วย Whisper API: {e}")
        else:
            # ดาวน์โหลด model แบบ local
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
                       language: str = "th", output_format: str = "json", 
                       use_thai_processor: bool = True) -> Dict:
        """แปลงเสียงเป็นข้อความ"""
        
        try:
            if self.use_docker:
                # ใช้ Whisper API Service
                whisper_api_url = self.whisper_api_url
                
                # แปลง path ให้ตรงกับ Whisper container
                # API container: temp/task_xxx/chunk_X_xxx.wav  
                # Whisper container: /app/temp/task_xxx/chunk_X_xxx.wav (เพราะ mount temp เป็น /app/temp)
                
                # แปลง path จาก temp/task_xxx/chunk_xxx.wav -> /app/temp/task_xxx/chunk_xxx.wav
                audio_path_obj = Path(audio_path)
                if audio_path_obj.is_absolute():
                    # ถ้าเป็น absolute path ให้แปลงเป็น relative จาก project root
                    try:
                        relative_path = audio_path_obj.relative_to(Path.cwd())
                        whisper_audio_path = f"/app/{relative_path}"
                    except ValueError:
                        # ถ้าไม่สามารถหา relative path ได้ ให้ใช้ absolute path
                        whisper_audio_path = str(audio_path_obj)
                else:
                    # ถ้าเป็น relative path แล้ว
                    whisper_audio_path = f"/app/{audio_path}"
                
                # ตรวจสอบว่าไฟล์มีอยู่จริงหรือไม่
                if not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Audio file not found: {audio_path}")
                
                logger.info(f"Original audio path: {audio_path}")
                logger.info(f"Whisper audio path: {whisper_audio_path}")
                
                # ส่งคำขอไปยัง Whisper API
                request_data = {
                    "audio_path": whisper_audio_path,
                    "language": language,
                    "model_size": model_size,
                    "output_format": output_format
                }
                
                logger.info(f"ส่งคำขอไปยัง Whisper API: {request_data}")
                
                response = requests.post(
                    f"{whisper_api_url}/transcribe",
                    json=request_data,
                    timeout=300  # 5 นาที
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result["success"]:
                        transcription_result = {
                            "text": result["text"],
                            "segments": result.get("segments", [])
                        }
                        
                        # ใช้ Thai Text Processor หากเป็นภาษาไทย
                        if use_thai_processor and language == "th":
                            transcription_result = self._apply_thai_processing(transcription_result)
                        
                        return transcription_result
                    else:
                        raise Exception(f"Whisper API error: {result['error']}")
                else:
                    raise Exception(f"Whisper API HTTP error: {response.status_code}")
                    
            else:
                # ใช้ local installation
                model_path = self.download_model(model_size)
                
                # สร้างไฟล์ output ชั่วคราว
                with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp_file:
                    output_path = tmp_file.name
                
                try:
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
                        
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงเสียง: {e}")
            raise
    
    def _apply_thai_processing(self, transcription_result: Dict) -> Dict:
        """ใช้ Thai Text Processor เพื่อปรับปรุงความแม่นยำ"""
        try:
            from .thai_text_processor import create_thai_processor
            
            processor = create_thai_processor()
            
            # ประมวลผล segments
            if "segments" in transcription_result and transcription_result["segments"]:
                # แปลง segments เป็น chunks format
                chunks = []
                for segment in transcription_result["segments"]:
                    chunk = {
                        "start_time": segment.get("start", 0),
                        "end_time": segment.get("end", 0), 
                        "text": segment.get("text", ""),
                        "confidence": segment.get("avg_logprob")
                    }
                    chunks.append(chunk)
                
                # ประมวลผล chunks
                processed_chunks = processor.process_transcription_chunks(chunks)
                
                # รวมข้อความที่แก้ไขแล้ว
                corrected_text = " ".join([chunk["text"] for chunk in processed_chunks if chunk.get("text")])
                
                # อัปเดตผลลัพธ์
                transcription_result["text"] = corrected_text
                transcription_result["original_text"] = transcription_result.get("text", "")
                transcription_result["chunks"] = processed_chunks
                transcription_result["processing_stats"] = processor.get_statistics(processed_chunks)
                
                logger.info(f"Thai processing completed: {transcription_result['processing_stats']}")
            
            return transcription_result
            
        except Exception as e:
            logger.error(f"Thai processing error: {e}")
            # ถ้าเกิดข้อผิดพลาด ส่งกลับผลลัพธ์เดิม
            return transcription_result
    
    def transcribe_chunks(self, chunk_paths: List[str], model_size: str = "base",
                         language: str = "th", use_thai_processor: bool = True) -> List[Dict]:
        """แปลงเสียงหลาย chunks"""
        results = []
        
        for i, chunk_path in enumerate(chunk_paths):
            try:
                logger.info(f"กำลังแปลง chunk {i+1}/{len(chunk_paths)}")
                result = self.transcribe_file(chunk_path, model_size, language, use_thai_processor=use_thai_processor)
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
                    
                    # แปลง timestamp string เป็นวินาที
                    start_seconds = self._timestamp_to_seconds(segment["start"])
                    end_seconds = self._timestamp_to_seconds(segment["end"])
                    
                    adjusted_segment["start"] = start_seconds + current_time
                    adjusted_segment["end"] = end_seconds + current_time
                    merged["segments"].append(adjusted_segment)
            
            current_time += chunk_duration
        
        # ทำความสะอาดข้อความ
        merged["text"] = merged["text"].strip()
        
        return merged
    
    def _timestamp_to_seconds(self, timestamp: str) -> float:
        """แปลง timestamp string (HH:MM:SS,mmm) เป็นวินาที"""
        try:
            # แยกส่วนเวลาและมิลลิวินาที
            time_part, ms_part = timestamp.split(',')
            
            # แยกชั่วโมง นาที วินาที
            hours, minutes, seconds = map(int, time_part.split(':'))
            
            # คำนวณวินาทีรวม
            total_seconds = hours * 3600 + minutes * 60 + seconds + int(ms_part) / 1000
            
            return total_seconds
        except (ValueError, AttributeError):
            # ถ้าแปลงไม่ได้ ให้คืนค่า 0
            return 0.0
    
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