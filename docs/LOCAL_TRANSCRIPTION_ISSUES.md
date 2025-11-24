# 🔧 แก้ไขปัญหา Transcription บน Local Environment

## 📋 สรุปปัญหา

### 1. **404 Error: `/api/transcription/9/segments`**
- **สาเหตุ**: Job ยังไม่มี Result เพราะ transcription ยังไม่เสร็จ
- **สถานะ**: ✅ Frontend จัดการแล้ว - return empty segments array เมื่อได้ 404
- **ไม่ต้องแก้ไข**: Frontend code จัดการกรณีนี้แล้ว

### 2. **Whisper Timeout Errors**
- **Error**: `HTTPConnectionPool(host='whisper', port=8002): Read timed out. (read timeout=300)`
- **Error**: `ERROR:__main__:การแปลงเสียงใช้เวลานานเกินไป`
- **สาเหตุ**: Whisper service ใช้เวลานานกว่า 5 นาที (300 วินาที) ในการแปลงเสียง
- **สถานะ**: ✅ แก้ไขแล้ว (timeout=600) แต่ยังไม่ได้ deploy

### 3. **RabbitMQ Connection Reset**
- **Error**: `ConnectionResetError: [Errno 104] Connection reset by peer`
- **สถานะ**: ✅ Auto-reconnect ทำงานแล้ว - ไม่ต้องแก้ไข

## ✅ การแก้ไขที่ทำแล้ว

### 1. เพิ่ม Whisper API Timeout

**ไฟล์**: `app/services/whisper_service.py`

**เปลี่ยนจาก:**
```python
timeout=300  # 5 นาที
```

**เป็น:**
```python
timeout=600  # 10 นาที (เพิ่มจาก 5 นาที เพื่อรองรับ chunks ที่ซับซ้อน)
```

**ผลลัพธ์**: Whisper service จะรอได้นานขึ้น (10 นาที) ก่อน timeout

### 2. Frontend Handle 404 Gracefully

**ไฟล์**: `src/services/transcriptionBackendService.ts`

**Code:**
```typescript
const getTranscriptionSegmentsAsync = async (jobId: number): Promise<TranscriptionSegmentsResponse> => {
  try {
    const response = await http.get<TranscriptionSegmentsResponse>(`api/transcription/${jobId}/segments`);
    // ...
  } catch (err: any) {
    const status = err?.response?.status as number | undefined;
    // 404 = job ยังไม่เสร็จหรือไม่มี Result (ปกติ - ไม่ใช่ error)
    if (status === 404) {
      return {
        job_id: jobId,
        source: "Database",
        segments: [],
        segments_count: 0
      };
    }
    throw err;
  }
};
```

**ผลลัพธ์**: Frontend จะ return empty segments array แทน throw error เมื่อ job ยังไม่เสร็จ

## 🚀 Deployment

### Step 1: Build และ Push Docker Image ใหม่

```bash
cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service
./scripts/build-and-push-acr.sh
```

### Step 2: Deploy Image ใหม่ (Local)

```bash
# Restart transcription services
docker-compose restart transcription-api video-worker-1 video-worker-2 whisper
```

### Step 3: ตรวจสอบ Logs

```bash
# ตรวจสอบว่า timeout fix ทำงานแล้ว
docker logs video-worker-1 --tail 50 | grep -E "timeout|ERROR"
docker logs whisper --tail 50 | grep -E "timeout|ERROR"
```

## 📝 หมายเหตุ

1. **404 Error เป็นปกติ**: เมื่อ transcription ยังไม่เสร็จ job จะไม่มี Result → return 404
2. **Frontend จัดการแล้ว**: Frontend จะ retry หรือแสดง loading state
3. **Timeout Issues**: ต้อง deploy image ใหม่ที่มี timeout fix (600 seconds)

## 🔍 การตรวจสอบ

### 1. ตรวจสอบว่า Timeout Fix ทำงานแล้ว

```bash
# ตรวจสอบ logs ว่าไม่มี timeout errors แล้ว
docker logs video-worker-1 --tail 100 | grep -E "timeout=600|Read timed out"
```

### 2. ตรวจสอบ Transcription Progress

```bash
# ตรวจสอบว่า transcription กำลังทำงาน
docker logs transcription-api --tail 50 | grep -E "transcription|chunk"
```

### 3. ตรวจสอบ Whisper Service

```bash
# ตรวจสอบว่า Whisper service ทำงานปกติ
docker logs whisper --tail 50 | grep -E "transcribe|ERROR"
```

## 🎯 สรุป

1. ✅ **404 Error**: Frontend จัดการแล้ว - ไม่ต้องแก้ไข
2. ✅ **Whisper Timeout**: แก้ไขแล้ว (timeout=600) - ต้อง deploy
3. ✅ **RabbitMQ Connection**: Auto-reconnect ทำงานแล้ว - ไม่ต้องแก้ไข

**Next Step**: Deploy transcription service image ใหม่ที่มี timeout fix

