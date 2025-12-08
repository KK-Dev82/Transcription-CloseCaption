import subprocess
import json
import logging
import requests
import asyncio
from typing import List, Dict, Optional
from pathlib import Path
import tempfile
import os

# Import Provider Pattern
from .whisper_providers import WhisperProviderFactory, TranscriptionResult

logger = logging.getLogger(__name__)

class WhisperService:
    """
    Whisper Service - Wrapper สำหรับ Provider Pattern
    
    Features:
    - รองรับ switch ระหว่าง Groq API และ On-Premise (whisper.cpp)
    - Backward compatible กับ code เดิม
    - ใช้ environment variable WHISPER_PROVIDER เพื่อเลือก provider
    
    Environment Variables:
    - WHISPER_PROVIDER: "builtin" หรือ "groq" (default: builtin)
    - WHISPER_MODEL: model ที่ใช้ (default: base)
    - GROQ_API_KEY: API key สำหรับ Groq
    """
    
    def __init__(self, use_docker: bool = True, whisper_cpp_path: str = "whisper.cpp", model_dir: str = "models"):
        self.use_docker = use_docker
        self.whisper_cpp_path = Path(whisper_cpp_path)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        # Whisper API URL - ใช้ environment variable (for builtin provider)
        self.whisper_api_url = os.getenv('WHISPER_API_URL', 'http://localhost:8002')
        
        # Initialize provider (lazy loading)
        self._provider = None
        self._provider_name = os.getenv('WHISPER_PROVIDER', 'builtin')
        
        # Log provider info
        logger.info(f"🎯 WhisperService initialized with provider: {self._provider_name}")
        
        # ตรวจสอบว่า whisper.cpp ถูกติดตั้งแล้วหรือไม่ (สำหรับ builtin)
        if self._provider_name == 'builtin':
            self._check_whisper_installation()
    
    @property
    def provider(self):
        """Lazy load provider"""
        if self._provider is None:
            logger.info(f"🔍 DEBUG: Initializing provider, provider_name={self._provider_name}")
            logger.info(f"🔍 DEBUG: Calling WhisperProviderFactory.get_with_fallback()...")
            self._provider = WhisperProviderFactory.get_with_fallback()
            logger.info(f"🔍 DEBUG: Provider loaded: {self._provider.provider_name}, type: {type(self._provider)}")
            logger.info(f"🏭 Loaded provider: {self._provider.provider_name}")
        return self._provider
    
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
                    timeout=600  # 10 นาที (เพิ่มจาก 5 นาที)
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
                       use_thai_processor: bool = True,
                       initial_prompt: Optional[str] = None) -> Dict:
        """
        แปลงเสียงเป็นข้อความ - ใช้ Provider Pattern
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            model_size: ขนาด model (base, small, medium, large, large-v3-turbo)
            language: ภาษา (th, en, auto)
            output_format: รูปแบบ output (json) - deprecated, ใช้ json เสมอ
            use_thai_processor: ใช้ Thai text processor หรือไม่
            
        Returns:
            Dict: {"text": "...", "segments": [...]}
        """
        
        try:
            # Use provider to transcribe
            logger.info(f"📝 Transcribing with provider: {self.provider.provider_name}")
            logger.info(f"🔍 DEBUG: transcribe_file() called with audio_path={audio_path}, language={language}, model_size={model_size}")
            logger.info(f"🔍 DEBUG: Provider name: {self.provider.provider_name}")
            logger.info(f"🔍 DEBUG: Provider type: {type(self.provider)}")
            
            # ⚠️ ใช้ _run_async_transcribe เสมอ (ใช้ asyncio.run()) เพื่อป้องกัน event loop conflict
            # ไม่ต้องตรวจสอบ event loop เพราะ _run_async_transcribe จะจัดการเอง
            logger.info(f"🔍 DEBUG: Calling _run_async_transcribe()...")
            result: TranscriptionResult = self._run_async_transcribe(audio_path, language, model_size, initial_prompt)
            logger.info(f"🔍 DEBUG: _run_async_transcribe() completed, result type: {type(result)}")
            
            # Convert to dict format (backward compatible)
            transcription_result = {
                "text": result.text,
                "segments": result.segments,
                "provider": result.provider,
                "model": result.model,
                "processing_time": result.processing_time
            }
            
            # ใช้ Thai Text Processor หากเป็นภาษาไทย
            if use_thai_processor and language == "th":
                transcription_result = self._apply_thai_processing(transcription_result)
            
            return transcription_result
                        
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงเสียง: {e}")
            raise
    
    def _run_async_transcribe(self, audio_path: str, language: str, model_size: str, initial_prompt: Optional[str] = None) -> TranscriptionResult:
        """
        Helper method to run async transcribe
        ⚠️ ต้องไม่ถูกเรียกจาก async function โดยตรง - ใช้ await provider.transcribe() แทน
        """
        # ตรวจสอบว่ามี event loop อยู่แล้วหรือไม่
        try:
            # ถ้ามี event loop อยู่แล้ว - หมายความว่าถูกเรียกจาก async function
            # ในกรณีนี้ไม่ควรใช้ ThreadPoolExecutor เพราะจะทำให้เกิด nested event loop
            # แต่เนื่องจาก transcribe_file เป็น sync function และถูกเรียกจาก async function
            # เราต้องสร้าง event loop ใหม่ใน thread แยก
            loop = asyncio.get_running_loop()
            # ใช้ ThreadPoolExecutor เพื่อรัน async function ใน thread แยก (ไม่มี event loop)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_async_transcribe_in_new_loop, audio_path, language, model_size, initial_prompt)
                return future.result()
        except RuntimeError:
            # ไม่มี event loop อยู่แล้ว - สร้าง event loop ใหม่
            return self._run_async_transcribe_in_new_loop(audio_path, language, model_size, initial_prompt)
    
    def _run_async_transcribe_in_new_loop(self, audio_path: str, language: str, model_size: str, initial_prompt: Optional[str] = None) -> TranscriptionResult:
        """Helper method to run async transcribe in a completely new event loop (for thread execution)"""
        # สร้าง event loop ใหม่สำหรับ thread นี้
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.provider.transcribe(audio_path, language, model_size, initial_prompt)
            )
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    def transcribe_file_legacy(self, audio_path: str, model_size: str = "base", 
                       language: str = "th", output_format: str = "json", 
                       use_thai_processor: bool = True) -> Dict:
        """
        [LEGACY] แปลงเสียงเป็นข้อความ - ใช้ code เดิม (ไม่ผ่าน Provider)
        สำหรับ fallback ในกรณีที่ Provider มีปัญหา
        """
        
        try:
            if self.use_docker:
                # ใช้ Whisper API Service
                whisper_api_url = self.whisper_api_url
                
                # แปลง path ให้ตรงกับ Whisper container
                audio_path_obj = Path(audio_path)
                if audio_path_obj.is_absolute():
                    try:
                        relative_path = audio_path_obj.relative_to(Path.cwd())
                        whisper_audio_path = f"/app/{relative_path}"
                    except ValueError:
                        whisper_audio_path = str(audio_path_obj)
                else:
                    whisper_audio_path = f"/app/{audio_path}"
                
                # ตรวจสอบว่าไฟล์มีอยู่จริงหรือไม่
                if not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Audio file not found: {audio_path}")
                
                logger.info(f"[Legacy] Original audio path: {audio_path}")
                logger.info(f"[Legacy] Whisper audio path: {whisper_audio_path}")
                
                # ส่งคำขอไปยัง Whisper API
                request_data = {
                    "audio_path": whisper_audio_path,
                    "language": language,
                    "model_size": model_size,
                    "output_format": output_format
                }
                
                logger.info(f"[Legacy] ส่งคำขอไปยัง Whisper API: {request_data}")
                
                response = requests.post(
                    f"{whisper_api_url}/transcribe",
                    json=request_data,
                    timeout=600
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result["success"]:
                        transcription_result = {
                            "text": result["text"],
                            "segments": result.get("segments", [])
                        }
                        
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
                    try:
                        os.unlink(output_path)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"[Legacy] เกิดข้อผิดพลาดในการแปลงเสียง: {e}")
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
                corrected_text = " ".join([str(chunk["text"]) for chunk in processed_chunks if chunk.get("text")])
                
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
        total_transcriptions = len(transcriptions)
        logger.info(f"📊 Starting merge_transcriptions: {total_transcriptions} transcriptions, chunk_duration={chunk_duration}s")
        
        for i, trans in enumerate(transcriptions):
            if "error" in trans:
                logger.warning(f"⚠️  Transcription {i+1}/{total_transcriptions} has error: {trans.get('error')}, skipping...")
                continue
            
            logger.info(f"📝 Processing transcription {i+1}/{total_transcriptions}: has_text={bool(trans.get('text'))}, has_segments={bool(trans.get('segments'))}")
                
            # รวมข้อความ
            if "text" in trans:
                text_value = trans["text"]
                if not isinstance(text_value, str):
                    text_value = str(text_value) if text_value is not None else ""
                if text_value.strip():
                    merged["text"] += " " + text_value.strip()
                    logger.debug(f"   Added text: {len(text_value.strip())} chars")
            
            # รวม segments
            segments_count = 0
            if "segments" in trans and trans["segments"]:
                segments_list = trans["segments"]
                logger.info(f"   Found {len(segments_list)} segments in transcription {i+1}")
                for j, segment in enumerate(segments_list):
                    if not isinstance(segment, dict):
                        logger.warning(f"⚠️  Segment {j+1} in transcription {i+1} is not a dict: {type(segment)}, skipping...")
                        continue
                    
                    # ปรับเวลาให้ต่อเนื่อง
                    adjusted_segment = segment.copy()
                    
                    # แปลง timestamp เป็นวินาที (รองรับทั้ง string และ float/int)
                    start_value = segment.get("start") or segment.get("start_time") or 0
                    end_value = segment.get("end") or segment.get("end_time") or 0
                    
                    start_seconds = self._timestamp_to_seconds(start_value)
                    end_seconds = self._timestamp_to_seconds(end_value)
                    
                    # ปรับเวลาให้ต่อเนื่องกับ chunks ก่อนหน้า
                    adjusted_start = start_seconds + current_time
                    adjusted_end = end_seconds + current_time
                    adjusted_segment["start"] = adjusted_start
                    adjusted_segment["end"] = adjusted_end
                    
                    # เก็บ text จาก segment
                    segment_text = adjusted_segment.get("text", "").strip()
                    if segment_text:
                        merged["segments"].append(adjusted_segment)
                        segments_count += 1
                        logger.debug(f"   Added segment {j+1}: {adjusted_start:.2f}s - {adjusted_end:.2f}s ({len(segment_text)} chars)")
                    else:
                        logger.warning(f"⚠️  Segment {j+1} in transcription {i+1} has no text, skipping...")
            
            if segments_count > 0:
                logger.info(f"   ✅ Added {segments_count} segments from transcription {i+1}")
            
            current_time += chunk_duration
        
        # ทำความสะอาดข้อความ
        merged["text"] = merged["text"].strip()
        
        logger.info(f"📊 Merge completed: text length={len(merged['text'])}, segments count={len(merged['segments'])}")
        if merged["text"]:
            logger.info(f"   Text preview: {merged['text'][:200]}...")
        
        return merged
    
    def _timestamp_to_seconds(self, timestamp) -> float:
        """แปลง timestamp เป็นวินาที (รองรับทั้ง string และ float/int)"""
        # ถ้าเป็นตัวเลขอยู่แล้ว (float/int) → คืนค่าตรงๆ
        if isinstance(timestamp, (int, float)):
            return float(timestamp)
        
        # ถ้าเป็น string → พยายามแปลง
        if not isinstance(timestamp, str):
            try:
                return float(timestamp)
            except (ValueError, TypeError):
                return 0.0
        
        try:
            # รองรับรูปแบบ timestamp string (HH:MM:SS,mmm)
            if ',' in timestamp:
                # แยกส่วนเวลาและมิลลิวินาที
                time_part, ms_part = timestamp.split(',')
                
                # แยกชั่วโมง นาที วินาที
                hours, minutes, seconds = map(int, time_part.split(':'))
                
                # คำนวณวินาทีรวม
                total_seconds = hours * 3600 + minutes * 60 + seconds + int(ms_part) / 1000
                
                return total_seconds
            else:
                # ถ้าไม่มี comma → ลองแปลงเป็น float ตรงๆ (อาจเป็น "0.5" หรือ "5.2")
                try:
                    return float(timestamp)
                except ValueError:
                    # ลอง parse เป็น HH:MM:SS
                    parts = timestamp.split(':')
                    if len(parts) == 3:
                        hours, minutes, seconds = map(float, parts)
                        return hours * 3600 + minutes * 60 + seconds
                    elif len(parts) == 2:
                        minutes, seconds = map(float, parts)
                        return minutes * 60 + seconds
                    else:
                        return 0.0
        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"ไม่สามารถแปลง timestamp '{timestamp}' (type: {type(timestamp)}) เป็นวินาที: {e}")
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