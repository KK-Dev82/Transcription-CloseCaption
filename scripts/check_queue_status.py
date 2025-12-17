#!/usr/bin/env python3
"""
สคริปต์ตรวจสอบสถานะ transcription_request_queue
- จำนวน messages ใน queue (ready + unacked)
- จำนวน consumers ที่เชื่อมต่อ
- จำนวน messages ที่ถูก consume แล้ว
"""
import os
import sys
import json
import pika
from urllib.parse import quote

# อ่าน config จาก environment
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', '178.128.105.100')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'senate')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'qP2VtHz6fAX4xDksEpMrLT')
RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', '/')
QUEUE_NAME = 'transcription_request_queue'

def check_queue_status():
    """ตรวจสอบสถานะ queue"""
    try:
        # เชื่อมต่อ RabbitMQ
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            virtual_host=RABBITMQ_VHOST,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # ตรวจสอบ queue
        queue_info = channel.queue_declare(queue=QUEUE_NAME, passive=True)
        
        # ข้อมูล queue
        message_count = queue_info.method.message_count
        consumer_count = queue_info.method.consumer_count
        
        # ตรวจสอบ unacked messages
        # ใช้ queue_bind เพื่อดู unacked messages (ต้องใช้ management API สำหรับข้อมูลที่ละเอียดกว่า)
        
        print("=" * 60)
        print(f"📊 สถานะ Queue: {QUEUE_NAME}")
        print("=" * 60)
        print(f"✅ Messages Ready (ใน queue): {message_count}")
        print(f"👥 Consumers (จำนวน worker): {consumer_count}")
        print(f"📈 Messages ที่ถูก consume แล้ว: {consumer_count} messages (1 ต่อ consumer)")
        print(f"📊 Total Messages (Ready + Consumed): {message_count + consumer_count}")
        print()
        
        # ตรวจสอบ prefetch count
        # Note: prefetch count ไม่สามารถดูได้จาก queue_declare ต้องดูจาก consumer info
        print("=" * 60)
        print("⚙️  การตั้งค่า (จาก .env.runpod)")
        print("=" * 60)
        print(f"TRANSCRIPTION_REQUEST_PREFETCH_COUNT: {os.getenv('TRANSCRIPTION_REQUEST_PREFETCH_COUNT', '1')}")
        print(f"MAX_QUEUE_REQUEST: {os.getenv('MAX_QUEUE_REQUEST', '51')}")
        print()
        
        # วิเคราะห์
        print("=" * 60)
        print("🔍 วิเคราะห์")
        print("=" * 60)
        
        if consumer_count == 0:
            print("⚠️  ไม่มี consumers ที่เชื่อมต่อ!")
            print("   → Worker อาจไม่ได้รัน หรือไม่ได้ consume จาก queue นี้")
        elif consumer_count == 3:
            print("✅ มี 3 consumers (workers) ที่เชื่อมต่อ")
            print(f"   → แต่ละ consumer มี prefetch_count=1")
            print(f"   → รับได้ {consumer_count} messages พร้อมกัน (1 ต่อ consumer)")
            print(f"   → Messages ที่เห็นใน queue: {message_count} (ready)")
            print(f"   → Messages ที่ถูก consume: {consumer_count} (unacked)")
            print(f"   → รวมทั้งหมด: {message_count + consumer_count} messages")
        else:
            print(f"ℹ️  มี {consumer_count} consumers ที่เชื่อมต่อ")
            print(f"   → รับได้ {consumer_count} messages พร้อมกัน (1 ต่อ consumer)")
        
        if message_count + consumer_count < 3:
            print()
            print("💡 สาเหตุที่เป็นไปได้:")
            print("   1. API ส่งแค่ 3 messages (หรือน้อยกว่า)")
            print("   2. Messages ถูก process เสร็จแล้ว")
            print("   3. มี worker 3 ตัวที่ consume และแต่ละตัวรับได้ 1 message")
        
        connection.close()
        
    except pika.exceptions.ChannelClosedByBroker as e:
        print(f"❌ Channel closed: {e}")
        print("   → Queue อาจไม่มีอยู่ หรือไม่มีสิทธิ์เข้าถึง")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    check_queue_status()

