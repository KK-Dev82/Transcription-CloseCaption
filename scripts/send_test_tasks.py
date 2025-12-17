#!/usr/bin/env python3
"""
Script to send test mode messages to transcription_request_queue
"""
import sys
import os
sys.path.insert(0, '/workspace/transcription-service')

import json
import uuid
import time
import pika
from dotenv import load_dotenv

# Load environment
load_dotenv('/workspace/transcription-service/env.runpod')

# RabbitMQ connection
host = os.getenv('RABBITMQ_HOST', 'localhost')
port = int(os.getenv('RABBITMQ_PORT', '5672'))
username = os.getenv('RABBITMQ_USER', 'admin')
password = os.getenv('RABBITMQ_PASSWORD', 'admin123')
vhost = os.getenv('RABBITMQ_VHOST', '/')

# Connect
credentials = pika.PlainCredentials(username, password)
parameters = pika.ConnectionParameters(
    host=host,
    port=port,
    virtual_host=vhost,
    credentials=credentials,
    heartbeat=600,
    blocked_connection_timeout=300
)

connection = pika.BlockingConnection(parameters)
channel = connection.channel()

# Enable publisher confirms
channel.confirm_delivery()

count = int(sys.argv[1]) if len(sys.argv) > 1 else 25
task_ids = []
success_count = 0

print(f"Sending {count} test tasks...")

for i in range(count):
    test_task_id = f"test-{uuid.uuid4()}"
    task_ids.append(test_task_id)
    
    test_message = {
        "task_id": test_task_id,
        "task_type": "transcription_request",
        "test_mode": True,
        "test_message": f"Phase 3 Test message #{i+1}",
        "file_path": None,
        "file_url": None,
        "file_name": f"test_file_phase3_{i+1}.mp4",
        "language": "th",
        "model_size": "base",
        "chunk_duration": 30,
        "use_chunking": False,
        "display_mode": "full_text",
        "status": "pending",
        "created_at": time.time(),
        "callback_url": None,
        "job_id": None,
        "user_id": "test_user_phase3"
    }
    
    try:
        channel.basic_publish(
            exchange='',
            routing_key='transcription_request_queue',
            body=json.dumps(test_message),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json',
                priority=5
            ),
            mandatory=True
        )
        success_count += 1
        print(f"  Task {i+1}: {test_task_id} ✅")
    except Exception as e:
        print(f"  Task {i+1}: {test_task_id} ❌ Error: {e}")

connection.close()

# Output results
result = {
    "total": count,
    "successful": success_count,
    "failed": count - success_count,
    "task_ids": task_ids
}

print(json.dumps(result, indent=2))

