# 📊 การวิเคราะห์ Memory Usage สำหรับ Audio Tap (RTMP Stream)

## 🎯 สรุปผลการวิเคราะห์

**ความเสี่ยง: ⚠️ สูง - มีโอกาสทำให้ Memory เต็ม 31GB หาก stream ทำงานต่อเนื่องเป็นเวลานาน**

---

## 📈 การคำนวณ Memory Usage

### สถานการณ์: ส่งข้อมูลทุก 3 วินาที

#### 1. RTMP Stream Service (`rtmp_stream_service.py`)

**ปัญหาหลัก: เก็บ transcriptions ใน memory โดยไม่จำกัด**

```python
# Line 36, 73, 154
self.transcriptions[stream_id] = []  # ไม่มีการจำกัดขนาด
self.transcriptions[stream_id].append(result)  # เพิ่มเรื่อยๆ
```

**การคำนวณ:**

- **Frequency**: ทุก 3 วินาที = 20 chunks/นาที = 1,200 chunks/ชั่วโมง
- **ขนาดต่อ transcription result**:
  - Text: ~50-200 ตัวอักษร = ~150-600 bytes
  - Segments: ~2-5 segments × ~500 bytes = ~1-2.5 KB
  - Metadata: ~500 bytes
  - **รวม**: ~2-4 KB ต่อ transcription result

- **Memory usage ต่อ stream**:
  - 1 ชั่วโมง: 1,200 × 3 KB = **3.6 MB**
  - 24 ชั่วโมง: 1,200 × 24 × 3 KB = **86.4 MB**
  - 7 วัน: 1,200 × 24 × 7 × 3 KB = **604.8 MB**

- **Memory usage หลาย streams พร้อมกัน**:
  - 10 streams × 24 ชั่วโมง = **864 MB**
  - 50 streams × 24 ชั่วโมง = **4.32 GB**
  - 100 streams × 24 ชั่วโมง = **8.64 GB**
  - 200 streams × 7 วัน = **120.96 GB** ⚠️

**⚠️ ปัญหา**: ถ้ามีหลาย streams พร้อมกันและทำงานต่อเนื่องเป็นเวลานาน memory จะเพิ่มขึ้นเรื่อยๆ โดยไม่มีการ cleanup จนกว่า stream จะหยุด

---

#### 2. Live Chunk (`realtime_transcription.py`)

**ดีแล้ว: มีการจำกัดขนาด**

```python
# Line 487-489
if len(_chunk_metadata_store[meeting_id]) > 100:
    _chunk_metadata_store[meeting_id] = _chunk_metadata_store[meeting_id][-100:]
```

**การคำนวณ:**

- **จำกัด**: 100 chunks ต่อ meeting
- **ขนาดต่อ chunk metadata**: ~500 bytes
- **Memory usage**: 100 × 500 bytes = **50 KB ต่อ meeting**
- **100 meetings พร้อมกัน**: 100 × 50 KB = **5 MB**

**✅ ไม่เป็นปัญหา**: มีการจำกัดขนาดและ cleanup อัตโนมัติ

---

#### 3. Audio Stream (`realtime_audio_stream.py`)

**ดีแล้ว: มีการ cleanup เมื่อ stream จบ**

```python
# Line 477-479
if session_id in active_stream_sessions:
    del active_stream_sessions[session_id]
```

**✅ ไม่เป็นปัญหา**: มีการ cleanup session เมื่อ stream จบ

---

## 🚨 สถานการณ์ที่ทำให้ Memory เต็ม 31GB

### สถานการณ์ที่ 1: หลาย Streams พร้อมกัน

ถ้ามี **~360 streams** พร้อมกันและแต่ละ stream ทำงาน **24 ชั่วโมง**:
- 360 streams × 86.4 MB = **31.1 GB** ⚠️

### สถานการณ์ที่ 2: Stream ทำงานต่อเนื่องหลายวัน

ถ้ามี **~50 streams** พร้อมกันและแต่ละ stream ทำงาน **7 วัน**:
- 50 streams × 604.8 MB = **30.24 GB** ⚠️

### สถานการณ์ที่ 3: Stream ไม่หยุด (Memory Leak)

ถ้า stream ไม่หยุดหรือมี error ที่ทำให้ cleanup ไม่ทำงาน:
- Memory จะเพิ่มขึ้นเรื่อยๆ จนเต็ม

---

## 🔍 ปัญหาที่พบ

### 1. RTMP Stream Service - ไม่มีการจำกัด Memory

**ไฟล์**: `app/services/rtmp/rtmp_stream_service.py`

**ปัญหา**:
- `self.transcriptions[stream_id]` เก็บทุก transcription result โดยไม่จำกัด
- ไม่มีการ cleanup จนกว่า stream จะหยุด
- ถ้า stream ทำงานนาน transcriptions จะเพิ่มขึ้นเรื่อยๆ

**ผลกระทบ**:
- Memory leak เมื่อมีหลาย streams พร้อมกัน
- Memory เต็มเมื่อ stream ทำงานต่อเนื่องเป็นเวลานาน

---

### 2. ไม่มีการ Cleanup Periodic

**ปัญหา**:
- ไม่มีการ cleanup transcriptions ที่เก่าแล้ว
- ไม่มีการจำกัดจำนวน transcriptions ต่อ stream

---

## 💡 แนวทางแก้ไข

### 1. จำกัดจำนวน Transcriptions ต่อ Stream

```python
# ใน rtmp_stream_service.py
MAX_TRANSCRIPTIONS_PER_STREAM = 1000  # จำกัดไว้ 1000 transcriptions

async def _transcribe_segment(self, stream_id: str, audio_path: str, timestamp: float):
    # ... existing code ...
    
    # จำกัดจำนวน transcriptions
    if len(self.transcriptions[stream_id]) >= MAX_TRANSCRIPTIONS_PER_STREAM:
        # ลบ transcriptions เก่าที่สุด (FIFO)
        self.transcriptions[stream_id] = self.transcriptions[stream_id][-MAX_TRANSCRIPTIONS_PER_STREAM + 1:]
    
    self.transcriptions[stream_id].append(result)
```

**ผลลัพธ์**: จำกัด memory usage ต่อ stream ไว้ที่ ~3 MB (1,000 × 3 KB)

---

### 2. Periodic Cleanup Transcriptions

```python
# เพิ่ม periodic cleanup task
async def _cleanup_old_transcriptions(self):
    """Cleanup transcriptions ที่เก่ากว่า 1 ชั่วโมง"""
    current_time = time.time()
    for stream_id in list(self.transcriptions.keys()):
        transcriptions = self.transcriptions[stream_id]
        # ลบ transcriptions ที่เก่ากว่า 1 ชั่วโมง
        self.transcriptions[stream_id] = [
            t for t in transcriptions 
            if current_time - t.get('timestamp', 0) < 3600
        ]
```

---

### 3. บันทึก Transcriptions ลง Storage ทันที

```python
# แทนการเก็บใน memory ให้บันทึกลง storage ทันที
async def _transcribe_segment(self, stream_id: str, audio_path: str, timestamp: float):
    # ... transcription ...
    
    # บันทึกลง storage ทันที (ไม่เก็บใน memory)
    await self._save_transcription_to_storage(stream_id, result)
    
    # เก็บแค่ metadata ใน memory (ไม่เก็บ full result)
    self.transcriptions[stream_id].append({
        "timestamp": timestamp,
        "text_length": len(result.get("text", "")),
        "segments_count": len(result.get("segments", []))
    })
```

---

## 📊 สรุปความเสี่ยง

| สถานการณ์ | Memory Usage | ความเสี่ยง |
|-----------|--------------|------------|
| 1 stream × 1 ชั่วโมง | 3.6 MB | ✅ ต่ำ |
| 10 streams × 24 ชั่วโมง | 864 MB | ⚠️ ปานกลาง |
| 50 streams × 24 ชั่วโมง | 4.32 GB | ⚠️ สูง |
| 100 streams × 24 ชั่วโมง | 8.64 GB | 🚨 สูงมาก |
| 360 streams × 24 ชั่วโมง | 31.1 GB | 🚨 **เต็ม Memory** |
| 50 streams × 7 วัน | 30.24 GB | 🚨 **เต็ม Memory** |

---

## ✅ คำแนะนำ

1. **เพิ่มการจำกัดจำนวน transcriptions ต่อ stream** (แนะนำ: 1,000 transcriptions)
2. **เพิ่ม periodic cleanup** สำหรับ transcriptions ที่เก่า
3. **บันทึก transcriptions ลง storage ทันที** แทนการเก็บใน memory
4. **Monitor memory usage** และแจ้งเตือนเมื่อใกล้เต็ม
5. **เพิ่ม logging** เพื่อ track memory usage ของแต่ละ stream

---

## 🔧 Implementation Priority

1. **High Priority**: จำกัดจำนวน transcriptions ต่อ stream
2. **Medium Priority**: Periodic cleanup
3. **Low Priority**: บันทึกลง storage ทันที (ต้อง refactor)

---

**วันที่วิเคราะห์**: 2024-12-19
**วิเคราะห์โดย**: AI Code Analysis
