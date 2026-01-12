# 🔍 การตรวจสอบ Audio Tap Stream (RTMP Stream)

## 📋 สรุปผลการตรวจสอบ

**ผลการตรวจสอบ**: ✅ **มีระบบรองรับ Audio Tap Stream (RTMP Stream) และมีการส่งข้อมูลมาให้แปลง**

---

## 🎯 ระบบที่รองรับ Audio Tap Stream

### 1. RTMP Stream Service (`app/services/rtmp/rtmp_stream_service.py`)

**หน้าที่**: รับ RTMP stream และทำ transcription แบบ real-time

**การทำงาน**:
- รับ RTMP stream ผ่าน nginx-rtmp
- แปลงเป็น HLS segments
- ทำ transcription ทุก 3 วินาที (ตาม `chunk_duration = 3`)
- เก็บ transcription results ใน memory (`self.transcriptions[stream_id]`)

**⚠️ ปัญหา**: เก็บ transcriptions ใน memory โดยไม่จำกัด (ตามที่วิเคราะห์ใน MEMORY_ANALYSIS_AUDIO_TAP.md)

---

### 2. Endpoints ที่เกี่ยวข้อง

#### A. RTMP Stream Callbacks

**`POST /api/rtmp/on_publish`**
- เรียกเมื่อมี RTMP stream เข้ามา
- เริ่ม stream session และ transcription worker
- **ไฟล์**: `dashboard/routes/rtmp_streaming_routes.py:52`

**`POST /api/rtmp/on_publish_done`**
- เรียกเมื่อ RTMP stream หยุด
- หยุด stream session และ cleanup
- **ไฟล์**: `dashboard/routes/rtmp_streaming_routes.py:73`

#### B. Manual Stream Control

**`POST /api/rtmp/stream/start`**
- เริ่ม stream แบบ manual
- **ไฟล์**: `dashboard/routes/rtmp_streaming_routes.py:99`

**`POST /api/rtmp/stream/stop/{stream_id}`**
- หยุด stream
- **ไฟล์**: `dashboard/routes/rtmp_streaming_routes.py:121`

#### C. Stream Status

**`GET /api/rtmp/streams`**
- ดูรายการ active streams ทั้งหมด
- **ไฟล์**: `dashboard/routes/rtmp_streaming_routes.py:170`

**`GET /api/rtmp/stream/status/{stream_id}`**
- ดูสถานะ stream เฉพาะ
- **ไฟล์**: `dashboard/routes/rtmp_streaming_routes.py:144`

**`GET /api/rtmp/stream/{stream_id}/transcriptions`**
- ดู transcriptions ของ stream
- **ไฟล์**: `dashboard/routes/rtmp_streaming_routes.py:184`

---

### 3. Transcription Worker

**ไฟล์**: `app/services/rtmp/rtmp_stream_service.py:96`

**การทำงาน**:
```python
async def _transcription_worker(self, stream_id: str):
    """Worker สำหรับทำ transcription จาก HLS stream"""
    # อ่าน HLS playlist
    # หา segments ใหม่
    # แยกเสียงจาก segment
    # ทำ transcription
    # เก็บผลลัพธ์ใน self.transcriptions[stream_id]
    await asyncio.sleep(self.chunk_duration)  # 3 วินาที
```

**ความถี่**: ทุก 3 วินาที (ตาม `chunk_duration = 3`)

---

## 🔍 วิธีตรวจสอบว่ามีการส่ง Stream มาให้แปลงหรือไม่

### วิธีที่ 1: ตรวจสอบผ่าน API Endpoint

```bash
# ดูรายการ active streams
curl http://localhost:8010/api/rtmp/streams

# ดูสถานะ stream เฉพาะ
curl http://localhost:8010/api/rtmp/stream/status/{stream_id}

# ดู transcriptions ของ stream
curl http://localhost:8010/api/rtmp/stream/{stream_id}/transcriptions
```

### วิธีที่ 2: ตรวจสอบ Logs

**Logs ที่ควรเห็นเมื่อมี stream เข้ามา**:
```
📡 RTMP stream published: {name} (key: {stream_key})
✅ Started RTMP stream: {stream_id}
🎤 Starting transcription worker for stream: {stream_id}
📝 Transcribed segment: {text}...
```

### วิธีที่ 3: ตรวจสอบ Memory Usage

**ตรวจสอบว่า `self.transcriptions` มีข้อมูลหรือไม่**:
- ถ้ามี stream ทำงาน transcriptions จะเพิ่มขึ้นเรื่อยๆ
- ตรวจสอบผ่าน endpoint `/api/rtmp/stream/{stream_id}/transcriptions`

---

## 📊 สถานะการทำงาน

### ✅ สิ่งที่ทำงานได้

1. **รับ RTMP Stream**: ✅ ผ่าน nginx-rtmp callback
2. **แปลงเป็น HLS**: ✅ nginx-rtmp แปลงอัตโนมัติ
3. **ทำ Transcription**: ✅ Transcription worker ทำงานทุก 3 วินาที
4. **เก็บผลลัพธ์**: ✅ เก็บใน `self.transcriptions[stream_id]`

### ⚠️ ปัญหาที่พบ

1. **Memory Leak**: เก็บ transcriptions ใน memory โดยไม่จำกัด
   - ดูรายละเอียดใน `MEMORY_ANALYSIS_AUDIO_TAP.md`
   - **ความเสี่ยง**: Memory เต็ม 31GB เมื่อมี ~360 streams × 24 ชั่วโมง

2. **ไม่มีการ Cleanup Periodic**: 
   - Transcriptions จะเก็บไว้จนกว่า stream จะหยุด
   - ถ้า stream ไม่หยุด memory จะเพิ่มขึ้นเรื่อยๆ

---

## 🎯 สรุป

### ✅ มีการส่ง Audio Tap Stream มาให้แปลงข้อมูล

**หลักฐาน**:
1. ✅ มี RTMP Stream Service ที่รองรับ
2. ✅ มี Transcription Worker ที่ทำงานทุก 3 วินาที
3. ✅ มี Endpoints สำหรับจัดการ streams
4. ✅ มี Callback จาก nginx-rtmp เมื่อมี stream เข้ามา

**การทำงาน**:
- RTMP stream → nginx-rtmp → HLS segments
- Transcription worker อ่าน HLS segments ทุก 3 วินาที
- ทำ transcription และเก็บผลลัพธ์ใน memory

**⚠️ ข้อควรระวัง**:
- Memory จะเพิ่มขึ้นเรื่อยๆ ถ้ามีหลาย streams พร้อมกัน
- ควรเพิ่มการจำกัดจำนวน transcriptions ต่อ stream

---

## 📝 คำแนะนำ

1. **ตรวจสอบ Active Streams**: ใช้ `GET /api/rtmp/streams`
2. **Monitor Memory Usage**: ตรวจสอบ `self.transcriptions` ว่ามีขนาดเท่าไหร่
3. **เพิ่ม Memory Limit**: จำกัดจำนวน transcriptions ต่อ stream (แนะนำ: 1,000)
4. **เพิ่ม Periodic Cleanup**: ลบ transcriptions ที่เก่ากว่า 1 ชั่วโมง

---

**วันที่ตรวจสอบ**: 2024-12-19
**สถานะ**: ✅ ระบบทำงานได้ แต่มีปัญหา Memory Leak
