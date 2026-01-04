#!/usr/bin/env python3
"""
Whisper API Service - ใช้ faster-whisper แทน whisper.cpp
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import os
import logging
from pathlib import Path
from typing import Optional
import time

# Setup cuDNN library path BEFORE importing faster_whisper
# This ensures cuDNN libraries are found when CTranslate2 loads
cudnn_paths = [
    "/usr/lib/x86_64-linux-gnu",
    "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib",
    "/usr/local/lib/python3.10/dist-packages/ctranslate2.libs",
]

current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
new_ld_path = ':'.join(cudnn_paths)
if current_ld_path:
    os.environ['LD_LIBRARY_PATH'] = f"{new_ld_path}:{current_ld_path}"
else:
    os.environ['LD_LIBRARY_PATH'] = new_ld_path

# Pre-load cuDNN library to ensure it's available
try:
    import ctypes
    cudnn_ops_infer = "/usr/lib/x86_64-linux-gnu/libcudnn_ops_infer.so.8"
    if os.path.exists(cudnn_ops_infer):
        ctypes.CDLL(cudnn_ops_infer, mode=ctypes.RTLD_GLOBAL)
        logging.info(f"✅ Pre-loaded cuDNN library: {cudnn_ops_infer}")
except Exception as e:
    logging.warning(f"⚠️  Could not pre-load cuDNN library: {e}")

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Whisper Transcription API")

# Import faster-whisper
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
    logger.info("✅ faster-whisper available")
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.error("❌ faster-whisper not available - please install: pip install faster-whisper")

class TranscriptionRequest(BaseModel):
    audio_path: str
    language: str = "th"
    model_size: str = "base"  # ใช้ model_size แทน model_path
    model_path: Optional[str] = None  # เก็บไว้เพื่อ backward compatibility

class TranscriptionResponse(BaseModel):
    text: str
    segments: list
    language: str
    success: bool
    error: Optional[str] = None

# Model cache (singleton)
_model_cache = {}

def _get_model(model_size: str = "base", device: str = "cuda", compute_type: str = "float16"):
    """Get or load Whisper model (cached) with error handling"""
    cache_key = f"{model_size}_{device}_{compute_type}"
    
    if cache_key not in _model_cache:
        logger.info(f"Loading model: {model_size} (device: {device}, compute_type: {compute_type})")
        try:
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
            _model_cache[cache_key] = model
            logger.info(f"✅ Model loaded: {model_size}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to load model {model_size} on {device}: {error_msg}")
            
            # Check for cuDNN errors
            if "cudnn" in error_msg.lower() or "libcudnn" in error_msg.lower():
                logger.warning(f"⚠️  cuDNN error detected: {error_msg}")
                logger.warning(f"⚠️  Falling back to CPU for model {model_size}")
                try:
                    model = WhisperModel(model_size, device="cpu", compute_type="int8")
                    cache_key_cpu = f"{model_size}_cpu_int8"
                    _model_cache[cache_key_cpu] = model
                    logger.info(f"✅ Model loaded on CPU (fallback): {model_size}")
                    return model
                except Exception as e2:
                    logger.error(f"❌ Failed to load model on CPU: {e2}")
                    raise Exception(f"Model loading failed on both GPU and CPU: GPU error: {error_msg}, CPU error: {e2}")
            
            # Fallback to CPU for other errors
            if device != "cpu":
                logger.warning(f"⚠️  Falling back to CPU for model {model_size}")
                try:
                    model = WhisperModel(model_size, device="cpu", compute_type="int8")
                    cache_key_cpu = f"{model_size}_cpu_int8"
                    _model_cache[cache_key_cpu] = model
                    logger.info(f"✅ Model loaded on CPU (fallback): {model_size}")
                    return model
                except Exception as e2:
                    logger.error(f"❌ Failed to load model on CPU: {e2}")
                    raise Exception(f"Model loading failed: {error_msg}")
            else:
                raise
    else:
        logger.debug(f"Using cached model: {model_size}")
    
    return _model_cache[cache_key]

@app.get("/health")
async def health_check():
    """ตรวจสอบสถานะ service"""
    if not FASTER_WHISPER_AVAILABLE:
        return {"status": "unhealthy", "service": "whisper-transcription", "error": "faster-whisper not available"}
    return {"status": "healthy", "service": "whisper-transcription", "provider": "faster-whisper"}

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(request: TranscriptionRequest):
    """แปลงเสียงเป็นข้อความ - ใช้ faster-whisper"""
    
    if not FASTER_WHISPER_AVAILABLE:
        return TranscriptionResponse(
            text="",
            segments=[],
            language=request.language,
            success=False,
            error="faster-whisper not available. Please install: pip install faster-whisper"
        )
    
    try:
        # ตรวจสอบไฟล์ audio
        audio_path = request.audio_path
        
        # Convert Docker path to local path if needed
        # builtin provider ส่ง path เป็น /app/temp/... แต่ไฟล์จริงอยู่ที่ /workspace/transcription-service/temp/...
        if audio_path.startswith("/app/"):
            # Convert /app/... to workspace path
            audio_path = audio_path.replace("/app/", "/workspace/transcription-service/")
            logger.info(f"Converted path: {request.audio_path} -> {audio_path}")
        
        # Try multiple path variations
        possible_paths = [
            audio_path,
            request.audio_path,
            f"/workspace/transcription-service/{request.audio_path}" if not request.audio_path.startswith("/") else request.audio_path,
            request.audio_path.replace("/app/", "/workspace/transcription-service/") if "/app/" in request.audio_path else None
        ]
        
        audio_path_found = None
        for path in possible_paths:
            if path and os.path.exists(path):
                audio_path_found = path
                break
        
        if not audio_path_found:
            logger.error(f"Audio file not found. Tried: {possible_paths}")
            return TranscriptionResponse(
                text="",
                segments=[],
                language=request.language,
                success=False,
                error=f"Audio file not found: {request.audio_path}"
            )
        
        audio_path = audio_path_found
        logger.info(f"✅ Using audio path: {audio_path}")
        
        logger.info(f"🎯 เริ่มการแปลงเสียง: {audio_path}")
        
        # ใช้ model_size แทน model_path
        model_size = request.model_size or "base"
        
        # Get device and compute type
        # Try CUDA first, but fallback to CPU if cuDNN issues
        device = os.getenv('WHISPER_DEVICE', 'cuda')
        compute_type = os.getenv('WHISPER_COMPUTE_TYPE', 'float16' if device == 'cuda' else 'float32')
        
        # Load model (cached) with automatic CPU fallback
        model = None
        try:
            model = _get_model(model_size, device, compute_type)
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"⚠️  Failed to load model on {device}: {error_msg}")
            
            # Auto-fallback to CPU if CUDA fails
            if device == 'cuda' and ('cudnn' in error_msg.lower() or 'libcudnn' in error_msg.lower()):
                logger.warning(f"⚠️  cuDNN error detected, falling back to CPU")
                try:
                    model = _get_model(model_size, 'cpu', 'int8')
                    logger.info(f"✅ Successfully loaded model on CPU (fallback)")
                except Exception as e2:
                    logger.error(f"❌ Failed to load model on CPU: {e2}")
                    return TranscriptionResponse(
                        text="",
                        segments=[],
                        language=request.language,
                        success=False,
                        error=f"Failed to load model {model_size} on both CUDA and CPU: {str(e2)}"
                    )
            else:
                return TranscriptionResponse(
                    text="",
                    segments=[],
                    language=request.language,
                    success=False,
                    error=f"Failed to load model {model_size}: {str(e)}"
                )
        
        # Transcribe (run in thread pool to avoid blocking)
        start_time = time.time()
        
        try:
            # Run transcription in thread pool (faster-whisper is synchronous)
            # Wrap in try-except to handle transcription errors gracefully
            def transcribe_wrapper():
                try:
                    return model.transcribe(
                        audio_path,
                        language=request.language if request.language != "auto" else None,
                        beam_size=1,  # Greedy (fastest)
                        vad_filter=True  # Voice activity detection (faster)
                    )
                except Exception as e:
                    logger.error(f"❌ Transcription error: {e}", exc_info=True)
                    raise
            
            loop = asyncio.get_event_loop()
            segments_generator, info = await loop.run_in_executor(
                None,
                transcribe_wrapper
            )
            
            # Convert generator to list
            segments_list = list(segments_generator)
            
            processing_time = time.time() - start_time
            
            # Extract text and segments
            text = ' '.join([segment.text.strip() for segment in segments_list])
            
            # Format segments
            formatted_segments = []
            for segment in segments_list:
                formatted_segments.append({
                    'start': f"{int(segment.start // 3600):02d}:{int((segment.start % 3600) // 60):02d}:{int(segment.start % 60):02d},{int((segment.start % 1) * 1000):03d}",
                    'end': f"{int(segment.end // 3600):02d}:{int((segment.end % 3600) // 60):02d}:{int(segment.end % 60):02d},{int((segment.end % 1) * 1000):03d}",
                    'text': segment.text.strip()
                })
            
            detected_language = info.language if hasattr(info, 'language') else request.language
            
            logger.info(f"✅ แปลงเสียงสำเร็จ: {len(text)} ตัวอักษร, {len(formatted_segments)} segments, ใช้เวลา {processing_time:.2f}s")
            
            return TranscriptionResponse(
                text=text,
                segments=formatted_segments,
                language=detected_language,
                success=True
            )
            
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}", exc_info=True)
            return TranscriptionResponse(
                text="",
                segments=[],
                language=request.language,
                success=False,
                error=f"Transcription failed: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}", exc_info=True)
        return TranscriptionResponse(
            text="",
            segments=[],
            language=request.language,
            success=False,
            error=f"Unexpected error: {str(e)}"
        )

@app.get("/models")
async def list_models():
    """แสดงรายการ models ที่รองรับ"""
    models = [
        {"name": "tiny", "size": "39M"},
        {"name": "base", "size": "74M"},
        {"name": "small", "size": "244M"},
        {"name": "medium", "size": "769M"},
        {"name": "large", "size": "1550M"},
        {"name": "large-v2", "size": "1550M"},
        {"name": "large-v3", "size": "1550M"},
    ]
    return {"models": models, "provider": "faster-whisper"}

class DownloadModelRequest(BaseModel):
    model_size: str = "base"

class DownloadModelResponse(BaseModel):
    success: bool
    message: str = ""
    error: str = ""

@app.post("/download-model", response_model=DownloadModelResponse)
async def download_model(request: DownloadModelRequest):
    """ดาวน์โหลด Whisper model (faster-whisper จะดาวน์โหลดอัตโนมัติ)"""
    
    try:
        logger.info(f"Model {request.model_size} will be downloaded automatically by faster-whisper on first use")
        return DownloadModelResponse(
            success=True,
            message=f"Model {request.model_size} will be downloaded automatically by faster-whisper on first use"
        )
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาด: {e}")
        return DownloadModelResponse(
            success=False,
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    import signal
    import sys
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("🛑 Received shutdown signal, cleaning up...")
        # Clear model cache to free memory
        _model_cache.clear()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup exception handler to log crashes
    def exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger.critical("❌ Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        # Clear model cache
        _model_cache.clear()
    
    sys.excepthook = exception_handler
    
    # ใช้ workers=1 เพื่อหลีกเลี่ยงปัญหา model loading ในหลาย processes
    # faster-whisper models จะถูก cache ใน memory
    try:
        logger.info("🚀 Starting Whisper API service on port 8002...")
        uvicorn.run("whisper_api:app", host="0.0.0.0", port=8002, workers=1, log_level="info")
    except Exception as e:
        logger.critical(f"❌ Whisper API service crashed: {e}", exc_info=True)
        _model_cache.clear()
        sys.exit(1)
