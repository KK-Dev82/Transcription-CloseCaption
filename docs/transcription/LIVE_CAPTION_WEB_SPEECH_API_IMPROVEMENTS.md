# 🎯 Live Caption / Web Speech API-like Improvements

**วันที่:** 2026-01-26  
**สถานะ:** ⚠️ **Discarded** (ถูก revert ออกไปแล้ว)  
**เป้าหมาย:** ทำให้ Live Caption ผ่าน `ws_ingest` มี "ฟีล Web Speech API" (interim/final, แก้คำท้ายได้) + แก้ปัญหา "อ่านไม่ออก/ค้าง/หลุด WS" + ลด RAM peak

---

## 📋 สรุปการเปลี่ยนแปลงทั้งหมด

### 1️⃣ WebSocket Ingest Improvements (`app/api/websocket.py`)

#### 1.1 Word-by-Word Partial Updates (Web Speech API-like)
**เป้าหมาย:** ให้ `partial` event "ขึ้นทีละคำ" แทนที่จะเป็นประโยคยาวทันที

**การเปลี่ยนแปลง:**
- เพิ่ม `_WORDWISE_ENABLED`, `_WORDS_PER_UPDATE` (env configurable)
- เพิ่ม `_tokenize_caption()` สำหรับ tokenize ภาษาไทย (PyThaiNLP) หรือ whitespace split
- แก้ logic `partial` ให้แสดงเฉพาะ "N คำแรก" ตาม `_WORDS_PER_UPDATE` (default: 1)
- เพิ่ม `delta_tokens` ใน partial event (optional, FE อาจใช้ทำ animation)

**Code Pattern:**
```python
# Tokenize แล้วค่อย ๆ เพิ่มคำ
tokens = _tokenize_caption(pending_text, language)
sent_count = _last_sent_token_count_by_meeting.get(meeting_id, 0)
target_count = min(len(tokens), sent_count + _WORDS_PER_UPDATE)
display_text = " ".join(tokens[:target_count])
```

**Env Variables:**
```bash
FE_CC_WORDWISE_ENABLED=true
FE_CC_WORDS_PER_UPDATE=1
FE_CC_FORCE_FINAL_MAX_TOKENS=45
FE_CC_FORCE_FINAL_MAX_SECONDS=8.0
```

---

#### 1.2 Partial Gating (ลด spam events)
**เป้าหมาย:** กัน `partial` สั่น/รัวเกินไป

**การเปลี่ยนแปลง:**
- เพิ่ม `_PARTIAL_MIN_CHARS_THRESHOLD`, `_PARTIAL_MIN_TIME_THRESHOLD`
- ส่ง `partial` เฉพาะเมื่อ:
  - ข้อความเพิ่มขึ้น ≥ `_PARTIAL_MIN_CHARS` **หรือ**
  - เวลาผ่านไป ≥ `_PARTIAL_MIN_TIME` (ตั้งแต่ partial ล่าสุด)

**Env Variables:**
```bash
FE_CC_PARTIAL_ENABLED=true
FE_CC_PARTIAL_MIN_CHARS=6
FE_CC_PARTIAL_MIN_TIME=0.7
```

---

#### 1.3 Force-Final Guard (กัน pending ยาวเกิน)
**เป้าหมาย:** ถ้าผู้พูดไม่ pause เลย → force final เมื่อ pending ยาวเกิน

**การเปลี่ยนแปลง:**
- เพิ่ม `_FORCE_FINAL_MAX_TOKENS`, `_FORCE_FINAL_MAX_SECONDS`
- ถ้า pending text ยาวเกิน threshold → ส่ง `final` แบบ forced (มี `meta.forced_final=true`)

**Env Variables:**
```bash
FE_CC_FORCE_FINAL_MAX_TOKENS=45
FE_CC_FORCE_FINAL_MAX_SECONDS=8.0
```

---

#### 1.4 Audio Format Support (แก้ "เพี้ยนหนัก")
**เป้าหมาย:** รองรับ `float32` จาก browser (AudioWorklet) แทนที่จะอ่านเป็น PCM16 ผิด

**การเปลี่ยนแปลง:**
- เพิ่ม `_pcm_bytes_from_ws_frame()` สำหรับ convert:
  - `s16le` → ใช้ตรง ๆ
  - `f32le/float32` → แปลงเป็น PCM16LE ก่อนเขียน WAV
- เพิ่ม **auto-detect** กรณี FE ส่ง float32 แต่บอกว่า s16le (best-effort, ตรวจจาก byte pattern)

**Code Pattern:**
```python
def _pcm_bytes_from_ws_frame(b: bytes, audio_format: str) -> Optional[bytes]:
    if fmt in ("f32le", "float32"):
        # Convert float32 [-1, 1] → int16
        f = np.frombuffer(b, dtype="<f4")
        i16 = (np.clip(f, -1.0, 1.0) * 32767.0).astype("<i2")
        return i16.tobytes()
```

---

#### 1.5 Sample Rate Mismatch Detection (Debug)
**เป้าหมาย:** ตรวจสอบว่า FE ส่ง sample_rate ตรงกับข้อมูลจริงหรือไม่

**การเปลี่ยนแปลง:**
- เพิ่ม throughput estimation จาก byte/sec → estimate sample_rate
- ถ้า mismatch ≥ 20% → log warning + override (optional, ปิด default)
- เพิ่ม `meta` ใน event (`sample_rate`, `audio_format`, `avg_amplitude`)

**Env Variables:**
```bash
FE_CC_AUTO_SAMPLE_RATE_ENABLED=false  # ปิด default (อาจ misfire ตอน burst/drop)
```

---

#### 1.6 Non-Blocking Transcription (แก้ 1011 ping timeout)
**เป้าหมาย:** กัน event loop ถูกบล็อกจนตอบ keepalive ไม่ทัน

**การเปลี่ยนแปลง:**
- ย้าย `whisper_service.transcribe_file()` → `asyncio.to_thread()`
- ย้าย `postprocess_thai_text()` → `asyncio.to_thread()` (PyThaiNLP หนัก)
- ย้าย `dedupe_text()` → `asyncio.to_thread()`
- ย้าย `_tokenize_caption()` (Thai) → `asyncio.to_thread()`

**Code Pattern:**
```python
# Before (blocking)
result = whisper_service.transcribe_file(...)

# After (non-blocking)
result = await asyncio.to_thread(
    whisper_service.transcribe_file,
    audio_path=tmp_path,
    model_size=model_size,
    language=language,
    use_thai_processor=(language == "th"),
)
```

---

#### 1.7 Server → Client Keepalive (แก้ 1006 abnormal close)
**เป้าหมาย:** บาง proxy ตัด WS ถ้า server เงียบฝั่งตอบกลับ

**การเปลี่ยนแปลง:**
- เพิ่ม `uplink_keepalive_loop()` ส่ง status packet เป็นระยะ (default: ทุก 15s)
- เพิ่ม `_UPLINK_KEEPALIVE_SECONDS` (env configurable)

**Env Variables:**
```bash
FE_CC_UPLINK_KEEPALIVE_SECONDS=15
```

---

### 2️⃣ Thai Postprocessing Improvements (`app/utils/thai_postprocess.py`)

#### 2.1 Repair Spaced Thai Characters
**เป้าหมาย:** แก้ "ข อ บ คุ ณ" → "ขอบคุณ"

**การเปลี่ยนแปลง:**
- เพิ่ม `repair_spaced_thai_chars()`: ตรวจสอบ pattern "ตัวอักษรไทย + space + ตัวอักษรไทย" (1-2 ตัว) แล้ว merge

**Code Pattern:**
```python
def repair_spaced_thai_chars(text: str) -> str:
    # Pattern: ตัวอักษรไทย 1-2 ตัว + space + ตัวอักษรไทย 1-2 ตัว
    pattern = r'([ก-๙]{1,2})\s+([ก-๙]{1,2})'
    return re.sub(pattern, r'\1\2', text)
```

---

#### 2.2 Collapse Repeated N-grams
**เป้าหมาย:** แก้ "สุข สา สุข สา สุข สา ..." ซ้ำยาว ๆ

**การเปลี่ยนแปลง:**
- เพิ่ม `collapse_repeated_ngrams()`: หา n-gram (default: 2) ที่ซ้ำติดกันเกิน threshold แล้วลดเหลือ 1-2 ครั้ง

**Code Pattern:**
```python
def collapse_repeated_ngrams(text: str, n: int = 2, max_repeats: int = 2) -> str:
    tokens = text.split()
    if len(tokens) < n * (max_repeats + 1):
        return text
    # Detect and collapse repeats
    ...
```

---

#### 2.3 Repair Syllable-Spaced Thai
**เป้าหมาย:** แก้ "คุณ สม บัต" → "คุณสมบัต" (ก่อน tokenize)

**การเปลี่ยนแปลง:**
- เพิ่ม heuristic ใน `postprocess_thai_text()`:
  - ถ้ามี Thai tokens หลายตัวที่สั้น (median ≤ 3 ตัวอักษร)
  - → รวม tokens ที่เป็น Thai ติดกัน (เว้น non-Thai ไว้)

**Code Pattern:**
```python
# In postprocess_thai_text()
tokens = text.split()
thai_tokens = [t for t in tokens if re.fullmatch(r"[ก-๙]+", t)]
if median_len <= 3:
    # Merge consecutive Thai tokens
    merged_parts = []
    run = ""
    for tok in tokens:
        if re.fullmatch(r"[ก-๙]+", tok):
            run += tok
        else:
            if run:
                merged_parts.append(run)
                run = ""
            merged_parts.append(tok)
```

---

### 3️⃣ WebSocket Outgoing Event Debugging (`app/services/websocket_service.py`)

#### 3.1 In-Memory Event Buffer
**เป้าหมาย:** ดูว่า server ส่ง caption event อะไรออกไปจริง (ไม่ต้องดูผ่าน WS client)

**การเปลี่ยนแปลง:**
- เพิ่ม `_recent_outgoing_events = deque(maxlen=...)` (ring buffer)
- ใน `send_to_user()` → เก็บ event summary (truncate ตาม `_STORE_OUTGOING_WS_MAX_CHARS`)
- เพิ่ม `get_recent_outgoing_events()` สำหรับ query (filter by meeting_id/type)

**Env Variables:**
```bash
WS_STORE_OUTGOING_EVENTS=true
WS_STORE_OUTGOING_CAPTIONS_ONLY=true
WS_STORE_OUTGOING_MAX_EVENTS=200
```

---

#### 3.2 HTTP Endpoint for Debugging
**เป้าหมาย:** เรียกดู outgoing events ผ่าน HTTP (ง่ายกว่า WS)

**การเปลี่ยนแปลง:**
- เพิ่ม `GET /ws/outgoing` ใน `app/api/websocket.py`
- Query params: `meeting_id`, `event_type`, `limit`

**Usage:**
```bash
curl "https://.../ws/outgoing?meeting_id=xxx&event_type=partial&limit=50"
```

---

#### 3.3 Logging Toggle
**เป้าหมาย:** เปิด/ปิด log ของ outgoing events (ลด log noise)

**การเปลี่ยนแปลง:**
- เพิ่ม env flags สำหรับ log verbosity
- Helper functions: `_truncate()`, `_should_log_payload()`, `_make_event_record()`

**Env Variables:**
```bash
WS_LOG_OUTGOING_EVENTS=true
WS_LOG_OUTGOING_CAPTIONS_ONLY=true
WS_LOG_OUTGOING_MAX_CHARS=400
```

---

### 4️⃣ Container Memory Monitoring (`app/api/monitoring.py`)

#### 4.1 CGroup Memory Reporting
**เป้าหมาย:** แยก "host RAM" กับ "container RAM limit" (pod 31GB limit ≠ host 251GB)

**การเปลี่ยนแปลง:**
- เพิ่ม `container_memory_used_gb`, `container_memory_limit_gb`, `container_memory_percent` ใน `SystemStats`
- อ่านจาก cgroup v1 (`/sys/fs/cgroup/memory/memory.usage_in_bytes`) หรือ v2 (`/sys/fs/cgroup/memory.current`)

**Code Pattern:**
```python
# Try cgroup v2 first
cgroup_mem_current = Path("/sys/fs/cgroup/memory.current")
cgroup_mem_max = Path("/sys/fs/cgroup/memory.max")
if cgroup_mem_current.exists():
    current_bytes = int(cgroup_mem_current.read_text().strip())
    max_bytes_str = cgroup_mem_max.read_text().strip()
    # Parse "max" or number
    ...
```

**Response Example:**
```json
{
  "container_memory_used_gb": 4.49,
  "container_memory_limit_gb": 57.74,
  "container_memory_percent": 7.78
}
```

---

### 5️⃣ Close Caption Batching Separation (`app/services/whisper_providers/faster_whisper_provider.py`)

#### 5.1 Separate CC Batching Config
**เป้าหมาย:** Live Caption ใช้ non-batched (ลด RAM peak) แต่ transcription ปกติใช้ batched ได้

**การเปลี่ยนแปลง:**
- เพิ่ม `CC_USE_BATCHED`, `CC_BATCH_SIZE` (แยกจาก `WHISPER_USE_BATCHED`)
- ใน `transcribe()` → ถ้า `CC_ENABLED` → ใช้ `CC_USE_BATCHED` แทน

**Code Pattern:**
```python
# In FasterWhisperProvider.transcribe()
if is_close_caption:
    use_batched = os.getenv("CC_USE_BATCHED", "false").lower() == "true"
    batch_size = int(os.getenv("CC_BATCH_SIZE", "8"))
else:
    use_batched = self.use_batched
    batch_size = self.batch_size
```

**Env Variables:**
```bash
CC_USE_BATCHED=false  # Live Caption ใช้ non-batched
CC_BATCH_SIZE=8
```

---

### 6️⃣ Environment Configuration (`.env.runpod`)

#### 6.1 FE Live Caption Tuning
```bash
# Window/Step/Silence
FE_CC_WINDOW_SECONDS=3.0
FE_CC_MIN_WINDOW_SECONDS=1.6
FE_CC_STEP_SECONDS=0.6
FE_CC_SILENCE_THRESHOLD=0.9

# Partial gating
FE_CC_PARTIAL_ENABLED=true
FE_CC_PARTIAL_MIN_CHARS=6
FE_CC_PARTIAL_MIN_TIME=0.7

# Word-by-word
FE_CC_WORDWISE_ENABLED=true
FE_CC_WORDS_PER_UPDATE=1
FE_CC_FORCE_FINAL_MAX_TOKENS=45
FE_CC_FORCE_FINAL_MAX_SECONDS=8.0

# Debug
FE_CC_AUTO_SAMPLE_RATE_ENABLED=false
FE_CC_UPLINK_KEEPALIVE_SECONDS=15
```

#### 6.2 Uvicorn WebSocket Keepalive
```bash
UVICORN_WS_PING_INTERVAL=20
UVICORN_WS_PING_TIMEOUT=60
```

#### 6.3 WS Outgoing Logging/Buffer
```bash
WS_LOG_OUTGOING_EVENTS=true
WS_LOG_OUTGOING_CAPTIONS_ONLY=true
WS_LOG_OUTGOING_MAX_CHARS=400
WS_STORE_OUTGOING_EVENTS=true
WS_STORE_OUTGOING_CAPTIONS_ONLY=true
WS_STORE_OUTGOING_MAX_EVENTS=200
```

#### 6.4 CC Batching Separation
```bash
CC_USE_BATCHED=false
CC_BATCH_SIZE=8
```

---

### 7️⃣ Script Improvements

#### 7.1 `scripts/pod/restart-main-api.sh`
**การเปลี่ยนแปลง:**
- โหลด `.env.runpod` ก่อน start (ให้ `WHISPER_PROVIDER/MODEL` ตรงกับ production)
- เพิ่ม `--ws-ping-interval` และ `--ws-ping-timeout` ใน uvicorn command

**Code Pattern:**
```bash
if [ -f "$PROJECT_ROOT/.env.runpod" ]; then
    set -a
    source "$PROJECT_ROOT/.env.runpod"
    set +a
fi

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8010 \
  --ws-ping-interval "${UVICORN_WS_PING_INTERVAL:-20}" \
  --ws-ping-timeout "${UVICORN_WS_PING_TIMEOUT:-60}" \
  > /tmp/main-api.log 2>&1 & disown
```

---

#### 7.2 `scripts/pod/start-rq-workers.sh`
**การเปลี่ยนแปลง:**
- ใช้ `RQ_PRELOAD_MODEL` จาก env (ไม่ hardcode `true`)
- เตือนถ้า `RQ_PRELOAD_MODEL=true` + `GPU_WORKERS_PER_GPU > 1` (เสี่ยงคูณโมเดล)

**Code Pattern:**
```bash
RQ_PRELOAD_MODEL=${RQ_PRELOAD_MODEL:-false}
if [ "$RQ_PRELOAD_MODEL" = "true" ] && [ "$GPU_WORKERS_PER_GPU" -gt 1 ]; then
    print_warning "RQ_PRELOAD_MODEL=true with GPU_WORKERS_PER_GPU>1 will duplicate model in RAM/VRAM (may OOM)."
fi
```

---

## 🔍 ปัญหาที่แก้ได้

### ✅ "ข้อความไทยอ่านไม่ออก" (เว้นวรรค/คำซ้ำ)
- **สาเหตุ:** Audio source จาก `<video>` (HLS/MSE) มี burst/gap → โมเดลถอดเป็นพยางค์ ๆ
- **แก้:** Postprocess (`repair_spaced_thai_chars`, `collapse_repeated_ngrams`, syllable merge)

### ✅ "ค้าง 10 นาที แล้วหยุดแปล"
- **สาเหตุ:** WS ถูกตัดด้วย `1011 keepalive ping timeout` (event loop ถูกบล็อก)
- **แก้:** ย้ายงานหนักไป thread + เพิ่ม server keepalive

### ✅ "RAM เต็ม 31GB" (container limit)
- **สาเหตุ:** หลาย process โหลดโมเดลซ้ำ + batched inference peak สูง
- **แก้:** แยก `CC_USE_BATCHED=false` + monitoring cgroup memory

### ✅ "code=1006 abnormal close"
- **สาเหตุ:** Proxy ตัดเมื่อ server เงียบฝั่งตอบกลับ
- **แก้:** Server → client keepalive + uvicorn ping config

---

## 📝 หมายเหตุสำคัญ

### ⚠️ Audio Source Quality
**ปัญหาหลักที่ทำให้ "อ่านไม่ออก" ไม่ใช่โมเดล แต่คือแหล่งเสียง:**
- `<video>.captureStream()` จาก HLS/MSE → มี burst/gap ได้
- **แนะนำ:** ใช้ `audioContext.createMediaElementSource(videoEl)` แทน (นิ่งกว่า)

### ⚠️ Frontend Auto-Reconnect
**ต่อให้ BE แก้ keepalive แล้ว FE ยังต้องทำ reconnect:**
- `onclose` ถ้า `code === 1006 || code === 1011` → reconnect (backoff 1s → 2s → 4s)
- ระหว่าง reconnect → worklet ยังผลิตเฟรมได้ (แต่ drop ถ้า buffer เต็ม)

### ⚠️ Model Duplication
**"โมเดลเดียว" ≠ "โหลดครั้งเดียว":**
- ถ้ามี `GPU_WORKERS_PER_GPU=10` → โหลดโมเดลซ้ำ 10 ครั้ง (RAM คูณ)
- **แนะนำ:** `GPU_WORKERS_PER_GPU=2-3` + ใช้ `CHUNK_INFLIGHT_LIMIT` สำหรับ throughput

---

## 🚀 Next Steps (ถ้าจะทำต่อ)

1. **UX Web Speech API จริง:** ส่ง `final_append` + `live_replace` (revisable window) แทน `partial/final` แบบปัจจุบัน
2. **Audio Source:** เปลี่ยน FE จาก `captureStream()` → `createMediaElementSource()` (HLS/MSE)
3. **Auto-Reconnect:** เพิ่ม reconnect logic ที่ FE (backoff + init resend)

---

## 📚 References

- Web Speech API: https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition
- Chrome Live Caption: https://support.google.com/chrome/answer/10538231
- Uvicorn WebSocket: https://www.uvicorn.org/settings/#websocket-settings

---

**Last Updated:** 2026-01-29  
**Status:** ⚠️ Discarded (บางส่วน re-implement แล้ว: non-blocking, keepalive, uvicorn WS ping)

---

## 📌 Single Model + 2 GPU (2026-01-29)

### ใช้โมเดลเดียวได้ไหม (faster-whisper + close-caption)?

**ได้** — ตั้งค่าให้ทั้ง transcription และ close-caption ใช้โมเดลเดียวกัน:

1. **WHISPER_MODEL** (เช่น `.env.runpod` บรรทัด 48–49): ใช้เป็นโมเดลหลัก  
   - ตัวอย่าง: `WHISPER_MODEL=models--Vinxscribe--biodatlab-whisper-th-medium-faster`

2. **CC_MODEL_SIZE**:  
   - **ถ้าตั้งค่า** → ใช้ค่านี้สำหรับ close-caption (สามารถใช้ชื่อเดียวกับ `WHISPER_MODEL` ได้)  
   - **ถ้าไม่ตั้ง** → ระบบใช้ `WHISPER_MODEL` เป็น fallback (โมเดลเดียวทั้ง transcription และ close-caption)

ดังนั้นถ้าต้องการโมเดลเดียว: ตั้ง `WHISPER_MODEL` อย่างเดียว แล้วไม่ตั้ง `CC_MODEL_SIZE` หรือตั้ง `CC_MODEL_SIZE` ให้เท่ากับ `WHISPER_MODEL` ก็ได้

### Worker โหลดโมเดลทุกครั้งหรือไม่?

- **Main API (WebSocket ingest)**: โหลดโมเดลครั้งเดียวต่อ process (singleton / cache ใน faster-whisper)
- **RQ Workers**: แต่ละ worker process โหลดโมเดลของตัวเอง  
  - `RQ_PRELOAD_MODEL=true` → โหลดตอน start (ครั้งเดียวต่อ process)  
  - `RQ_PRELOAD_MODEL=false` → โหลดเมื่อ job แรกมาถึง (lazy)

ถ้าใช้ **2 GPU** และ `GPU_WORKERS_PER_GPU=10` จะมี 20 worker processes → โมเดลถูกโหลด 20 ครั้ง (RAM/VRAM คูณตามจำนวน process)

**ทางเลือกเพื่อลดการโหลดโมเดลซ้ำ:**

1. **ใช้โมเดลเดียวแต่ลดจำนวน workers**: เช่น `GPU_WORKERS_PER_GPU=2` หรือ 3 แล้วใช้ `CHUNK_INFLIGHT_LIMIT` จัด throughput แทน (เอกสารเดิมแนะนำ 2–3 ต่อ GPU)
2. **ใช้ Whisper API แยก (builtin provider)**: รัน whisper service ตัวเดียว (โหลดโมเดลครั้งเดียว) แล้วให้ทั้ง Main API และ RQ workers เรียก HTTP ไปที่ service นั้น — ต้องเปลี่ยนเป็น `WHISPER_PROVIDER=builtin` และให้ process เดียวโหลดโมเดล
3. **คง faster-whisper in-process แต่ลด workers**: ใช้ `RQ_PRELOAD_MODEL=true` เพื่อไม่ให้โหลดซ้ำในแต่ละ job ภายใน process เดียวกัน แต่ยังคงโหลดต่อ process ตามจำนวน worker

สรุป: **ใช้โมเดลเดียวได้** ผ่าน `WHISPER_MODEL` + fallback ใน CloseCaptionConfig; การที่ worker “ไม่โหลดทุกครั้ง” หมายถึงไม่โหลดซ้ำในแต่ละ job ภายใน process เดียว (preload) ไม่ได้หมายถึงโมเดลแชร์ข้าม process — ถ้าต้องการโหลดจริงๆ แค่ครั้งเดียวให้ใช้ whisper API แยกหรือลดจำนวน worker
