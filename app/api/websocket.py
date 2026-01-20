"""
WebSocket API Endpoints สำหรับ Real-time Transcription Updates
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import json
import asyncio
import os
import uuid
import time
import tempfile
import wave
from datetime import datetime, timezone

from ..services.websocket_service import websocket_manager
from ..services.close_caption_config import CloseCaptionConfig
from ..utils.dedupe_text import dedupe_text
from ..utils.thai_postprocess import postprocess_thai_text

logger = logging.getLogger(__name__)
router = APIRouter()

MOCK_MODE = os.getenv("TRANSCRIPTION_MOCK_MODE", "false").lower() == "true"

# Producer soft-lock (in-memory)
_active_producer_by_meeting: dict[str, dict] = {}
_PRODUCER_TTL_SECONDS = float(os.getenv("FE_CC_PRODUCER_TTL_SECONDS", "20"))

# Rolling window inference parameters (server-side)
_DEFAULT_SAMPLE_RATE = 16000
_DEFAULT_CHANNELS = 1
_WINDOW_SECONDS = float(os.getenv("FE_CC_WINDOW_SECONDS", "3.0"))          # ✅ เพิ่มจาก 2.0 เป็น 3.0 เพื่อให้ได้ประโยคสมบูรณ์ขึ้น
_STEP_SECONDS = float(os.getenv("FE_CC_STEP_SECONDS", "1.0"))              # ✅ เพิ่มจาก 0.5 เป็น 1.0 เพื่อลด requests และรอประโยคสมบูรณ์
_MIN_WINDOW_SECONDS = float(os.getenv("FE_CC_MIN_WINDOW_SECONDS", "2.0"))  # ✅ เพิ่มจาก 1.2 เป็น 2.0 เพื่อให้มีเสียงพอสำหรับประโยค
_SILENCE_THRESHOLD_SECONDS = float(os.getenv("FE_CC_SILENCE_THRESHOLD", "0.8"))  # ✅ รอ silence 0.8s ก่อนส่ง final (sentence boundary)

_last_emitted_text_by_meeting: dict[str, str] = {}
_last_silence_time_by_meeting: dict[str, float] = {}  # ✅ เก็บเวลาที่มีเสียงล่าสุด

_whisper_service_singleton = None

def _get_whisper_service():
    global _whisper_service_singleton
    if _whisper_service_singleton is None and not MOCK_MODE:
        # Lazy init เพื่อไม่ block startup
        from ..services.whisper_service import WhisperService
        _whisper_service_singleton = WhisperService()
    return _whisper_service_singleton

def _now_s() -> float:
    return time.time()

def _producer_lock_is_active(meeting_id: str) -> bool:
    info = _active_producer_by_meeting.get(meeting_id)
    if not info:
        return False
    return (_now_s() - float(info.get("last_heartbeat_s", 0.0))) < _PRODUCER_TTL_SECONDS

def _acquire_or_refresh_producer_lock(meeting_id: str, session_id: str) -> tuple[bool, Optional[str]]:
    """
    Returns: (ok, current_owner_session_id_if_conflict)
    """
    info = _active_producer_by_meeting.get(meeting_id)
    if info and (_now_s() - float(info.get("last_heartbeat_s", 0.0))) < _PRODUCER_TTL_SECONDS:
        owner = str(info.get("session_id", ""))
        if owner and owner != session_id:
            return False, owner
    _active_producer_by_meeting[meeting_id] = {
        "session_id": session_id,
        "last_heartbeat_s": _now_s(),
    }
    return True, None

def _release_producer_lock_if_owner(meeting_id: str, session_id: str) -> None:
    info = _active_producer_by_meeting.get(meeting_id)
    if not info:
        return
    if str(info.get("session_id", "")) == session_id:
        _active_producer_by_meeting.pop(meeting_id, None)

def _pcm16_bytes_per_second(sample_rate: int, channels: int) -> int:
    return int(sample_rate) * int(channels) * 2

async def _safe_send_json(ws: WebSocket, payload: dict) -> None:
    try:
        await ws.send_text(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass

@router.websocket("/ws/transcription/{user_id}")
async def websocket_transcription_endpoint(
    websocket: WebSocket, 
    user_id: str,
    task_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint สำหรับ real-time transcription updates
    
    Usage:
    - ws://localhost:8001/ws/transcription/{user_id}
    - ws://localhost:8001/ws/transcription/{user_id}?task_id={task_id}
    """
    try:
        # เชื่อมต่อ user
        await websocket_manager.connect_user(websocket, user_id)
        
        # Subscribe task ถ้ามี
        if task_id:
            await websocket_manager.subscribe_task(user_id, task_id)
        
        # รอรับข้อความจาก client พร้อม keepalive
        
        async def heartbeat():
            """ส่ง ping ทุก 30 วินาที"""
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_text(json.dumps({
                        "type": "ping",
                        "timestamp": datetime.now().isoformat()
                    }))
                except Exception:
                    break
        
        # เริ่ม heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat())
        
        try:
            while True:
                try:
                    # รอ message หรือ timeout ใน 60 วินาที
                    data = await asyncio.wait_for(
                        websocket.receive_text(), 
                        timeout=60.0
                    )
                    message = json.loads(data)
                    
                    # Handle different message types
                    await handle_websocket_message(websocket, user_id, message)
                    
                except asyncio.TimeoutError:
                    # ไม่มี message ใน 60 วินาที - ส่ง ping
                    await websocket.send_text(json.dumps({
                        "type": "keepalive",
                        "message": "Connection active"
                    }))
                    continue
                    
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
                except WebSocketDisconnect:
                    break
        finally:
            heartbeat_task.cancel()
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        await websocket_manager.disconnect_user(websocket, user_id)

async def handle_websocket_message(websocket: WebSocket, user_id: str, message: dict):
    """จัดการข้อความที่ได้รับจาก WebSocket client"""
    
    message_type = message.get("type")
    
    if message_type == "subscribe":
        # Subscribe ใหม่
        task_id = message.get("task_id")
        if task_id:
            await websocket_manager.subscribe_task(user_id, task_id)
        else:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "task_id required for subscription"
            }))
    
    elif message_type == "unsubscribe":
        # Unsubscribe
        task_id = message.get("task_id")
        if task_id:
            await websocket_manager.unsubscribe_task(user_id, task_id)
    
    elif message_type == "ping":
        # Health check
        await websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": message.get("timestamp")
        }))
    
    elif message_type == "pong":
        # Acknowledge pong response from client
        # No response needed, just log for debugging
        logger.debug(f"Received pong from user {user_id}")
    
    elif message_type == "get_stats":
        # ส่งสถิติ (สำหรับ admin)
        stats = websocket_manager.get_stats()
        await websocket.send_text(json.dumps({
            "type": "stats",
            "data": stats
        }))
    
    else:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        }))

@router.websocket("/ws/caption/{user_id}")
async def websocket_caption_endpoint(
    websocket: WebSocket, 
    user_id: str,
    session_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint สำหรับ real-time close caption (Legacy - ใช้ user_id เป็น path parameter)
    
    Usage:
    - ws://localhost:8001/ws/caption/{user_id}
    - ws://localhost:8001/ws/caption/{user_id}?session_id={session_id}
    
    ⚠️ Deprecated: ใช้ /api/ws/captions แทน (V3 compliant)
    """
    try:
        # เชื่อมต่อ user
        await websocket_manager.connect_user(websocket, user_id)
        
        # Subscribe session ถ้ามี
        if session_id:
            await websocket_manager.subscribe_task(user_id, session_id)
        
        # รอรับข้อความจาก client พร้อม keepalive
        async def heartbeat():
            """ส่ง ping ทุก 30 วินาที"""
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_text(json.dumps({
                        "type": "ping",
                        "timestamp": datetime.now().isoformat()
                    }))
                except Exception:
                    break
        
        # เริ่ม heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat())
        
        try:
            while True:
                try:
                    # รอ message หรือ timeout ใน 60 วินาที
                    data = await asyncio.wait_for(
                        websocket.receive_text(), 
                        timeout=60.0
                    )
                    message = json.loads(data)
                    
                    # Handle different message types
                    await handle_caption_websocket_message(websocket, user_id, message)
                    
                except asyncio.TimeoutError:
                    # ไม่มี message ใน 60 วินาที - ส่ง ping
                    await websocket.send_text(json.dumps({
                        "type": "keepalive",
                        "message": "Connection active"
                    }))
                    continue
                    
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
                except WebSocketDisconnect:
                    break
        finally:
            heartbeat_task.cancel()
                
    except WebSocketDisconnect:
        logger.info(f"Caption WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"Caption WebSocket error for user {user_id}: {e}")
    finally:
        await websocket_manager.disconnect_user(websocket, user_id)

@router.websocket("/api/ws/captions")
async def websocket_captions_v3_endpoint(
    websocket: WebSocket,
    meeting_id: str = Query(..., description="Meeting ID (required)"),
    session_id: Optional[str] = Query(None, description="Session ID (optional)")
):
    """
    ✅ V3 Compliant: WebSocket endpoint สำหรับ real-time close caption
    
    Usage:
    - ws://localhost:8012/api/ws/captions?meeting_id={meeting_id}
    - ws://localhost:8012/api/ws/captions?meeting_id={meeting_id}&session_id={session_id}
    
    Events:
    - type: "sync" - Clock synchronization
    - type: "status" - Status updates
    - type: "heartbeat" - Keepalive
    - type: "partial" - Provisional captions
    - type: "final" - Final captions
    - type: "error" - Error events
    """
    try:
        # เชื่อมต่อ user (ใช้ meeting_id เป็น user_id)
        await websocket_manager.connect_user(websocket, meeting_id)
        
        # Subscribe session ถ้ามี
        if session_id:
            await websocket_manager.subscribe_task(meeting_id, session_id)
        
        # ส่ง sync event ทันทีเมื่อเชื่อมต่อ
        await websocket.send_text(json.dumps({
            "type": "sync",
            "meeting_id": meeting_id,
            "session_id": session_id or "",
            "seq": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "clock": {
                "meeting_start_utc": datetime.now(timezone.utc).isoformat(),
                "server_utc": datetime.now(timezone.utc).isoformat(),
                "timebase": "ms"
            }
        }))
        
        # ส่ง status event
        await websocket.send_text(json.dumps({
            "type": "status",
            "meeting_id": meeting_id,
            "session_id": session_id or "",
            "seq": 2,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "streaming",
            "message": "Connected and ready to receive captions"
        }))
        
        # รอรับข้อความจาก client พร้อม keepalive
        async def heartbeat():
            """ส่ง heartbeat ทุก 30 วินาที"""
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_text(json.dumps({
                        "type": "heartbeat",
                        "meeting_id": meeting_id,
                        "session_id": session_id or "",
                        "seq": 0,  # Will be incremented
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }))
                except Exception:
                    break
        
        # เริ่ม heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat())
        seq_counter = 3  # Start from 3 (after sync and status)
        
        try:
            while True:
                try:
                    # รอ message หรือ timeout ใน 60 วินาที
                    data = await asyncio.wait_for(
                        websocket.receive_text(), 
                        timeout=60.0
                    )
                    message = json.loads(data)
                    
                    # Handle different message types
                    message_type = message.get("type")
                    if message_type == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "meeting_id": meeting_id,
                            "session_id": session_id or "",
                            "seq": seq_counter,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "timestamp": message.get("timestamp")
                        }))
                        seq_counter += 1
                    elif message_type == "subscribe":
                        # Subscribe session
                        sub_session_id = message.get("session_id")
                        if sub_session_id:
                            await websocket_manager.subscribe_task(meeting_id, sub_session_id)
                    elif message_type == "unsubscribe":
                        # Unsubscribe session
                        unsub_session_id = message.get("session_id")
                        if unsub_session_id:
                            await websocket_manager.unsubscribe_task(meeting_id, unsub_session_id)
                    
                except asyncio.TimeoutError:
                    # ไม่มี message ใน 60 วินาที - heartbeat จะส่งอัตโนมัติ
                    continue
                    
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "meeting_id": meeting_id,
                        "session_id": session_id or "",
                        "seq": seq_counter,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "error": {
                            "code": "INVALID_JSON",
                            "message": "Invalid JSON format"
                        }
                    }))
                    seq_counter += 1
                except WebSocketDisconnect:
                    break
        finally:
            heartbeat_task.cancel()
                
    except WebSocketDisconnect:
        logger.info(f"V3 Caption WebSocket disconnected for meeting {meeting_id}")
    except Exception as e:
        logger.error(f"V3 Caption WebSocket error for meeting {meeting_id}: {e}")
    finally:
        await websocket_manager.disconnect_user(websocket, meeting_id)

@router.websocket("/api/ws/ingest-audio")
async def websocket_audio_ingest_endpoint(
    websocket: WebSocket,
    meeting_id: str = Query(..., description="Meeting ID (required)"),
    session_id: Optional[str] = Query(None, description="Producer session ID (optional)")
):
    """
    ✅ FE Live Caption Producer Uplink (PCM16 binary frames)
    - รับ binary frames (PCM16LE) ต่อเนื่องจาก browser (AudioWorklet)
    - ทำ producer soft-lock ต่อ meeting เพื่อให้มี producer ได้เพียง 1 คน
    - ทำ rolling window transcription เพื่อให้ UX ใกล้ realtime
    - broadcast caption events ไปยัง /api/ws/captions โดยใช้ meeting_id เป็น key
    """
    producer_session_id = session_id or str(uuid.uuid4())
    await websocket.accept()

    ok, owner = _acquire_or_refresh_producer_lock(meeting_id, producer_session_id)
    if not ok:
        await _safe_send_json(websocket, {
            "type": "error",
            "meeting_id": meeting_id,
            "session_id": producer_session_id,
            "error": {
                "code": "PRODUCER_LOCKED",
                "message": f"Meeting already has an active producer (owner_session_id={owner})"
            }
        })
        await websocket.close(code=4009)
        return

    await _safe_send_json(websocket, {
        "type": "status",
        "meeting_id": meeting_id,
        "session_id": producer_session_id,
        "status": "producer_connected",
        "message": "Audio ingest connected. Send JSON init then PCM16 binary frames."
    })

    # Config (can be overridden by init message)
    sample_rate = _DEFAULT_SAMPLE_RATE
    channels = _DEFAULT_CHANNELS
    audio_format = "s16le"
    model_size = CloseCaptionConfig.MODEL_SIZE
    language = CloseCaptionConfig.LANGUAGE

    ring = bytearray()
    seq_counter = 1

    min_bytes = int(_pcm16_bytes_per_second(sample_rate, channels) * _MIN_WINDOW_SECONDS)
    window_bytes = int(_pcm16_bytes_per_second(sample_rate, channels) * _WINDOW_SECONDS)

    stop_event = asyncio.Event()

    async def infer_loop():
        nonlocal seq_counter, min_bytes, window_bytes
        pending_text = ""  # ✅ เก็บข้อความที่รอส่ง (รอ silence ก่อน)
        pending_start_ms = None
        
        while not stop_event.is_set():
            try:
                await asyncio.sleep(_STEP_SECONDS)
                if len(ring) < max(1, min_bytes):
                    continue

                # Take the latest window
                chunk = bytes(ring[-window_bytes:]) if len(ring) >= window_bytes else bytes(ring)

                # ✅ Simple VAD: ตรวจสอบว่า chunk มีเสียงหรือไม่ (ตรวจจาก amplitude)
                # ถ้าไม่มีเสียง → ตรวจสอบ silence duration
                has_audio = False
                if len(chunk) >= 2:
                    # ตรวจสอบ amplitude (PCM16: -32768 to 32767)
                    samples = []
                    for i in range(0, min(len(chunk) - 1, 1600), 2):  # sample ทุก 0.1s
                        val = int.from_bytes(chunk[i:i+2], byteorder='little', signed=True)
                        samples.append(abs(val))
                    avg_amplitude = sum(samples) / len(samples) if samples else 0
                    has_audio = avg_amplitude > 500  # threshold สำหรับเสียง (ปรับได้)

                now_s = _now_s()
                if has_audio:
                    _last_silence_time_by_meeting[meeting_id] = now_s
                else:
                    # ไม่มีเสียง → ตรวจสอบ silence duration
                    last_silence = _last_silence_time_by_meeting.get(meeting_id, now_s)
                    silence_duration = now_s - last_silence
                    
                    # ✅ ถ้ามี pending text และ silence นานพอ → ส่ง final
                    if pending_text and silence_duration >= _SILENCE_THRESHOLD_SECONDS:
                        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                        event = {
                            "type": "final",
                            "meeting_id": meeting_id,
                            "session_id": producer_session_id,
                            "seq": seq_counter,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "chunk_index": seq_counter,
                            "chunk_start_ms": pending_start_ms or (now_ms - int(_WINDOW_SECONDS * 1000)),
                            "chunk_duration_ms": max(1, now_ms - (pending_start_ms or (now_ms - int(_WINDOW_SECONDS * 1000)))),
                            "language": language,
                            "model": model_size,
                            "provider": "faster-whisper" if not MOCK_MODE else "mock",
                            "text": pending_text,
                            "segments": [
                                {
                                    "id": f"seg-{seq_counter}-0",
                                    "t0_ms": pending_start_ms or (now_ms - int(_WINDOW_SECONDS * 1000)),
                                    "t1_ms": now_ms,
                                    "text": pending_text,
                                    "confidence": 0.0,
                                    "is_final": True,
                                    "speaker": None
                                }
                            ]
                        }
                        await websocket_manager.broadcast_to_meeting(meeting_id, event)
                        _last_emitted_text_by_meeting[meeting_id] = pending_text
                        pending_text = ""
                        pending_start_ms = None
                        seq_counter += 1
                        continue

                # ✅ ถ้ายังไม่มีเสียง หรือ silence ยังไม่พอ → ทำ transcription (partial)
                # MOCK: emit basic telemetry as caption
                if MOCK_MODE:
                    text = f"[MOCK] pcm_bytes={len(chunk)}"
                else:
                    # Write PCM as WAV to temp file
                    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    tmp_path = tmp.name
                    tmp.close()
                    try:
                        with wave.open(tmp_path, "wb") as wf:
                            wf.setnchannels(channels)
                            wf.setsampwidth(2)
                            wf.setframerate(sample_rate)
                            wf.writeframes(chunk)

                        whisper_service = _get_whisper_service()
                        if whisper_service is None:
                            continue
                        result = whisper_service.transcribe_file(
                            audio_path=tmp_path,
                            model_size=model_size,
                            language=language,
                            use_thai_processor=(language == "th")
                        )
                        text = (result.get("text") or "").strip()
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass

                if not text:
                    continue

                # Postprocess
                if CloseCaptionConfig.POSTPROCESS_ENABLED and language == "th":
                    try:
                        text = postprocess_thai_text(
                            text,
                            normalize=CloseCaptionConfig.POSTPROCESS_NORMALIZE,
                            fix_words=True,
                            word_segmentation=False  # FE overlay จะจัดรูปแบบเอง
                        ).strip()
                    except Exception:
                        pass

                if not text:
                    continue

                # ✅ ใช้ dedupe เพื่อหาข้อความใหม่ (ไม่ซ้ำกับที่ส่งไปแล้ว)
                last_emitted = _last_emitted_text_by_meeting.get(meeting_id, "")
                if CloseCaptionConfig.DEDUPE_ENABLED:
                    try:
                        new_text = dedupe_text(text, last_emitted, max_match_length=CloseCaptionConfig.DEDUPE_MAX_MATCH_LENGTH).strip()
                    except Exception:
                        new_text = text
                else:
                    # ถ้าไม่ใช้ dedupe → เปรียบเทียบแบบง่าย
                    if text.startswith(last_emitted):
                        new_text = text[len(last_emitted):].strip()
                    else:
                        new_text = text

                if new_text:
                    # ✅ เก็บ pending text (รอ silence ก่อนส่ง final)
                    if not pending_text:
                        pending_start_ms = int(datetime.now(timezone.utc).timestamp() * 1000) - int(_WINDOW_SECONDS * 1000)
                    pending_text = (pending_text + " " + new_text).strip()
                    
                    # ✅ ส่ง partial event ทันที (เพื่อให้เห็นข้อความแบบ realtime)
                    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                    partial_event = {
                        "type": "partial",
                        "meeting_id": meeting_id,
                        "session_id": producer_session_id,
                        "seq": seq_counter,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "text": pending_text,
                        "is_final": False
                    }
                    await websocket_manager.broadcast_to_meeting(meeting_id, partial_event)
            except Exception as e:
                logger.warning(f"[WS ingest] infer_loop error meeting_id={meeting_id}: {e}")

    infer_task = asyncio.create_task(infer_loop())

    try:
        while True:
            message = await websocket.receive()
            if "text" in message and message["text"] is not None:
                try:
                    payload = json.loads(message["text"])
                except Exception:
                    continue
                msg_type = payload.get("type")
                if msg_type == "init":
                    # Allow overriding config
                    sample_rate = int(payload.get("sample_rate") or sample_rate)
                    channels = int(payload.get("channels") or channels)
                    audio_format = str(payload.get("format") or audio_format)
                    model_size = str(payload.get("model_size") or model_size)
                    language = str(payload.get("language") or language)
                    min_bytes = int(_pcm16_bytes_per_second(sample_rate, channels) * _MIN_WINDOW_SECONDS)
                    window_bytes = int(_pcm16_bytes_per_second(sample_rate, channels) * _WINDOW_SECONDS)
                elif msg_type == "heartbeat":
                    _acquire_or_refresh_producer_lock(meeting_id, producer_session_id)
                elif msg_type == "stop":
                    break
            elif "bytes" in message and message["bytes"] is not None:
                b = message["bytes"]
                if audio_format != "s16le":
                    # Only PCM16LE supported in v1
                    continue
                ring.extend(b)
                # Keep only last ~10 seconds to cap memory
                max_keep = _pcm16_bytes_per_second(sample_rate, channels) * 10
                if len(ring) > max_keep:
                    ring[:] = ring[-max_keep:]
                _acquire_or_refresh_producer_lock(meeting_id, producer_session_id)
            else:
                # disconnect
                break
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        try:
            infer_task.cancel()
        except Exception:
            pass
        _release_producer_lock_if_owner(meeting_id, producer_session_id)
        try:
            await websocket.close()
        except Exception:
            pass

async def handle_caption_websocket_message(websocket: WebSocket, user_id: str, message: dict):
    """จัดการข้อความที่ได้รับจาก Caption WebSocket client"""
    
    message_type = message.get("type")
    
    if message_type == "subscribe":
        # Subscribe ใหม่
        session_id = message.get("session_id")
        if session_id:
            await websocket_manager.subscribe_task(user_id, session_id)
        else:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "session_id required for subscription"
            }))
    
    elif message_type == "unsubscribe":
        # Unsubscribe
        session_id = message.get("session_id")
        if session_id:
            await websocket_manager.unsubscribe_task(user_id, session_id)
    
    elif message_type == "ping":
        # Health check
        await websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": message.get("timestamp")
        }))
    
    elif message_type == "pong":
        # Acknowledge pong response from client
        logger.debug(f"Received pong from caption user {user_id}")
    
    elif message_type == "get_stats":
        # ส่งสถิติ (สำหรับ admin)
        stats = websocket_manager.get_stats()
        await websocket.send_text(json.dumps({
            "type": "stats",
            "data": stats
        }))
    
    else:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        }))

@router.get("/ws/stats")
async def get_websocket_stats():
    """API endpoint สำหรับดู WebSocket statistics"""
    return {
        "websocket_stats": websocket_manager.get_stats(),
        "status": "active"
    }