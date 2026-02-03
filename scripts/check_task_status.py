#!/usr/bin/env python3
"""
ตรวจสอบสถานะ task การถอดข้อความ (Transcription / FE-CC)
- ดูจาก storage ว่ามี task หรือไม่ สถานะอะไร
- ดูจาก RQ ว่าติดคิวไหน (preprocess / GPU / aggregator) หรือกำลังทำอยู่
Usage:
  python scripts/check_task_status.py 8c8326ca-6322-44f2-b1fd-99ee22eb596b
"""

import os
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    for env_file in [project_root / ".env.runpod", project_root / ".env"]:
        if env_file.exists():
            load_dotenv(env_file)
            break
except ImportError:
    pass

# RQ ใช้ queue names แบบ RedisQueueService
RQ_QUEUE_NAMES = [
    "transcription_preprocess",
    "transcription_priority",
    "transcription_cpu",
] + [f"transcription_gpu{i}" for i in range(int(os.getenv("NUM_GPUS", "4")))]


def load_task_from_storage(task_id: str):
    """โหลด task จาก storage (SQLite หรือ JSON)"""
    storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
    if storage_type == "sqlite":
        from app.utils.sqlite_storage import SQLiteStorage
        storage = SQLiteStorage()
    else:
        from app.utils.json_storage import JSONStorage
        storage = JSONStorage()
    return storage.load_transcription(task_id)


def find_jobs_for_task(redis_conn, task_id: str):
    """หา RQ jobs ที่เกี่ยวกับ task_id (จาก job_id หรือ args[0])"""
    from rq import Queue
    from rq.job import Job

    found = []
    for queue_name in RQ_QUEUE_NAMES:
        try:
            queue = Queue(queue_name, connection=redis_conn)
            for jid in queue.job_ids:
                try:
                    job = Job.fetch(jid, connection=redis_conn)
                    if not job:
                        continue
                    # job_id อาจเป็น task_id, task_id_preprocess, task_id_aggregator
                    if task_id in (jid if isinstance(jid, str) else jid.decode()):
                        found.append({
                            "queue": queue_name,
                            "job_id": jid.decode() if isinstance(jid, bytes) else jid,
                            "status": job.get_status(),
                            "args0": job.args[0] if job.args else None,
                        })
                        continue
                    if job.args and len(job.args) > 0:
                        first_arg = job.args[0]
                        if isinstance(first_arg, bytes):
                            first_arg = first_arg.decode("utf-8", errors="replace")
                        if first_arg == task_id:
                            found.append({
                                "queue": queue_name,
                                "job_id": jid.decode() if isinstance(jid, bytes) else jid,
                                "status": job.get_status(),
                                "args0": first_arg,
                            })
                except Exception as e:
                    pass
        except Exception as e:
            pass

    # ตรวจสอบ StartedJobRegistry ด้วย (job ที่กำลังรัน)
    from rq.registry import StartedJobRegistry
    for queue_name in RQ_QUEUE_NAMES:
        try:
            queue = Queue(queue_name, connection=redis_conn)
            registry = StartedJobRegistry(queue=queue, connection=redis_conn)
            for jid in registry.get_job_ids():
                jid_str = jid.decode() if isinstance(jid, bytes) else jid
                if task_id in jid_str:
                    if not any(f["job_id"] == jid_str for f in found):
                        try:
                            job = Job.fetch(jid, connection=redis_conn)
                            found.append({
                                "queue": queue_name,
                                "job_id": jid_str,
                                "status": job.get_status(),
                                "args0": job.args[0] if job.args else None,
                            })
                        except Exception:
                            found.append({
                                "queue": queue_name,
                                "job_id": jid_str,
                                "status": "started",
                                "args0": None,
                            })
                else:
                    try:
                        job = Job.fetch(jid, connection=redis_conn)
                        if job.args and len(job.args) > 0:
                            first_arg = job.args[0]
                            if isinstance(first_arg, bytes):
                                first_arg = first_arg.decode("utf-8", errors="replace")
                            if first_arg == task_id and not any(f["job_id"] == jid_str for f in found):
                                found.append({
                                    "queue": queue_name,
                                    "job_id": jid_str,
                                    "status": job.get_status(),
                                    "args0": first_arg,
                                })
                    except Exception:
                        pass
        except Exception:
            pass

    return found


def main():
    task_id = (sys.argv[1] or "").strip() if len(sys.argv) > 1 else "8c8326ca-6322-44f2-b1fd-99ee22eb596b"
    if not task_id:
        print("Usage: python scripts/check_task_status.py <task_id>")
        sys.exit(1)

    print(f"🔍 ตรวจสอบ Task: {task_id}\n")

    # 1. Storage
    task_data = load_task_from_storage(task_id)
    if not task_data:
        print("❌ ไม่พบ task ใน storage")
        print("   อาจยังไม่มีการส่งงานเข้ามา หรือ task_id ผิด")
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            from redis import Redis
            try:
                conn = Redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=5)
                jobs = find_jobs_for_task(conn, task_id)
                if jobs:
                    print(f"\n⚠️ แต่พบ {len(jobs)} job ใน RQ ที่เกี่ยวกับ task นี้:")
                    for j in jobs:
                        print(f"   - {j['queue']}: {j['job_id']} ({j['status']})")
                conn.close()
            except Exception as e:
                print(f"   (ไม่สามารถตรวจ RQ: {e})")
        sys.exit(2)

    status = task_data.get("status", "unknown")
    progress = task_data.get("progress", 0)
    stage = task_data.get("current_stage") or task_data.get("current_stage_description") or "N/A"
    file_path = task_data.get("file_path") or task_data.get("file_url") or "N/A"
    created = task_data.get("created_at", "N/A")
    updated = task_data.get("updated_at", "N/A")

    print("📦 Storage:")
    print(f"   status: {status}")
    print(f"   progress: {progress}%")
    print(f"   stage: {stage}")
    print(f"   file: {file_path}")
    print(f"   created_at: {created}")
    print(f"   updated_at: {updated}")
    if task_data.get("error_message"):
        print(f"   error_message: {task_data.get('error_message')}")

    # 2. RQ
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("\n⚠️ REDIS_URL ไม่ได้ตั้งค่า - ข้ามการตรวจ RQ")
        _summary(status, progress, [])
        return

    try:
        from redis import Redis
        conn = Redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=10)
        jobs = find_jobs_for_task(conn, task_id)
        conn.close()
    except Exception as e:
        print(f"\n❌ ไม่สามารถเชื่อมต่อ Redis: {e}")
        _summary(status, progress, [])
        return

    if jobs:
        print(f"\n📋 RQ Jobs ที่เกี่ยวกับ task นี้ ({len(jobs)}):")
        for j in jobs:
            print(f"   - {j['queue']}: {j['job_id']} → status={j['status']}")

    # 3. Redis chunk counters (เมื่อ status=processing เพื่อดูว่าค้างที่ขั้นตอน transcribing กี่ส่วน)
    try:
        from redis import Redis
        conn = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
        total_key = f"task:{task_id}:total_chunks"
        done_key = f"task:{task_id}:done_chunks"
        total_chunks = conn.get(total_key)
        done_chunks = conn.get(done_key)
        conn.close()
        if total_chunks is not None and status == "processing":
            total_chunks = int(total_chunks)
            done_chunks = int(done_chunks) if done_chunks else 0
            # progress 40-90% = 40 + (done/total)*50
            expected_pct = 40 + int((done_chunks / total_chunks) * 50) if total_chunks else 0
            print(f"\n📊 Chunks (Transcribing): {done_chunks}/{total_chunks} ส่วนเสร็จ (progress คาด ~{expected_pct}%)")
            if total_chunks > 0 and done_chunks < total_chunks:
                print(f"   💡 ค้างที่ ~{progress}% = กำลังรอ chunk transcription เสร็จ (ไม่ใช่ค้างที่อัปโหลด)")
    except Exception as e:
        pass  # Redis optional for chunk counters

    if not jobs:
        print("\n📋 RQ: ไม่พบ job ที่เกี่ยวข้องกับ task นี้ในคิว (อาจเสร็จแล้ว หรือยังไม่ถูก enqueue)")

    _summary(status, progress, jobs)


def _summary(status: str, progress: int, jobs: list):
    print("\n" + "=" * 50)
    if status == "completed":
        print("✅ สรุป: Task ถอดข้อความเสร็จแล้ว")
    elif status == "failed":
        print("❌ สรุป: Task ล้มเหลว (ดู error_message ใน storage)")
    elif jobs:
        queued = [j for j in jobs if j["status"] == "queued"]
        started = [j for j in jobs if j["status"] == "started"]
        if started:
            print("🔄 สรุป: กำลังมีการประมวลผลอยู่ (มี job อยู่ในสถานะ started)")
        elif queued:
            qnames = ", ".join(set(j["queue"] for j in queued))
            print(f"⏳ สรุป: ติดคิวรอทำ — อยู่ในคิว: {qnames}")
        else:
            print("📋 สรุป: มี job ที่เกี่ยวข้อง (ตรวจสอบ status ด้านบน)")
    else:
        if status in ("processing", "queued", "pending"):
            print("⏳ สรุป: Task อยู่ในสถานะ " + status + " แต่ไม่พบ job ใน RQ — อาจติดคิว FE-CC / preprocess หรือ worker ยังไม่รับงาน")
        else:
            print("📋 สรุป: ดูสถานะจาก storage ด้านบน")


if __name__ == "__main__":
    main()
