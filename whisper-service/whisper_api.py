#!/usr/bin/env python3
"""
Whisper API Service สำหรับรันใน whisper container
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import tempfile
import os
import logging
from pathlib import Path
import json
from typing import Optional

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Whisper Transcription API")

class TranscriptionRequest(BaseModel):
    audio_path: str
    language: str = "th"
    model_path: str = "/app/models/ggml-base.bin"

class TranscriptionResponse(BaseModel):
    text: str
    segments: list
    language: str
    success: bool
    error: Optional[str] = None

@app.get("/health")
async def health_check():
    """ตรวจสอบสถานะ service"""
    return {"status": "healthy", "service": "whisper-transcription"}

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(request: TranscriptionRequest):
    """แปลงเสียงเป็นข้อความ"""
    
    try:
        # ตรวจสอบไฟล์ audio
        if not os.path.exists(request.audio_path):
            raise HTTPException(status_code=404, detail=f"Audio file not found: {request.audio_path}")
        
        # ตรวจสอบ model
        if not os.path.exists(request.model_path):
            raise HTTPException(status_code=404, detail=f"Model file not found: {request.model_path}")
        
        logger.info(f"เริ่มการแปลงเสียง: {request.audio_path}")
        
        # ตรวจสอบประเภทไฟล์และแปลงเป็น WAV ถ้าจำเป็น
        audio_file_path = request.audio_path
        file_extension = Path(request.audio_path).suffix.lower()
        
        # ถ้าเป็นไฟล์ที่ไม่รองรับโดยตรง ให้แปลงเป็น WAV
        if file_extension in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4a', '.aac']:
            logger.info(f"แปลงไฟล์ {file_extension} เป็น WAV")
            
            # สร้าง temporary file สำหรับ WAV
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
                wav_file_path = tmp_wav.name
            
            # ใช้ FFmpeg แปลงไฟล์
            ffmpeg_cmd = [
                'ffmpeg', '-i', request.audio_path,
                '-ar', '16000',  # sample rate 16kHz
                '-ac', '1',      # mono
                '-y',            # overwrite output file
                wav_file_path
            ]
            
            logger.info(f"รันคำสั่ง FFmpeg: {' '.join(ffmpeg_cmd)}")
            
            ffmpeg_result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=60  # timeout 1 นาที
            )
            
            if ffmpeg_result.returncode != 0:
                logger.error(f"FFmpeg conversion failed: {ffmpeg_result.stderr}")
                return TranscriptionResponse(
                    text="",
                    segments=[],
                    language=request.language,
                    success=False,
                    error=f"FFmpeg conversion failed: {ffmpeg_result.stderr}"
                )
            
            audio_file_path = wav_file_path
            logger.info(f"แปลงไฟล์สำเร็จ: {wav_file_path}")
        
        # สร้าง temporary file สำหรับ output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            output_file = tmp_file.name
        
        # รันคำสั่ง whisper-cli
        cmd = [
            "/app/whisper.cpp/build/bin/whisper-cli",
            "-m", request.model_path,
            "-f", request.audio_path,
            "-l", request.language,
            "-oj",  # output JSON format
            "-of", output_file.replace('.json', '')  # output file path (without extension)
        ]
        
        logger.info(f"รันคำสั่ง: {' '.join(cmd)}")
        
        # รันคำสั่ง
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # timeout 5 นาที
        )
        
        if result.returncode != 0:
            logger.error(f"เกิดข้อผิดพลาดในการแปลงเสียง: {result.stderr}")
            return TranscriptionResponse(
                text="",
                segments=[],
                language=request.language,
                success=False,
                error=f"Whisper command failed: {result.stderr}"
            )
        
        # อ่านผลลัพธ์ JSON
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                whisper_result = json.load(f)
            
            # แยกข้อความและ segments จาก format ของ whisper-cli
            transcription = whisper_result.get('transcription', [])
            
            # รวมข้อความทั้งหมด
            text = ' '.join([segment.get('text', '').strip() for segment in transcription])
            
            # แปลง segments ให้ตรงกับ format ที่ API ต้องการ
            segments = []
            for segment in transcription:
                timestamps = segment.get('timestamps', {})
                segments.append({
                    'start': timestamps.get('from', '00:00:00,000'),
                    'end': timestamps.get('to', '00:00:00,000'),
                    'text': segment.get('text', '').strip()
                })
            
            # ลบ temporary file
            os.unlink(output_file)
            
            logger.info(f"แปลงเสียงสำเร็จ: {len(text)} ตัวอักษร, {len(segments)} segments")
            
            return TranscriptionResponse(
                text=text,
                segments=segments,
                language=request.language,
                success=True
            )
            
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"เกิดข้อผิดพลาดในการอ่านผลลัพธ์: {e}")
            return TranscriptionResponse(
                text="",
                segments=[],
                language=request.language,
                success=False,
                error=f"Failed to read output: {str(e)}"
            )
            
    except subprocess.TimeoutExpired:
        logger.error("การแปลงเสียงใช้เวลานานเกินไป")
        return TranscriptionResponse(
            text="",
            segments=[],
            language=request.language,
            success=False,
            error="Transcription timeout"
        )
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")
        return TranscriptionResponse(
            text="",
            segments=[],
            language=request.language,
            success=False,
            error=str(e)
        )

@app.get("/models")
async def list_models():
    """แสดงรายการ models ที่มี"""
    models_dir = Path("/app/models")
    models = []
    
    if models_dir.exists():
        for model_file in models_dir.glob("*.bin"):
            models.append({
                "name": model_file.name,
                "size": model_file.stat().st_size,
                "path": str(model_file)
            })
    
    return {"models": models}

class DownloadModelRequest(BaseModel):
    model_size: str = "base"

class DownloadModelResponse(BaseModel):
    success: bool
    message: str = ""
    error: str = ""

@app.post("/download-model", response_model=DownloadModelResponse)
async def download_model(request: DownloadModelRequest):
    """ดาวน์โหลด Whisper model"""
    
    try:
        logger.info(f"เริ่มดาวน์โหลด model: {request.model_size}")
        
        # รันคำสั่งดาวน์โหลด
        cmd = [
            "/bin/bash", "-c",
            f"cd /app/whisper.cpp && ./models/download-ggml-model.sh {request.model_size}"
        ]
        
        logger.info(f"รันคำสั่ง: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # ตรวจสอบว่าไฟล์ถูกสร้างขึ้นหรือไม่
        model_name = f"ggml-{request.model_size}.bin"
        model_path = Path(f"/app/models/{model_name}")
        
        if model_path.exists():
            logger.info(f"ดาวน์โหลด model สำเร็จ: {model_path}")
            return DownloadModelResponse(
                success=True,
                message=f"ดาวน์โหลด model {request.model_size} สำเร็จ"
            )
        else:
            # ตรวจสอบใน whisper.cpp/models directory
            whisper_model_path = Path(f"/app/whisper.cpp/models/{model_name}")
            if whisper_model_path.exists():
                # ย้ายไฟล์ไปยัง models directory
                import shutil
                shutil.move(str(whisper_model_path), str(model_path))
                logger.info(f"ย้าย model ไปยัง: {model_path}")
                return DownloadModelResponse(
                    success=True,
                    message=f"ดาวน์โหลดและย้าย model {request.model_size} สำเร็จ"
                )
            else:
                raise Exception(f"ไม่พบไฟล์ model หลังดาวน์โหลด: {model_name}")
                
    except subprocess.CalledProcessError as e:
        logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลด model: {e}")
        logger.error(f"stderr: {e.stderr}")
        return DownloadModelResponse(
            success=False,
            error=f"เกิดข้อผิดพลาดในการดาวน์โหลด model: {e.stderr}"
        )
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาด: {e}")
        return DownloadModelResponse(
            success=False,
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002) 