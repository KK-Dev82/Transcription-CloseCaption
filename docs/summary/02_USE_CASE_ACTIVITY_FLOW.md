# Use Case, Activity และ Process Flow

## Use Case Diagram

```mermaid
flowchart LR
    subgraph Actors["Actors"]
        User["User"]
        Producer["Producer (Browser)"]
        Consumer["Consumer (Viewer)"]
        System["External System"]
    end
    
    subgraph FE_CC["FE Live Caption"]
        UC1["ส่งเสียง Real-time"]
        UC2["รับ Caption"]
    end
    
    subgraph Transcription["Transcription"]
        UC3["เริ่ม Transcription"]
        UC4["ตรวจสอบสถานะ"]
        UC5["รับผลลัพธ์"]
    end
    
    Producer --> UC1
    Consumer --> UC2
    User --> UC3
    User --> UC4
    User --> UC5
    System --> UC3
    System --> UC5
```

---

## Use Case รายละเอียด

### UC-01: ส่งเสียง Real-time (FE CC Producer)

| รายการ | รายละเอียด |
|--------|-------------|
| **Actor** | Producer (Browser/AudioWorklet) |
| **Precondition** | meeting_id ไม่ถูก lock โดย producer อื่น |
| **Flow หลัก** | 1. Connect WebSocket ingest-audio 2. ส่ง JSON init 3. ส่ง PCM16 binary frames ต่อเนื่อง |
| **Postcondition** | ระบบทำ transcription และ broadcast caption ไปยัง consumers |
| **Alternative** | Producer lock conflict → error + close |

### UC-02: รับ Caption (FE CC Consumer)

| รายการ | รายละเอียด |
|--------|-------------|
| **Actor** | Consumer (Viewer/Frontend) |
| **Precondition** | Connect WebSocket captions ด้วย meeting_id |
| **Flow หลัก** | 1. Connect 2. รับ sync, status 3. รับ partial/final events |
| **Postcondition** | แสดง caption แบบ real-time |

### UC-03: เริ่ม Transcription

| รายการ | รายละเอียด |
|--------|-------------|
| **Actor** | User / External System |
| **Precondition** | มี file_path หรือ file_url ที่เข้าถึงได้ |
| **Flow หลัก** | 1. POST /api/transcribe/ 2. ระบบ enqueue preprocess 3. คืน task_id |
| **Postcondition** | Job ใน queue รอ processing |

### UC-04: ตรวจสอบสถานะ Transcription

| รายการ | รายละเอียด |
|--------|-------------|
| **Actor** | User |
| **Precondition** | มี task_id |
| **Flow หลัก** | GET /api/v2/tasks/{task_id}?format=progress |
| **Postcondition** | ได้ progress, current_stage |

### UC-05: รับผลลัพธ์ Transcription

| รายการ | รายละเอียด |
|--------|-------------|
| **Actor** | User / External System (callback_url) |
| **Precondition** | Task completed |
| **Flow หลัก** | GET /api/v2/tasks/{task_id} หรือรับ callback POST |
| **Postcondition** | ได้ full_text, segments |

---

## Activity Diagrams

### Activity: FE CC End-to-End

```mermaid
flowchart TD
    A[Producer Connect] --> B{Producer Lock OK?}
    B -->|No| C[Error + Close]
    B -->|Yes| D[Append PCM to Ring Buffer]
    D --> E[Infer Loop: Step every 1s]
    E --> F{Ring >= min_bytes?}
    F -->|No| E
    F -->|Yes| G[Take Window]
    G --> H[Write Temp WAV]
    H --> I[ASR Transcribe]
    I --> J[Postprocess + Dedupe]
    J --> K{VAD: Silence?}
    K -->|Yes| L[Broadcast final]
    K -->|No| M[Broadcast partial]
    L --> E
    M --> E
```

### Activity: Transcription Job lifecycle

```mermaid
flowchart TD
    A[POST /api/transcribe/] --> B[Enqueue Preprocess]
    B --> C[Preprocess: Extract Audio]
    C --> D[Convert 16k Mono]
    D --> E[Chunk + Overlap]
    E --> F[Enqueue GPU Jobs]
    F --> G[GPU Worker: Transcribe Chunk]
    G --> H{More Chunks?}
    H -->|Yes| G
    H -->|No| I[Enqueue Aggregator]
    I --> J[Aggregate Segments]
    J --> K[Save SQLite]
    K --> L[Callback if set]
    L --> M[Complete]
```

---

## Process Flow

### FE CC: Sequence Flow

```mermaid
sequenceDiagram
    participant P as Producer
    participant WS as ingest-audio
    participant ASR as ASR Engine
    participant Captions as ws/captions
    participant C as Consumer

    P->>WS: Connect + init
    WS->>P: producer_connected
    loop PCM
        P->>WS: Binary frames
    end
    loop Step
        WS->>ASR: transcribe(wav)
        ASR->>WS: text, segments
        WS->>Captions: broadcast event
        Captions->>C: partial/final
    end
```

### Transcription: Sequence Flow

```mermaid
sequenceDiagram
    participant API
    participant Redis
    participant Pre
    participant GPU
    participant Agg
    participant DB

    API->>Redis: preprocess job
    Redis->>Pre: dequeue
    Pre->>Pre: extract, chunk
    Pre->>Redis: N × GPU job
    loop Chunks
        Redis->>GPU: dequeue
        GPU->>GPU: transcribe
        GPU->>Redis: aggregator job
    end
    Redis->>Agg: dequeue
    Agg->>DB: save
    Agg->>API: callback (opt)
```
