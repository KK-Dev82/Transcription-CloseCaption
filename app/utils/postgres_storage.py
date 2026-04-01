"""
PostgreSQL Storage Backend
เขียนตรงไป Postgres transcription schema (เดียวกับ senate-backend)
เป็น Single Source of Truth สำหรับ transcription data

Tables ที่ใช้:
- transcription."TranscriptionJobs" — job metadata, status, progress
- transcription."TranscriptionResults" — full_text, segments (1:1 กับ Jobs)

Delegate ไป SQLite สำหรับ:
- captions, live_streams (ephemeral real-time CC)
- uploaded_files (local file metadata)
- video_tasks
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# ─── Field mapping: Python snake_case ↔ Postgres PascalCase ───

# TranscriptionJobs columns that Python writes
_JOB_FIELD_MAP = {
    "task_id": "TaskId",
    "status": "Status",
    "progress": "Progress",
    "file_name": "FileName",
    "file_path": "FilePath",
    "file_url": "FileUrl",
    "language": "Language",
    "model_size": "ModelSize",
    "error_message": "ErrorMessage",
    "current_stage": "CurrentStage",
    "current_stage_description": "CurrentStageDescription",
    "stage_progress": "StageProgress",
    "processing_time": "ProcessingTime",
    "transcription_time": "TranscriptionTime",
    "audio_extraction_time": "AudioExtractionTime",
    "text_correction_time": "TextCorrectionTime",
    "total_duration": "TotalDuration",
    "enable_diarization": "EnableDiarization",
    "partial_text": "PartialText",
    "original_text": "OriginalText",
    "corrected_text": "CorrectedText",
    "source": "Source",
    "callback_url": "CallbackUrl",
    "created_at": "CreatedAt",
    "updated_at": "UpdatedAt",
    "completed_at": "CompletedAt",
    "started_at": "StartedAt",
}

# Reverse mapping: PascalCase → snake_case
_PG_TO_PYTHON = {v: k for k, v in _JOB_FIELD_MAP.items()}
# Additional Postgres-only columns
_PG_TO_PYTHON.update({
    "Id": "id",
    "UserId": "user_id",
    "UserGuid": "user_guid",
    "FileId": "file_id",
    "TaskId": "task_id",
    "HangfireJobId": "hangfire_job_id",
    "DurationSeconds": "duration_seconds",
    "MeetingId": "meeting_id",
    "ChapterId": "chapter_id",
    "IsRealtime": "is_realtime",
    "ChunkIndex": "chunk_index",
    "ConversionJobId": "conversion_job_id",
    "WavFileId": "wav_file_id",
    "ChunkFileIdsJson": "chunk_file_ids_json",
    "QueuePosition": "queue_position",
    "QueuedAt": "queued_at",
    "DispatchRetryCount": "dispatch_retry_count",
    "CreatedBy": "created_by",
    "UpdatedBy": "updated_by",
    "PhaseTimingsJson": "phase_timings_json",
})

# Fields ที่ map ลง TranscriptionJobs.PhaseTimingsJson (JSON column)
_PHASE_TIMINGS_FIELD = "PhaseTimingsJson"

# Empty GUID สำหรับ Flow B (direct API, no backend job)
_EMPTY_GUID = "00000000-0000-0000-0000-000000000000"


class PostgresStorage:
    """
    Storage backend ที่เขียน transcription data ตรงไป PostgreSQL

    - Transcription jobs/results → Postgres (transcription schema)
    - Captions, live_streams, uploaded_files → delegate ไป local SQLite
    """

    def __init__(self, database_url: str, sqlite_db_path: Optional[str] = None):
        """
        Args:
            database_url: PostgreSQL connection string
                e.g. postgresql://user:pass@host:5432/dbname
            sqlite_db_path: Path สำหรับ local SQLite (captions, live_streams, uploaded_files)
        """
        self.engine: Engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={"options": "-c search_path=transcription,public"},
        )
        logger.info(f"PostgresStorage: connected to {database_url.split('@')[-1] if '@' in database_url else 'postgres'}")

        # Local SQLite สำหรับ ephemeral data (captions, live_streams, uploaded_files)
        self._local_sqlite = None
        if sqlite_db_path:
            try:
                from .sqlite_storage import SQLiteStorage
                self._local_sqlite = SQLiteStorage(sqlite_db_path)
                logger.info(f"PostgresStorage: SQLite delegate at {sqlite_db_path}")
            except Exception as e:
                logger.warning(f"PostgresStorage: Failed to init SQLite delegate: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Transcription CRUD → PostgreSQL
    # ═══════════════════════════════════════════════════════════════════

    def save_transcription(self, task_id: str, transcription_data: Dict) -> str:
        """บันทึก transcription data ลง Postgres TranscriptionJobs (+Results ถ้า completed)"""
        now_utc = datetime.now(timezone.utc)

        # Prepare timestamps
        created_at = self._parse_timestamp(transcription_data.get("created_at")) or now_utc
        updated_at = self._parse_timestamp(transcription_data.get("updated_at")) or now_utc
        completed_at = self._parse_timestamp(transcription_data.get("completed_at"))
        started_at = self._parse_timestamp(transcription_data.get("started_at"))

        status = transcription_data.get("status", "pending")
        progress = transcription_data.get("progress", 0)

        # Phase timings → JSON string
        phase_timings_json = None
        if "phase_timings" in transcription_data:
            try:
                phase_timings_json = json.dumps(transcription_data["phase_timings"], ensure_ascii=False)
            except Exception:
                pass

        with self.engine.connect() as conn:
            # Check if job already exists
            result = conn.execute(
                text('SELECT "Id", "CreatedAt" FROM "TranscriptionJobs" WHERE "TaskId" = :task_id'),
                {"task_id": task_id}
            )
            existing = result.fetchone()

            if existing:
                # ── UPDATE existing job (Flow A: backend created the row) ──
                job_id = existing[0]
                # Preserve original created_at
                created_at = existing[1] or created_at

                conn.execute(
                    text('''
                        UPDATE "TranscriptionJobs" SET
                            "Status" = :status,
                            "Progress" = :progress,
                            "ErrorMessage" = :error_message,
                            "UpdatedAt" = :updated_at,
                            "CompletedAt" = COALESCE(:completed_at, "CompletedAt"),
                            "StartedAt" = COALESCE(:started_at, "StartedAt"),
                            "CurrentStage" = :current_stage,
                            "CurrentStageDescription" = :current_stage_description,
                            "StageProgress" = :stage_progress,
                            "ProcessingTime" = :processing_time,
                            "TranscriptionTime" = :transcription_time,
                            "AudioExtractionTime" = :audio_extraction_time,
                            "TextCorrectionTime" = :text_correction_time,
                            "FilePath" = COALESCE(:file_path, "FilePath"),
                            "FileUrl" = COALESCE(:file_url, "FileUrl"),
                            "TotalDuration" = COALESCE(:total_duration, "TotalDuration"),
                            "EnableDiarization" = :enable_diarization,
                            "PartialText" = :partial_text,
                            "OriginalText" = :original_text,
                            "CorrectedText" = :corrected_text,
                            "CallbackUrl" = COALESCE(:callback_url, "CallbackUrl"),
                            "PhaseTimingsJson" = COALESCE(:phase_timings_json, "PhaseTimingsJson"),
                            "Language" = COALESCE(:language, "Language"),
                            "ModelSize" = COALESCE(:model_size, "ModelSize"),
                            "Source" = COALESCE(:source, "Source")
                        WHERE "Id" = :job_id
                    '''),
                    {
                        "job_id": job_id,
                        "status": status,
                        "progress": progress,
                        "error_message": transcription_data.get("error_message"),
                        "updated_at": updated_at,
                        "completed_at": completed_at,
                        "started_at": started_at,
                        "current_stage": transcription_data.get("current_stage"),
                        "current_stage_description": transcription_data.get("current_stage_description"),
                        "stage_progress": transcription_data.get("stage_progress"),
                        "processing_time": transcription_data.get("processing_time"),
                        "transcription_time": transcription_data.get("transcription_time"),
                        "audio_extraction_time": transcription_data.get("audio_extraction_time"),
                        "text_correction_time": transcription_data.get("text_correction_time"),
                        "file_path": transcription_data.get("file_path"),
                        "file_url": transcription_data.get("file_url"),
                        "total_duration": transcription_data.get("total_duration"),
                        "enable_diarization": bool(transcription_data.get("enable_diarization", False)),
                        "partial_text": transcription_data.get("partial_text"),
                        "original_text": transcription_data.get("original_text"),
                        "corrected_text": transcription_data.get("corrected_text"),
                        "callback_url": transcription_data.get("callback_url"),
                        "phase_timings_json": phase_timings_json,
                        "language": transcription_data.get("language"),
                        "model_size": transcription_data.get("model_size"),
                        "source": transcription_data.get("source"),
                    }
                )
            else:
                # ── INSERT new job (Flow B: direct API, no backend job) ──
                result = conn.execute(
                    text('''
                        INSERT INTO "TranscriptionJobs" (
                            "TaskId", "UserId", "FileId", "FileName", "Status", "Progress",
                            "Language", "ModelSize", "ErrorMessage",
                            "CreatedAt", "UpdatedAt", "CompletedAt", "StartedAt",
                            "CurrentStage", "CurrentStageDescription", "StageProgress",
                            "ProcessingTime", "TranscriptionTime", "AudioExtractionTime", "TextCorrectionTime",
                            "FilePath", "FileUrl", "TotalDuration", "EnableDiarization",
                            "PartialText", "OriginalText", "CorrectedText",
                            "CallbackUrl", "PhaseTimingsJson", "Source",
                            "IsRealtime", "DispatchRetryCount"
                        ) VALUES (
                            :task_id, :user_id, :file_id, :file_name, :status, :progress,
                            :language, :model_size, :error_message,
                            :created_at, :updated_at, :completed_at, :started_at,
                            :current_stage, :current_stage_description, :stage_progress,
                            :processing_time, :transcription_time, :audio_extraction_time, :text_correction_time,
                            :file_path, :file_url, :total_duration, :enable_diarization,
                            :partial_text, :original_text, :corrected_text,
                            :callback_url, :phase_timings_json, :source,
                            false, 0
                        )
                        RETURNING "Id"
                    '''),
                    {
                        "task_id": task_id,
                        "user_id": int(transcription_data.get("user_id", 0) or 0),
                        "file_id": _EMPTY_GUID,
                        "file_name": transcription_data.get("file_name", "unknown"),
                        "status": status,
                        "progress": progress,
                        "language": transcription_data.get("language", "th"),
                        "model_size": transcription_data.get("model_size", "base"),
                        "error_message": transcription_data.get("error_message"),
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "completed_at": completed_at,
                        "started_at": started_at,
                        "current_stage": transcription_data.get("current_stage"),
                        "current_stage_description": transcription_data.get("current_stage_description"),
                        "stage_progress": transcription_data.get("stage_progress"),
                        "processing_time": transcription_data.get("processing_time"),
                        "transcription_time": transcription_data.get("transcription_time"),
                        "audio_extraction_time": transcription_data.get("audio_extraction_time"),
                        "text_correction_time": transcription_data.get("text_correction_time"),
                        "file_path": transcription_data.get("file_path"),
                        "file_url": transcription_data.get("file_url"),
                        "total_duration": transcription_data.get("total_duration"),
                        "enable_diarization": bool(transcription_data.get("enable_diarization", False)),
                        "partial_text": transcription_data.get("partial_text"),
                        "original_text": transcription_data.get("original_text"),
                        "corrected_text": transcription_data.get("corrected_text"),
                        "callback_url": transcription_data.get("callback_url"),
                        "phase_timings_json": phase_timings_json,
                        "source": transcription_data.get("source"),
                    }
                )
                row = result.fetchone()
                job_id = row[0] if row else None

            # ── Save TranscriptionResults (when completed with full_text) ──
            full_text = transcription_data.get("full_text", "")
            chunks = transcription_data.get("chunks") or transcription_data.get("segments") or []

            if status == "completed" and job_id and full_text:
                segments_json = json.dumps(chunks, ensure_ascii=False) if chunks else "[]"
                word_count = len(full_text.split()) if full_text else 0

                # Compute average confidence from chunks
                avg_confidence = None
                confidences = [c.get("confidence") for c in chunks if isinstance(c, dict) and c.get("confidence") is not None]
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences)

                # UPSERT TranscriptionResults — ใช้ check exists ก่อนเพื่อหลีกเลี่ยง constraint errors
                try:
                    existing_result = conn.execute(
                        text('SELECT "Id" FROM "TranscriptionResults" WHERE "TranscriptionJobId" = :job_id'),
                        {"job_id": job_id}
                    ).fetchone()

                    if existing_result:
                        conn.execute(
                            text('''
                                UPDATE "TranscriptionResults" SET
                                    "FullText" = :full_text,
                                    "SegmentsJson" = :segments_json::jsonb,
                                    "AudioDurationSeconds" = :audio_duration,
                                    "WordCount" = :word_count,
                                    "AverageConfidence" = :avg_confidence
                                WHERE "TranscriptionJobId" = :job_id
                            '''),
                            {
                                "job_id": job_id,
                                "full_text": full_text,
                                "segments_json": segments_json,
                                "audio_duration": transcription_data.get("total_duration"),
                                "word_count": word_count,
                                "avg_confidence": avg_confidence,
                            }
                        )
                    else:
                        conn.execute(
                            text('''
                                INSERT INTO "TranscriptionResults" (
                                    "TranscriptionJobId", "FullText", "SegmentsJson",
                                    "AudioDurationSeconds", "WordCount", "AverageConfidence",
                                    "CreatedAt"
                                ) VALUES (
                                    :job_id, :full_text, :segments_json::jsonb,
                                    :audio_duration, :word_count, :avg_confidence,
                                    :created_at
                                )
                            '''),
                            {
                                "job_id": job_id,
                                "full_text": full_text,
                                "segments_json": segments_json,
                                "audio_duration": transcription_data.get("total_duration"),
                                "word_count": word_count,
                                "avg_confidence": avg_confidence,
                                "created_at": now_utc,
                            }
                        )
                except Exception as result_err:
                    logger.warning(f"PostgresStorage: Failed to save TranscriptionResult for job {job_id}: {result_err}")

            conn.commit()

        logger.info(f"PostgresStorage: saved task {task_id} (status={status}, progress={progress})")

        # WebSocket notification (background thread, non-blocking)
        self._notify_websocket(task_id, transcription_data, created_at, updated_at, completed_at)

        return task_id

    def load_transcription(self, task_id: str, skip_migration: bool = False) -> Optional[Dict]:
        """โหลด transcription จาก Postgres (JOIN กับ TranscriptionResults)"""
        with self.engine.connect() as conn:
            result = conn.execute(
                text('''
                    SELECT j.*, r."FullText", r."SegmentsJson",
                           r."AudioDurationSeconds" AS "ResultAudioDuration",
                           r."WordCount" AS "ResultWordCount",
                           r."AverageConfidence" AS "ResultAvgConfidence"
                    FROM "TranscriptionJobs" j
                    LEFT JOIN "TranscriptionResults" r ON r."TranscriptionJobId" = j."Id"
                    WHERE j."TaskId" = :task_id
                '''),
                {"task_id": task_id}
            )
            row = result.mappings().fetchone()

        if not row:
            return None

        return self._row_to_dict(row)

    def list_all_transcriptions(self) -> List[Dict]:
        """ดึงรายการ transcription ทั้งหมด (เรียงจากใหม่ไปเก่า, limit 1000)"""
        max_tasks = int(os.getenv("POSTGRES_MAX_TASKS_PER_QUERY", "1000"))

        with self.engine.connect() as conn:
            result = conn.execute(
                text('''
                    SELECT j.*, r."FullText", r."SegmentsJson",
                           r."AudioDurationSeconds" AS "ResultAudioDuration",
                           r."WordCount" AS "ResultWordCount",
                           r."AverageConfidence" AS "ResultAvgConfidence"
                    FROM "TranscriptionJobs" j
                    LEFT JOIN "TranscriptionResults" r ON r."TranscriptionJobId" = j."Id"
                    ORDER BY COALESCE(j."UpdatedAt", j."CreatedAt") DESC
                    LIMIT :limit
                '''),
                {"limit": max_tasks}
            )
            rows = result.mappings().fetchall()

        return [self._row_to_dict(row) for row in rows]

    def delete_transcription(self, task_id: str) -> bool:
        """ลบ transcription (cascade จะลบ TranscriptionResults ด้วย)"""
        with self.engine.connect() as conn:
            result = conn.execute(
                text('DELETE FROM "TranscriptionJobs" WHERE "TaskId" = :task_id'),
                {"task_id": task_id}
            )
            conn.commit()
            deleted = result.rowcount > 0

        if deleted:
            logger.info(f"PostgresStorage: deleted task {task_id}")
        return deleted

    def search_transcription(self, task_id: str, query: str, case_sensitive: bool = False) -> List[Dict]:
        """ค้นหาข้อความใน chunks ของ task"""
        data = self.load_transcription(task_id)
        if not data:
            return []

        results = []
        chunks = data.get("chunks", [])
        search_query = query if case_sensitive else query.lower()

        for chunk in chunks:
            chunk_text = chunk.get("text", "")
            compare_text = chunk_text if case_sensitive else chunk_text.lower()
            if search_query in compare_text:
                results.append({
                    "task_id": task_id,
                    "chunk": chunk,
                    "highlighted_text": chunk_text,
                })
        return results

    def search_all_transcriptions(self, query: str, case_sensitive: bool = False) -> List[Dict]:
        """ค้นหาข้อความข้าม transcription ทั้งหมด"""
        # ค้นหาใน FullText ก่อนเพื่อลด scope
        search_pattern = f"%{query}%"
        with self.engine.connect() as conn:
            if case_sensitive:
                result = conn.execute(
                    text('''
                        SELECT j."TaskId"
                        FROM "TranscriptionJobs" j
                        JOIN "TranscriptionResults" r ON r."TranscriptionJobId" = j."Id"
                        WHERE r."FullText" LIKE :pattern
                        LIMIT 50
                    '''),
                    {"pattern": search_pattern}
                )
            else:
                result = conn.execute(
                    text('''
                        SELECT j."TaskId"
                        FROM "TranscriptionJobs" j
                        JOIN "TranscriptionResults" r ON r."TranscriptionJobId" = j."Id"
                        WHERE r."FullText" ILIKE :pattern
                        LIMIT 50
                    '''),
                    {"pattern": search_pattern}
                )
            task_ids = [row[0] for row in result.fetchall()]

        all_results = []
        for tid in task_ids:
            all_results.extend(self.search_transcription(tid, query, case_sensitive))
        return all_results

    def get_transcription_stats(self, task_id: str) -> Dict:
        """ดึง stats ของ transcription"""
        data = self.load_transcription(task_id)
        if not data:
            return {}

        chunks = data.get("chunks", [])
        full_text = data.get("full_text", "")

        total_words = len(full_text.split()) if full_text else 0
        total_chars = len(full_text) if full_text else 0
        total_duration = data.get("total_duration", 0) or 0

        confidences = []
        for chunk in chunks:
            if isinstance(chunk, dict) and chunk.get("confidence") is not None:
                confidences.append(chunk["confidence"])

        return {
            "task_id": task_id,
            "total_chunks": len(chunks),
            "total_words": total_words,
            "total_characters": total_chars,
            "total_duration": total_duration,
            "language": data.get("language"),
            "average_confidence": sum(confidences) / len(confidences) if confidences else None,
        }

    # ═══════════════════════════════════════════════════════════════════
    # Caption / LiveStream / UploadedFiles → delegate to SQLite
    # ═══════════════════════════════════════════════════════════════════

    def save_caption(self, task_id: str, caption_data: Dict) -> str:
        return self._sqlite.save_caption(task_id, caption_data)

    def load_caption(self, task_id: str) -> Optional[Dict]:
        return self._sqlite.load_caption(task_id)

    def save_video_task(self, task_id: str, video_data: Dict) -> str:
        return self._sqlite.save_video_task(task_id, video_data)

    def load_video_task(self, task_id: str) -> Optional[Dict]:
        return self._sqlite.load_video_task(task_id)

    def list_all_video_tasks(self) -> List[Dict]:
        return self._sqlite.list_all_video_tasks()

    def delete_video_task(self, task_id: str) -> bool:
        return self._sqlite.delete_video_task(task_id)

    def save_live_stream(self, stream_id: str, stream_data: Dict) -> str:
        return self._sqlite.save_live_stream(stream_id, stream_data)

    def load_live_stream(self, stream_id: str) -> Optional[Dict]:
        return self._sqlite.load_live_stream(stream_id)

    def save_uploaded_file(self, filename: str, file_path: str, file_type: str, file_size: int,
                           duration: float = None, video_info: Dict = None, audio_info: Dict = None,
                           user_id: str = None, tags: str = None, description: str = None) -> int:
        return self._sqlite.save_uploaded_file(
            filename, file_path, file_type, file_size,
            duration, video_info, audio_info, user_id, tags, description
        )

    def get_uploaded_file(self, file_id: int) -> Optional[Dict]:
        return self._sqlite.get_uploaded_file(file_id)

    def get_uploaded_file_by_path(self, file_path: str) -> Optional[Dict]:
        return self._sqlite.get_uploaded_file_by_path(file_path)

    def list_uploaded_files(self, file_type: Optional[str] = None, include_deleted: bool = False) -> List[Dict]:
        return self._sqlite.list_uploaded_files(file_type, include_deleted)

    def delete_uploaded_file(self, file_id: int, soft_delete: bool = True) -> bool:
        return self._sqlite.delete_uploaded_file(file_id, soft_delete)

    def cleanup_old_files(self, max_age_hours: int = 24):
        if self._local_sqlite and hasattr(self._local_sqlite, 'cleanup_old_files'):
            return self._local_sqlite.cleanup_old_files(max_age_hours)

    def cleanup_deleted_files(self, *args, **kwargs):
        if self._local_sqlite and hasattr(self._local_sqlite, 'cleanup_deleted_files'):
            return self._local_sqlite.cleanup_deleted_files(*args, **kwargs)

    def get_database_stats(self) -> Dict:
        """ดึง stats ของ database"""
        stats = {"storage_type": "postgres"}
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text('SELECT COUNT(*) FROM "TranscriptionJobs"'))
                stats["total_jobs"] = result.scalar()

                result = conn.execute(text('SELECT COUNT(*) FROM "TranscriptionResults"'))
                stats["total_results"] = result.scalar()

                result = conn.execute(
                    text('SELECT "Status", COUNT(*) FROM "TranscriptionJobs" GROUP BY "Status"')
                )
                stats["status_counts"] = {row[0]: row[1] for row in result.fetchall()}
        except Exception as e:
            stats["error"] = str(e)
        return stats

    def close(self):
        """ปิด connection pool"""
        self.engine.dispose()
        if self._local_sqlite and hasattr(self._local_sqlite, 'close'):
            self._local_sqlite.close()
        logger.info("PostgresStorage: closed")

    # ═══════════════════════════════════════════════════════════════════
    # Internal helpers
    # ═══════════════════════════════════════════════════════════════════

    @property
    def _sqlite(self):
        """Get SQLite delegate (raise if not configured)"""
        if not self._local_sqlite:
            raise RuntimeError("PostgresStorage: SQLite delegate not configured (needed for captions/live_streams)")
        return self._local_sqlite

    def _row_to_dict(self, row) -> Dict:
        """Convert a Postgres row (RowMapping) to Python dict compatible with SQLiteStorage format"""
        # Parse chunks from SegmentsJson
        chunks = []
        segments_json = row.get("SegmentsJson")
        if segments_json:
            try:
                if isinstance(segments_json, str):
                    chunks = json.loads(segments_json)
                elif isinstance(segments_json, list):
                    chunks = segments_json
                else:
                    chunks = list(segments_json)
            except Exception:
                chunks = []

        # Parse phase_timings from PhaseTimingsJson
        phase_timings = None
        pt_json = row.get("PhaseTimingsJson")
        if pt_json:
            try:
                if isinstance(pt_json, str):
                    phase_timings = json.loads(pt_json)
                elif isinstance(pt_json, dict):
                    phase_timings = pt_json
            except Exception:
                pass

        result = {
            "task_id": row.get("TaskId"),
            "status": row.get("Status", "pending"),
            "progress": row.get("Progress", 0),
            "file_name": row.get("FileName"),
            "file_path": row.get("FilePath"),
            "file_url": row.get("FileUrl"),
            "language": row.get("Language"),
            "model_size": row.get("ModelSize"),
            "error_message": row.get("ErrorMessage"),
            "created_at": self._format_timestamp(row.get("CreatedAt")),
            "updated_at": self._format_timestamp(row.get("UpdatedAt")),
            "completed_at": self._format_timestamp(row.get("CompletedAt")),
            "started_at": self._format_timestamp(row.get("StartedAt")),
            "current_stage": row.get("CurrentStage"),
            "current_stage_description": row.get("CurrentStageDescription"),
            "stage_progress": row.get("StageProgress"),
            "processing_time": row.get("ProcessingTime"),
            "transcription_time": row.get("TranscriptionTime"),
            "audio_extraction_time": row.get("AudioExtractionTime"),
            "text_correction_time": row.get("TextCorrectionTime"),
            "total_duration": row.get("TotalDuration"),
            "enable_diarization": bool(row.get("EnableDiarization", False)),
            "partial_text": row.get("PartialText"),
            "original_text": row.get("OriginalText"),
            "corrected_text": row.get("CorrectedText"),
            "callback_url": row.get("CallbackUrl"),
            "source": row.get("Source"),
            "full_text": row.get("FullText", ""),
            "chunks": chunks,
            # Additional fields from Postgres
            "id": row.get("Id"),
            "user_id": str(row.get("UserId", 0)),
            "job_id": row.get("HangfireJobId"),
            "meeting_id": str(row["MeetingId"]) if row.get("MeetingId") else None,
            "chapter_id": str(row["ChapterId"]) if row.get("ChapterId") else None,
            "duration_seconds": row.get("DurationSeconds"),
            "queue_position": row.get("QueuePosition"),
        }

        if phase_timings:
            result["phase_timings"] = phase_timings

        return result

    @staticmethod
    def _parse_timestamp(value) -> Optional[datetime]:
        """Parse various timestamp formats to datetime (UTC)"""
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str):
            try:
                if "Z" in value:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                return None
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except Exception:
                return None
        return None

    @staticmethod
    def _format_timestamp(value) -> Optional[str]:
        """Format datetime to ISO string"""
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return str(value)

    def _notify_websocket(self, task_id: str, data: Dict,
                          created_at, updated_at, completed_at):
        """Send WebSocket notification (background thread, non-blocking)"""
        try:
            task_data = {
                "task_id": task_id,
                "status": data.get("status", "pending"),
                "progress": data.get("progress", 0),
                "file_name": data.get("file_name"),
                "file_path": data.get("file_path"),
                "created_at": self._format_timestamp(created_at),
                "updated_at": self._format_timestamp(updated_at),
                "completed_at": self._format_timestamp(completed_at),
                "language": data.get("language"),
                "total_duration": data.get("total_duration"),
                "current_stage": data.get("current_stage"),
                "current_stage_description": data.get("current_stage_description"),
                "full_text": data.get("full_text", ""),
                "text": data.get("text", ""),
                "chunks": data.get("chunks", []),
                "segments": data.get("segments", []),
                "error_message": data.get("error_message", ""),
                "error": data.get("error", ""),
                "processing_time": data.get("processing_time", 0),
            }

            thread = threading.Thread(
                target=self._notify_websocket_sync,
                args=(task_id, task_data),
                daemon=True,
            )
            thread.start()
        except Exception as e:
            logger.debug(f"Failed to send WebSocket notification for {task_id}: {e}")

    @staticmethod
    def _notify_websocket_sync(task_id: str, task_data: Dict):
        """Synchronous WebSocket notification (runs in background thread)"""
        try:
            import asyncio
            from app.services.websocket_manager import get_websocket_manager

            manager = get_websocket_manager()
            if manager is None:
                return

            status = task_data.get("status", "")
            loop = asyncio.new_event_loop()
            try:
                if status == "completed":
                    loop.run_until_complete(
                        manager.notify_transcription_completed(task_id, task_data)
                    )
                elif status == "failed":
                    loop.run_until_complete(
                        manager.notify_transcription_failed(
                            task_id, task_data.get("error_message", "Unknown error")
                        )
                    )
                else:
                    loop.run_until_complete(
                        manager.notify_transcription_progress(
                            task_id,
                            task_data.get("progress", 0),
                            task_data.get("status", "processing"),
                            task_data,
                        )
                    )
            finally:
                loop.close()
        except Exception as e:
            logger.debug(f"WebSocket notify error for {task_id}: {e}")
