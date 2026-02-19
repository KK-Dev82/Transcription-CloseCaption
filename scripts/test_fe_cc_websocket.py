#!/usr/bin/env python3
"""
สคริปต์ทดสอบ WebSocket FE CC (Live Caption)
ใช้ตรวจสอบว่า /api/ws/captions ทำงานปกติหรือไม่

Usage:
    # ทดสอบรับ captions (Consumer) — ใช้ meeting_id เดียวกับ FE Producer
    python scripts/test_fe_cc_websocket.py --mode consumer --base-url http://localhost:8010 --meeting-id test-meeting-001

    # ทดสอบทั้ง Consumer + ตรวจสอบ logs
    python scripts/test_fe_cc_websocket.py --mode consumer --base-url http://localhost:8010 --meeting-id test-meeting-001 --verbose
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("❌ ต้องติดตั้ง websockets: pip install websockets")
    sys.exit(1)


async def test_captions_consumer(base_url: str, meeting_id: str, timeout: int = 120, verbose: bool = False):
    """
    เชื่อมต่อ /api/ws/captions ในฐานะ Consumer และรับ events
    ถ้า Producer (FE) ส่งเสียง และ backend ทำ transcription ได้ จะเห็น partial/final
    """
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    endpoint = f"{ws_url}/api/ws/captions?meeting_id={meeting_id}"

    print(f"\n🔌 Connecting to: {endpoint}")
    print(f"   Meeting ID: {meeting_id}")
    print(f"   Timeout: {timeout}s (กด Ctrl+C เพื่อหยุด)\n")
    print("-" * 60)

    try:
        async with websockets.connect(endpoint, close_timeout=2) as ws:
            print("✅ WebSocket connected!\n")

            start = datetime.now()
            msg_count = 0
            partial_count = 0
            final_count = 0

            while (datetime.now() - start).seconds < timeout:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    msg_type = data.get("type", "?")
                    msg_count += 1

                    if msg_type == "partial":
                        partial_count += 1
                        text = data.get("text", "")
                        print(f"📝 [partial] {text[:80]}{'...' if len(text) > 80 else ''}")
                    elif msg_type == "final":
                        final_count += 1
                        text = data.get("text", "")
                        print(f"✅ [final]   {text[:80]}{'...' if len(text) > 80 else ''}")
                    elif msg_type in ("sync", "status"):
                        print(f"📡 [{msg_type}] OK")
                    elif msg_type == "heartbeat":
                        if verbose:
                            print("💓 heartbeat")
                    elif msg_type == "error":
                        print(f"❌ [error] {data}")
                    else:
                        if verbose:
                            print(f"📨 [{msg_type}] {json.dumps(data, ensure_ascii=False)[:120]}")

                except asyncio.TimeoutError:
                    # No message - continue
                    continue

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Connection failed: {e.status_code} - {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    print("-" * 60)
    print(f"\n📊 Summary: messages={msg_count}, partial={partial_count}, final={final_count}")
    if partial_count == 0 and final_count == 0:
        print("\n⚠️  ไม่ได้รับ partial/final — ตรวจสอบว่า:")
        print("   1. Producer (FE) connect ไป /api/ws/ingest-audio แล้ว")
        print("   2. Producer ส่ง PCM frames แล้ว (พูดหรือเปิดไมค์)")
        print("   3. meeting_id ตรงกันทั้ง Producer และ Consumer")
        print("   4. ดู logs: tail -f logs/main-api.log | grep 'WS ingest'")
    else:
        print("\n✅ WebSocket FE CC ทำงานปกติ!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test FE CC WebSocket")
    parser.add_argument("--mode", default="consumer", choices=["consumer"])
    parser.add_argument("--base-url", default="http://localhost:8010", help="API base URL")
    parser.add_argument("--meeting-id", default="test-fe-cc-001", help="Meeting ID (ต้องตรงกับ FE Producer)")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    asyncio.run(
        test_captions_consumer(
            base_url=args.base_url,
            meeting_id=args.meeting_id,
            timeout=args.timeout,
            verbose=args.verbose,
        )
    )


if __name__ == "__main__":
    main()
