"""
Whisper.cpp Provider (Local Direct)
ใช้ whisper.cpp โดยตรงผ่าน command line (ไม่ผ่าน Docker API)
เหมาะสำหรับ Local Testing บน Mac Mini M4 (ใช้ CPU)

Features:
- รองรับ model: tiny, base, small, medium, large
- ใช้ CPU (เหมาะสำหรับ Mac Mini M4)
- ไม่ต้องใช้ Docker
- รองรับ Metal (Apple Silicon acceleration) ถ้ามี
"""
import os
import subprocess
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional

from .base_provider import WhisperProvider, TranscriptionResult

logger = logging.getLogger(__name__)


class WhisperCppProvider(WhisperProvider):
    """
    Whisper.cpp Provider (Local Direct)
    ใช้ whisper.cpp โดยตรงผ่าน command line
    
    Environment Variables:
    - WHISPER_CPP_PATH: Path ไปยัง whisper.cpp executable (default: whisper.cpp/main หรือ /usr/local/bin/whisper)
    - WHISPER_MODEL_DIR: Directory ที่เก็บ models (default: models หรือ ~/.cache/whisper)
    - WHISPER_MODEL: Default model (default: base)
    - WHISPER_USE_METAL: ใช้ Metal acceleration สำหรับ Apple Silicon (default: true on macOS)
    
    Model Support:
    - tiny: เร็วสุด, ความแม่นยำต่ำ
    - base: เร็ว, ความแม่นยำปานกลาง (default)
    - small: ปานกลาง, ความแม่นยำดี
    - medium: ช้า, ความแม่นยำดีมาก
    - large: ช้าสุด, ความแม่นยำสูงสุด
    """
    
    # Supported models
    SUPPORTED_MODELS = [
        "tiny", "base", "small", "medium", "large"
    ]
    
    # Model to file mapping
    MODEL_FILES = {
        "tiny": "ggml-tiny.bin",
        "base": "ggml-base.bin",
        "small": "ggml-small.bin",
        "medium": "ggml-medium.bin",
        "large": "ggml-large.bin"
    }
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.provider_name = "whisper-cpp"
        
        # Config
        config = config or {}
        self.whisper_cpp_path = config.get('whisper_cpp_path') or self._find_whisper_cpp()
        self.model_dir = Path(config.get('model_dir') or os.getenv('WHISPER_MODEL_DIR', 'models'))
        self.default_model = config.get('model') or os.getenv('WHISPER_MODEL', 'base')
        
        # Metal acceleration สำหรับ Apple Silicon (macOS)
        self.use_metal = config.get('use_metal', None)
        if self.use_metal is None:
            # Auto-detect: ใช้ Metal ถ้าเป็น macOS และ Apple Silicon
            import platform
            if platform.system() == 'Darwin' and platform.machine() == 'arm64':
                self.use_metal = os.getenv('WHISPER_USE_METAL', 'true').lower() == 'true'
            else:
                self.use_metal = False
        
        logger.info(f"[Whisper.cpp] Initialized")
        logger.info(f"[Whisper.cpp]   Executable: {self.whisper_cpp_path}")
        logger.info(f"[Whisper.cpp]   Model dir: {self.model_dir}")
        logger.info(f"[Whisper.cpp]   Default model: {self.default_model}")
        logger.info(f"[Whisper.cpp]   Use Metal: {self.use_metal}")
    
    def _find_whisper_cpp(self) -> str:
        """Find whisper.cpp executable"""
        # Try environment variable first
        env_path = os.getenv('WHISPER_CPP_PATH')
        if env_path and Path(env_path).exists():
            return env_path
        
        # Try common locations
        possible_paths = [
            'whisper.cpp/main',
            'whisper.cpp/build/bin/whisper',
            '/usr/local/bin/whisper',
            '/opt/homebrew/bin/whisper',
            'whisper',
        ]
        
        for path_str in possible_paths:
            path = Path(path_str)
            if path.exists() and path.is_file():
                return str(path.resolve())
            # Try in current directory
            if Path.cwd() / path_str:
                full_path = Path.cwd() / path_str
                if full_path.exists() and full_path.is_file():
                    return str(full_path.resolve())
        
        # If not found, return default (will fail with clear error)
        return 'whisper.cpp/main'
    
    async def transcribe(
        self, 
        audio_path: str, 
        language: str = "th",
        model_size: str = None,
        initial_prompt: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio using whisper.cpp directly
        
        Args:
            audio_path: Path ไปยังไฟล์ audio
            language: ภาษา ("th", "en", "auto")
            model_size: ขนาด model (tiny, base, small, medium, large)
            initial_prompt: Initial prompt (not supported by whisper.cpp)
            
        Returns:
            TranscriptionResult
        """
        audio_path_obj = Path(audio_path)
        
        if not audio_path_obj.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Use default model if not specified
        model = model_size or self.default_model
        if model not in self.SUPPORTED_MODELS:
            logger.warning(f"[Whisper.cpp] Unknown model '{model}', using 'base'")
            model = "base"
        
        # Get model file path
        model_file = self.MODEL_FILES.get(model, "ggml-base.bin")
        model_path = self.model_dir / model_file
        
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}\n"
                f"Please download model using: ./models/download-ggml-model.sh {model}"
            )
        
        logger.info(f"[Whisper.cpp] 🎯 Transcribing: {audio_path}")
        logger.info(f"[Whisper.cpp] 📦 Model: {model} ({model_file})")
        logger.info(f"[Whisper.cpp] 🌍 Language: {language}")
        
        start_time = time.time()
        
        # Create temp file for JSON output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_json:
            output_json_path = tmp_json.name
        
        try:
            # Build command
            cmd = [
                str(self.whisper_cpp_path),
                "-m", str(model_path),
                "-f", str(audio_path_obj.resolve()),
                "-l", language if language != "auto" else "th",
                "-of", output_json_path.replace('.json', ''),  # whisper.cpp adds .json automatically
                "--output-format", "json"
            ]
            
            # Add Metal flag if enabled (Apple Silicon)
            if self.use_metal:
                cmd.append("--use-metal")
                logger.info(f"[Whisper.cpp] 🍎 Using Metal acceleration")
            
            # Run transcription
            logger.info(f"[Whisper.cpp] 📡 Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False  # Don't raise on error, check return code
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"[Whisper.cpp] ❌ Transcription failed: {error_msg}")
                raise Exception(f"Whisper.cpp error: {error_msg}")
            
            # Read JSON output
            # whisper.cpp creates {output_path}.json
            json_output_path = output_json_path.replace('.json', '') + '.json'
            if not Path(json_output_path).exists():
                # Try alternative path
                json_output_path = str(audio_path_obj.parent / audio_path_obj.stem) + '.json'
            
            if not Path(json_output_path).exists():
                raise FileNotFoundError(
                    f"JSON output not found. Expected: {json_output_path}\n"
                    f"Command output: {result.stdout}\n"
                    f"Command error: {result.stderr}"
                )
            
            with open(json_output_path, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            
            processing_time = time.time() - start_time
            
            # Parse result
            text = result_data.get('text', '').strip()
            segments = []
            
            # Convert segments format
            for seg in result_data.get('segments', []):
                segments.append({
                    "start": seg.get('start', 0.0),
                    "end": seg.get('end', 0.0),
                    "text": seg.get('text', '').strip()
                })
            
            logger.info(f"[Whisper.cpp] ✅ Transcription complete!")
            logger.info(f"[Whisper.cpp] 📊 Text length: {len(text)} chars")
            logger.info(f"[Whisper.cpp] 📊 Segments: {len(segments)}")
            logger.info(f"[Whisper.cpp] ⏱️ Processing time: {processing_time:.2f}s")
            
            return TranscriptionResult(
                text=text,
                segments=segments,
                language=language,
                provider='whisper-cpp',
                model=model,
                duration=None,  # whisper.cpp doesn't return this
                processing_time=processing_time
            )
            
        finally:
            # Cleanup temp files
            try:
                if Path(output_json_path).exists():
                    os.unlink(output_json_path)
                if Path(json_output_path).exists():
                    os.unlink(json_output_path)
            except Exception as e:
                logger.warning(f"[Whisper.cpp] Failed to cleanup temp files: {e}")
    
    def health_check(self) -> bool:
        """Check if whisper.cpp is available"""
        try:
            # Check if executable exists
            if not Path(self.whisper_cpp_path).exists():
                logger.warning(f"[Whisper.cpp] ⚠️ Executable not found: {self.whisper_cpp_path}")
                return False
            
            # Try to run whisper.cpp with --help
            result = subprocess.run(
                [str(self.whisper_cpp_path), "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 or "--help" in result.stdout or "--help" in result.stderr:
                logger.info("[Whisper.cpp] ✅ Health check passed")
                return True
            else:
                logger.warning(f"[Whisper.cpp] ⚠️ Health check failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.warning(f"[Whisper.cpp] ⚠️ Health check error: {e}")
            return False
    
    def get_provider_info(self) -> Dict:
        """Return provider information"""
        base_info = super().get_provider_info()
        base_info.update({
            "executable": str(self.whisper_cpp_path),
            "model_dir": str(self.model_dir),
            "default_model": self.default_model,
            "use_metal": self.use_metal,
            "supported_models": self.SUPPORTED_MODELS,
            "model_exists": {
                model: (self.model_dir / self.MODEL_FILES[model]).exists()
                for model in self.SUPPORTED_MODELS
            }
        })
        return base_info

