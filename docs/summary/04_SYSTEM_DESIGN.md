# System Design: ER Diagram, Class Diagram, Data Dictionary

## ER Diagram

```mermaid
erDiagram
    transcriptions ||--o{ segments : "has"
    transcriptions {
        string task_id PK
        timestamp created_at
        timestamp updated_at
        timestamp completed_at
        string file_path
        string file_url
        string file_name
        string language
        real total_duration
        text full_text
        text chunks_json
        string status
        int progress
        string model_size
        int chunk_duration
        string error_message
        real processing_time
        string callback_url
        int enable_diarization
    }
    
    segments {
        int id PK
        string task_id FK
        int idx
        real start_time
        real end_time
        text text
        real confidence
        timestamp created_at
    }
    
    captions {
        string task_id PK
        timestamp created_at
        string file_path
        string language
        text subtitle_content
        text segments_json
        string status
        string model_size
    }
    
    video_tasks {
        string task_id PK
        timestamp created_at
        string type
        string status
        string input_file
        string output_file
        string error_message
        real progress
    }
    
    live_streams {
        string stream_id PK
        timestamp created_at
        timestamp ended_at
        string status
        string language
        string model_size
        real total_audio_duration
        int transcription_count
    }
    
    uploaded_files {
        int id PK
        string filename
        string file_path UK
        string file_type
        int file_size
        real duration
        timestamp created_at
        timestamp deleted_at
    }
    
    transcriptions ||--o| captions : "may generate"
```

---

## Class Diagram

```mermaid
classDiagram
    class WhisperProvider {
        <<abstract>>
        +transcribe()
    }
    
    class FasterWhisperProvider {
        +transcribe()
    }
    
    class NeMoTyphoonProvider {
        +transcribe()
    }
    
    class WhisperProviderFactory {
        +create_provider()
        +get_provider_type()
    }
    
    WhisperProvider <|-- FasterWhisperProvider
    WhisperProvider <|-- NeMoTyphoonProvider
    WhisperProviderFactory ..> WhisperProvider : creates
    
    class WhisperService {
        -provider: WhisperProvider
        +transcribe_file()
        +get_provider()
    }
    
    WhisperService --> WhisperProvider : uses
    
    class TranscriptionService {
        -redis_queue: RedisQueueService
        +start_transcription()
        +get_task_status()
    }
    
    class RedisQueueService {
        -preprocess_queue
        -gpu_queues
        -priority_queue
        -cpu_queue
        +enqueue_preprocess()
        +enqueue_gpu_job()
        +enqueue_aggregator()
    }
    
    TranscriptionService --> RedisQueueService : uses
    
    class WebSocketManager {
        -connections: dict
        +connect()
        +disconnect()
        +broadcast_to_meeting()
    }
    
    class TyPhoonASRService {
        +transcribe_audio()
        +is_typhoon_available()
    }
    
    class SQLiteStorage {
        -conn
        +save_transcription()
        +get_transcription()
        +save_segment()
    }
    
    TranscriptionService --> SQLiteStorage : uses
    
    class VideoService {
        +extract_audio()
    }
    
    class CloseCaptionConfig {
        <<config>>
        +MODEL_SIZE
        +CHUNK_HOP_SECONDS
        +DEDUPE_ENABLED
    }
    
    class FileService {
        +is_video_file()
        +is_audio_file()
    }
```

---

## Data Dictionary

### transcriptions

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| task_id | TEXT | NO | PK, UUID |
| created_at | TIMESTAMP | YES | เวลาสร้าง |
| updated_at | TIMESTAMP | YES | เวลาอัปเดตล่าสุด |
| completed_at | TIMESTAMP | YES | เวลาเสร็จสิ้น |
| file_path | TEXT | YES | path ไฟล์ในระบบ |
| file_url | TEXT | YES | URL ไฟล์ (ถ้าใช้ URL) |
| file_name | TEXT | YES | ชื่อไฟล์ |
| language | TEXT | YES | ภาษา (th, en, auto) |
| total_duration | REAL | YES | ความยาวเสียง (วินาที) |
| full_text | TEXT | YES | ข้อความเต็ม |
| original_text | TEXT | YES | ข้อความดิบก่อน postprocess |
| corrected_text | TEXT | YES | หลัง Thai processing |
| partial_text | TEXT | YES | ข้อความบางส่วน (streaming) |
| chunks_json | TEXT | YES | JSON ของ chunks |
| status | TEXT | YES | pending, processing, completed, failed |
| progress | INTEGER | YES | 0–100 |
| model_size | TEXT | YES | base, small, medium, large-v3, turbo |
| chunk_duration | INTEGER | YES | วินาทีต่อ chunk |
| error_message | TEXT | YES | ข้อความ error |
| processing_time | REAL | YES | เวลาประมวลผล (วินาที) |
| transcription_time | REAL | YES | เวลา transcription |
| audio_extraction_time | REAL | YES | เวลา extract audio |
| current_stage | TEXT | YES | สถานะขั้นตอนปัจจุบัน |
| current_stage_description | TEXT | YES | คำอธิบาย |
| stage_progress | INTEGER | YES | ความคืบหน้าขั้นตอน |
| job_id | TEXT | YES | RQ job ID |
| callback_url | TEXT | YES | URL สำหรับ callback |
| enable_diarization | INTEGER | YES | 0/1 |

### segments

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | NO | PK, autoincrement |
| task_id | TEXT | NO | FK → transcriptions |
| idx | INTEGER | NO | ลำดับ segment |
| start_time | REAL | NO | เวลาเริ่ม (วินาที) |
| end_time | REAL | NO | เวลาสิ้นสุด (วินาที) |
| text | TEXT | NO | ข้อความ segment |
| confidence | REAL | YES | ความมั่นใจ (0–1) |
| created_at | TIMESTAMP | YES | เวลาสร้าง |

### captions

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| task_id | TEXT | NO | PK |
| created_at | TIMESTAMP | YES | |
| file_path | TEXT | YES | |
| language | TEXT | YES | |
| subtitle_format | TEXT | YES | srt, vtt |
| subtitle_content | TEXT | YES | เนื้อหา subtitle |
| segments_json | TEXT | YES | JSON segments |
| status | TEXT | YES | |
| model_size | TEXT | YES | |
| error_message | TEXT | YES | |

### video_tasks

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| task_id | TEXT | NO | PK |
| created_at | TIMESTAMP | YES | |
| type | TEXT | YES | ประเภท task |
| status | TEXT | YES | pending, processing, completed |
| input_file | TEXT | YES | |
| output_file | TEXT | YES | |
| error_message | TEXT | YES | |
| progress | REAL | YES | 0–1 |

### live_streams

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| stream_id | TEXT | NO | PK |
| created_at | TIMESTAMP | YES | |
| ended_at | TIMESTAMP | YES | |
| status | TEXT | YES | active, ended |
| language | TEXT | YES | |
| model_size | TEXT | YES | |
| total_audio_duration | REAL | YES | |
| transcription_count | INTEGER | YES | |

### uploaded_files

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | NO | PK |
| filename | TEXT | NO | ชื่อไฟล์ |
| file_path | TEXT | NO | path (unique) |
| file_type | TEXT | NO | video, audio |
| file_size | INTEGER | NO | bytes |
| duration | REAL | YES | วินาที |
| created_at | TIMESTAMP | YES | |
| deleted_at | TIMESTAMP | YES | soft delete |
