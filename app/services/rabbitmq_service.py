"""
RabbitMQ Service สำหรับจัดการ message queue
"""

import json
import logging
import os
from typing import Dict, Any, Optional
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError
import uuid
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class RabbitMQService:
    def __init__(self):
        """เริ่มต้น RabbitMQ Service"""
        self.connection = None
        self.channel = None
        self.host = "rabbitmq"
        self.port = 5672
        self.username = "admin"
        self.password = "admin123"
        self.virtual_host = "/"
        
        # เพิ่ม JSON storage
        from ..utils.json_storage import JSONStorage
        self.json_storage = JSONStorage()
        
        # Queue names
        self.trim_queue = 'video_trim_queue'
        self.merge_queue = 'video_merge_queue'
        self.convert_queue = 'video_convert_queue'
        self.resize_queue = 'video_resize_queue'
    
    def _connect(self):
        """เชื่อมต่อกับ RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # สร้าง queues
            self.channel.queue_declare(queue=self.trim_queue, durable=True)
            self.channel.queue_declare(queue=self.merge_queue, durable=True)
            self.channel.queue_declare(queue=self.convert_queue, durable=True)
            self.channel.queue_declare(queue=self.resize_queue, durable=True)
            
            logger.info("เชื่อมต่อ RabbitMQ สำเร็จ")
            
        except AMQPConnectionError as e:
            logger.error(f"ไม่สามารถเชื่อมต่อ RabbitMQ: {e}")
            raise
    
    def _ensure_connection(self):
        """ตรวจสอบการเชื่อมต่อและเชื่อมต่อใหม่หากจำเป็น"""
        if not self.connection or self.connection.is_closed:
            logger.info("เชื่อมต่อ RabbitMQ ใหม่...")
            self._connect()
    
    def send_trim_task(self, input_file: str, start_time: float, end_time: float, 
                      output_format: str = "mp4", quality: str = "medium", 
                      segment_number: int = 1) -> str:
        """ส่งงานตัดวิดีโอไปยัง queue"""
        try:
            # เชื่อมต่อ RabbitMQ ก่อนใช้งาน
            self._ensure_connection()
            
            task_id = str(uuid.uuid4())
            task_data = {
                "task_id": task_id,
                "task_type": "trim",
                "input_file": input_file,
                "start_time": start_time,
                "end_time": end_time,
                "output_format": output_format,
                "quality": quality,
                "segment_number": segment_number,
                "status": "pending",
                "created_at": time.time()
            }
            
            # บันทึก task ลง storage
            self.json_storage.save_video_task(task_id, task_data)
            
            # ส่งไปยัง queue
            self.channel.basic_publish(
                exchange='',
                routing_key='video_trim_queue',
                body=json.dumps(task_data)
            )
            
            logger.info(f"ส่งงานตัดวิดีโอไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่งงานตัดวิดีโอ: {e}")
            raise
    
    def send_merge_task(self, input_files: list, output_format: str = "mp4",
                       quality: str = "medium") -> str:
        """ส่ง merge video task ไปยัง queue"""
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "type": "merge",
            "status": "pending",
            "input_files": input_files,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        try:
            self._ensure_connection()
            
            # ส่ง message ไปยัง queue
            self.channel.basic_publish(
                exchange='',
                routing_key=self.merge_queue,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"ส่ง merge task ไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง merge task: {e}")
            raise
    
    def send_convert_task(self, input_file: str, output_format: str,
                         quality: str = "medium") -> str:
        """ส่ง convert format task ไปยัง queue"""
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "type": "convert",
            "status": "pending",
            "input_file": input_file,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        try:
            self._ensure_connection()
            
            # ส่ง message ไปยัง queue
            self.channel.basic_publish(
                exchange='',
                routing_key=self.convert_queue,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"ส่ง convert task ไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง convert task: {e}")
            raise
    
    def send_resize_task(self, input_file: str, width: int, height: int,
                        output_format: str = "mp4", quality: str = "medium") -> str:
        """ส่ง resize video task ไปยัง queue"""
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "type": "resize",
            "status": "pending",
            "input_file": input_file,
            "width": width,
            "height": height,
            "output_format": output_format,
            "quality": quality,
            "created_at": datetime.now().isoformat()
        }
        
        try:
            self._ensure_connection()
            
            # ส่ง message ไปยัง queue
            self.channel.basic_publish(
                exchange='',
                routing_key=self.resize_queue,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"ส่ง resize task ไปยัง queue: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง resize task: {e}")
            raise
    
    def send_batch_tasks(self, tasks: list) -> list:
        """ส่ง batch tasks ไปยัง queue"""
        task_ids = []
        
        for task in tasks:
            task_type = task.get('type')
            
            if task_type == 'trim':
                task_id = self.send_trim_task(
                    input_file=task['input_file'],
                    start_time=task['start_time'],
                    end_time=task['end_time'],
                    output_format=task.get('output_format', 'mp4'),
                    quality=task.get('quality', 'medium')
                )
            elif task_type == 'merge':
                task_id = self.send_merge_task(
                    input_files=task['input_files'],
                    output_format=task.get('output_format', 'mp4'),
                    quality=task.get('quality', 'medium')
                )
            elif task_type == 'convert':
                task_id = self.send_convert_task(
                    input_file=task['input_file'],
                    output_format=task['output_format'],
                    quality=task.get('quality', 'medium')
                )
            elif task_type == 'resize':
                task_id = self.send_resize_task(
                    input_file=task['input_file'],
                    width=task['width'],
                    height=task['height'],
                    output_format=task.get('output_format', 'mp4'),
                    quality=task.get('quality', 'medium')
                )
            else:
                logger.warning(f"ไม่รู้จัก task type: {task_type}")
                continue
            
            task_ids.append(task_id)
        
        return task_ids
    
    def get_queue_info(self) -> Dict[str, Any]:
        """ดึงข้อมูล queue"""
        try:
            self._ensure_connection()
            
            queue_info = {}
            
            # ตรวจสอบแต่ละ queue
            for queue_name in [self.trim_queue, self.merge_queue, 
                             self.convert_queue, self.resize_queue]:
                method = self.channel.queue_declare(queue=queue_name, passive=True)
                queue_info[queue_name] = {
                    'name': queue_name,
                    'message_count': method.method.message_count,
                    'consumer_count': method.method.consumer_count
                }
            
            return queue_info
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล queue: {e}")
            return {}
    
    def purge_queue(self, queue_name: str) -> bool:
        """ลบ messages ทั้งหมดใน queue"""
        try:
            self._ensure_connection()
            
            if queue_name in [self.trim_queue, self.merge_queue, 
                            self.convert_queue, self.resize_queue]:
                self.channel.queue_purge(queue=queue_name)
                logger.info(f"ลบ messages ใน queue {queue_name} เรียบร้อย")
                return True
            else:
                logger.warning(f"ไม่พบ queue: {queue_name}")
                return False
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการลบ queue: {e}")
            return False
    
    def close(self):
        """ปิดการเชื่อมต่อ"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("ปิดการเชื่อมต่อ RabbitMQ")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 