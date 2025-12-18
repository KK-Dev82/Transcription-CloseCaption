"""
Redis Queue Service สำหรับจัดการ message queue
แทนที่ RabbitMQ ด้วย Redis เพื่อความเสถียรและง่ายต่อการจัดการ
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List
import redis
from datetime import datetime
import uuid
import time

logger = logging.getLogger(__name__)

class RedisQueueService:
    def __init__(self):
        """เริ่มต้น Redis Queue Service"""
        self.redis_client = None
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", "6379"))
        self.db = int(os.getenv("REDIS_DB", "0"))
        self.password = os.getenv("REDIS_PASSWORD", None)
        
        # Queue names
        self.trim_queue = 'video_trim_queue'
        self.merge_queue = 'video_merge_queue'
        self.convert_queue = 'video_convert_queue'
        self.transcription_queue = 'transcription_queue'
        self.transcription_chunk_queue = 'transcription_chunk_queue'
        self.resize_queue = 'video_resize_queue'
        
        # 3-Queue Architecture
        self.transcription_request_queue = 'transcription_request_queue'
        self.audio_extraction_queue = 'audio_extraction_queue'
        
        # ใช้ Storage Factory
        from ..utils.storage_factory import get_storage
        self.json_storage = get_storage()
        
        # Connect to Redis (lazy connection - will retry on first use)
        try:
            self._connect()
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed on init, will retry on first use: {e}")
            self.redis_client = None
    
    def _connect(self):
        """เชื่อมต่อ Redis"""
        try:
            # ตรวจสอบว่ามี REDIS_URL หรือไม่ (สำหรับ Redis.io)
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                # ใช้ Redis URL (สำหรับ Redis.io cloud)
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                logger.info(f"✅ เชื่อมต่อ Redis.io สำเร็จ (using REDIS_URL)")
            else:
                # ใช้ host/port/password (สำหรับ local Redis)
                self.redis_client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                logger.info(f"✅ เชื่อมต่อ Redis สำเร็จ: {self.host}:{self.port}")
            
            # Test connection
            self.redis_client.ping()
        except Exception as e:
            logger.error(f"❌ ไม่สามารถเชื่อมต่อ Redis: {e}")
            self.redis_client = None
            raise
    
    def _ensure_connection(self):
        """ตรวจสอบและเชื่อมต่อ Redis อีกครั้งถ้าจำเป็น"""
        if self.redis_client is None:
            self._connect()
        try:
            self.redis_client.ping()
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("⚠️ Redis connection lost, reconnecting...")
            self._connect()
    
    def send_chunk_transcription_task(self, chunk_task: Dict[str, Any], use_streams: bool = True) -> str:
        """
        ส่ง chunk transcription task ไปยัง Redis queue
        
        Args:
            chunk_task: Chunk task data
            use_streams: ใช้ Redis Streams (มี acknowledgment) หรือ Redis List (เร็วแต่ไม่มี ack)
        """
        try:
            self._ensure_connection()
            
            chunk_task_id = chunk_task.get('task_id')
            if not chunk_task_id:
                chunk_task_id = str(uuid.uuid4())
                chunk_task['task_id'] = chunk_task_id
            
            queue_name = self.transcription_chunk_queue
            
            logger.info(f"📤 Publishing chunk task to Redis {'Stream' if use_streams else 'List'}: {queue_name}")
            logger.info(f"   Chunk Task ID: {chunk_task_id}")
            logger.info(f"   Parent Task ID: {chunk_task.get('parent_task_id')}")
            logger.info(f"   Chunk Index: {chunk_task.get('chunk_index')}/{chunk_task.get('total_chunks')}")
            
            if use_streams:
                # ใช้ Redis Streams (มี acknowledgment support)
                # XADD stream_name * field1 value1 field2 value2
                message_id = self.redis_client.xadd(
                    queue_name,
                    {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) 
                     for k, v in chunk_task.items()}
                )
                logger.info(f"✅ ส่ง chunk task ไปยัง Redis Stream สำเร็จ: {chunk_task_id} (message_id: {message_id})")
                return message_id
            else:
                # ใช้ Redis List (เร็วแต่ไม่มี acknowledgment)
                message = json.dumps(chunk_task)
                # LPUSH = Left Push (add to left/head of list) = FIFO queue
                self.redis_client.lpush(queue_name, message)
                logger.info(f"✅ ส่ง chunk task ไปยัง Redis List สำเร็จ: {chunk_task_id}")
                return chunk_task_id
            
        except Exception as e:
            logger.error(f"❌ Error sending chunk task to Redis queue: {e}", exc_info=True)
            raise
    
    def send_transcription_task(self, task_data: Dict[str, Any], use_streams: bool = True) -> str:
        """ส่ง transcription task ไปยัง Redis queue"""
        try:
            self._ensure_connection()
            
            task_id = task_data.get('task_id')
            if not task_id:
                task_id = str(uuid.uuid4())
                task_data['task_id'] = task_id
            
            queue_name = self.transcription_queue
            
            logger.info(f"📤 Publishing transcription task to Redis {'Stream' if use_streams else 'List'}: {queue_name}")
            logger.info(f"   Task ID: {task_id}")
            
            if use_streams:
                # ใช้ Redis Streams (มี acknowledgment support)
                message_id = self.redis_client.xadd(
                    queue_name,
                    {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) 
                     for k, v in task_data.items()}
                )
                logger.info(f"✅ ส่ง transcription task ไปยัง Redis Stream สำเร็จ: {task_id} (message_id: {message_id})")
                return message_id
            else:
                # ใช้ Redis List (เร็วแต่ไม่มี acknowledgment)
                message = json.dumps(task_data)
                self.redis_client.lpush(queue_name, message)
                logger.info(f"✅ ส่ง transcription task ไปยัง Redis List สำเร็จ: {task_id}")
                return task_id
            
        except Exception as e:
            logger.error(f"❌ Error sending transcription task to Redis queue: {e}", exc_info=True)
            raise
    
    def send_audio_extraction_task(self, task_data: Dict[str, Any]) -> str:
        """ส่ง audio extraction task ไปยัง Redis queue"""
        try:
            self._ensure_connection()
            
            task_id = task_data.get('task_id')
            if not task_id:
                task_id = str(uuid.uuid4())
                task_data['task_id'] = task_id
            
            queue_name = self.audio_extraction_queue
            message = json.dumps(task_data)
            
            logger.info(f"📤 Publishing audio extraction task to Redis queue: {queue_name}")
            logger.info(f"   Task ID: {task_id}")
            
            self.redis_client.lpush(queue_name, message)
            
            logger.info(f"✅ ส่ง audio extraction task ไปยัง Redis queue สำเร็จ: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Error sending audio extraction task to Redis queue: {e}", exc_info=True)
            raise
    
    def consume_transcription_tasks(self, callback, timeout: int = 1, use_streams: bool = True, consumer_group: str = 'workers', consumer_name: str = 'worker1'):
        """
        Consume transcription request tasks from Redis queue (blocking)
        
        Args:
            callback: Function to call with transcription task
            timeout: Timeout in seconds
            use_streams: ใช้ Redis Streams (มี acknowledgment) หรือ Redis List
            consumer_group: Consumer group name (for streams)
            consumer_name: Consumer name (for streams)
        """
        try:
            self._ensure_connection()
            
            queue_name = self.transcription_queue
            
            if use_streams:
                # ใช้ Redis Streams (มี acknowledgment support)
                # สร้าง consumer group ถ้ายังไม่มี
                try:
                    self.redis_client.xgroup_create(
                        queue_name,
                        consumer_group,
                        id='0',
                        mkstream=True
                    )
                    logger.debug(f"✅ Created consumer group: {consumer_group}")
                except Exception as e:
                    # Consumer group อาจมีอยู่แล้ว
                    if 'BUSYGROUP' not in str(e):
                        logger.warning(f"⚠️  Error creating consumer group: {e}")
                
                # XREADGROUP: Read from stream with consumer group
                messages = self.redis_client.xreadgroup(
                    consumer_group,
                    consumer_name,
                    {queue_name: '>'},
                    count=1,
                    block=timeout * 1000  # milliseconds
                )
                
                if messages:
                    for stream, messages_list in messages:
                        for message_id, data in messages_list:
                            try:
                                # Parse message data
                                task_data = {}
                                for k, v in data.items():
                                    key = k.decode() if isinstance(k, bytes) else k
                                    try:
                                        if isinstance(v, bytes):
                                            try:
                                                task_data[key] = json.loads(v.decode())
                                            except (json.JSONDecodeError, UnicodeDecodeError):
                                                task_data[key] = v.decode()
                                        else:
                                            try:
                                                task_data[key] = json.loads(v) if isinstance(v, str) and (v.startswith('{') or v.startswith('[')) else v
                                            except (json.JSONDecodeError, TypeError):
                                                task_data[key] = v
                                    except Exception:
                                        task_data[key] = str(v)
                                
                                # Process message
                                callback(task_data, message_id)
                                
                                # Acknowledge message
                                self.redis_client.xack(queue_name, consumer_group, message_id)
                                logger.debug(f"✅ Acknowledged transcription request: {message_id}")
                                return True
                            except Exception as e:
                                logger.error(f"❌ Error processing transcription request {message_id}: {e}", exc_info=True)
                                # Move to DLQ
                                try:
                                    self.redis_client.xadd(f'{queue_name}.dlq', data)
                                    self.redis_client.xack(queue_name, consumer_group, message_id)
                                    logger.warning(f"⚠️  Moved message {message_id} to DLQ")
                                except Exception as dlq_error:
                                    logger.error(f"❌ Error moving to DLQ: {dlq_error}")
                    return True
                return False
            else:
                # ใช้ Redis List
                result = self.redis_client.brpop(queue_name, timeout=timeout)
                if result:
                    queue_name, message = result
                    task_data = json.loads(message)
                    callback(task_data, None)
                    return True
                return False
        except Exception as e:
            logger.error(f"❌ Error consuming transcription tasks: {e}", exc_info=True)
            return False
    
    def consume_chunk_transcription_tasks(self, callback, timeout: int = 1, use_streams: bool = True, consumer_group: str = 'workers', consumer_name: str = 'worker1'):
        """
        Consume chunk transcription tasks from Redis queue (blocking)
        
        Args:
            callback: Function to call with chunk task
            timeout: Timeout in seconds
            use_streams: ใช้ Redis Streams (มี acknowledgment) หรือ Redis List
            consumer_group: Consumer group name (for streams)
            consumer_name: Consumer name (for streams)
        """
        try:
            self._ensure_connection()
            
            queue_name = self.transcription_chunk_queue
            
            if use_streams:
                # ใช้ Redis Streams (มี acknowledgment support)
                # สร้าง consumer group ถ้ายังไม่มี
                try:
                    self.redis_client.xgroup_create(
                        queue_name,
                        consumer_group,
                        id='0',
                        mkstream=True
                    )
                    logger.debug(f"✅ Created consumer group: {consumer_group}")
                except Exception as e:
                    # Consumer group อาจมีอยู่แล้ว
                    if 'BUSYGROUP' not in str(e):
                        logger.warning(f"⚠️  Error creating consumer group: {e}")
                
                # XREADGROUP: Read from stream with consumer group
                # '>' = read new messages
                messages = self.redis_client.xreadgroup(
                    consumer_group,
                    consumer_name,
                    {queue_name: '>'},
                    count=1,
                    block=timeout * 1000  # milliseconds
                )
                
                if messages:
                    for stream, messages_list in messages:
                        for message_id, data in messages_list:
                            try:
                                # Parse message data
                                chunk_task = {}
                                for k, v in data.items():
                                    key = k.decode() if isinstance(k, bytes) else k
                                    # Try to parse JSON values, otherwise use as string
                                    try:
                                        if isinstance(v, bytes):
                                            try:
                                                chunk_task[key] = json.loads(v.decode())
                                            except (json.JSONDecodeError, UnicodeDecodeError):
                                                chunk_task[key] = v.decode()
                                        else:
                                            try:
                                                chunk_task[key] = json.loads(v) if isinstance(v, str) and (v.startswith('{') or v.startswith('[')) else v
                                            except (json.JSONDecodeError, TypeError):
                                                chunk_task[key] = v
                                    except Exception as e:
                                        # Fallback: use as string
                                        chunk_task[key] = str(v)
                                
                                # Process message
                                callback(chunk_task)
                                
                                # Acknowledge message
                                self.redis_client.xack(queue_name, consumer_group, message_id)
                                logger.debug(f"✅ Acknowledged message: {message_id}")
                                return True
                            except Exception as e:
                                logger.error(f"❌ Error processing message {message_id}: {e}", exc_info=True)
                                # Move to DLQ
                                try:
                                    self.redis_client.xadd(
                                        f'{queue_name}.dlq',
                                        data
                                    )
                                    self.redis_client.xack(queue_name, consumer_group, message_id)
                                    logger.warning(f"⚠️  Moved message {message_id} to DLQ")
                                except Exception as dlq_error:
                                    logger.error(f"❌ Error moving to DLQ: {dlq_error}")
                    return True
                return False
            else:
                # ใช้ Redis List (เร็วแต่ไม่มี acknowledgment)
                # BRPOP = Blocking Right Pop (pop from right/tail of list) = FIFO
                # timeout = 1 second (block for 1 second, then return None if no message)
                result = self.redis_client.brpop(queue_name, timeout=timeout)
                
                if result:
                    queue, message = result
                    chunk_task = json.loads(message)
                    callback(chunk_task)
                    return True
                return False
            
        except Exception as e:
            logger.error(f"❌ Error consuming chunk task from Redis queue: {e}", exc_info=True)
            return False
    
    def consume_audio_extraction_tasks(self, callback, timeout: int = 1):
        """Consume audio extraction tasks from Redis queue (blocking)"""
        try:
            self._ensure_connection()
            
            queue_name = self.audio_extraction_queue
            
            result = self.redis_client.brpop(queue_name, timeout=timeout)
            
            if result:
                queue, message = result
                task_data = json.loads(message)
                callback(task_data)
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Error consuming audio extraction task from Redis queue: {e}", exc_info=True)
            return False
    
    def get_queue_length(self, queue_name: str) -> int:
        """ตรวจสอบจำนวน messages ใน queue"""
        try:
            self._ensure_connection()
            return self.redis_client.llen(queue_name)
        except Exception as e:
            logger.error(f"❌ Error getting queue length: {e}", exc_info=True)
            return 0
    
    def clear_queue(self, queue_name: str):
        """ลบ messages ทั้งหมดใน queue"""
        try:
            self._ensure_connection()
            self.redis_client.delete(queue_name)
            logger.info(f"✅ ลบ queue {queue_name} สำเร็จ")
        except Exception as e:
            logger.error(f"❌ Error clearing queue: {e}", exc_info=True)

