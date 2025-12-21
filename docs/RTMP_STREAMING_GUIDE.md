# 🎥 RTMP Streaming with Transcription & Close Caption Guide

## 📋 สรุป

ระบบนี้รองรับการรับสัญญาณ RTMP และแสดงเป็น HLS พร้อมกับ:
- ✅ แยกสัญญาณเสียงมา transcription (3 วินาที หรือ realtime)
- ✅ บันทึก text
- ✅ ทำ restream → ffmpeg burn-in แสดง Close Caption (Overlay Text)
- ✅ ค้นหาข้อความจาก Close Caption และหาเวลาที่บันทึก

## 🏗️ สถาปัตยกรรม

```
nginx-rtmp ingest (port 1935)
   ├── A) Clean relay out  ─────────► rtmp://localhost:1936/clean/stream
   │                                    └──► HLS: /hls/clean/stream.m3u8
   │
   └── B) CC pipeline (ffmpeg burn-in) ─► rtmp://localhost:1937/cc/stream
                                            └──► HLS: /hls/cc/stream.m3u8
```

## 🚀 การติดตั้งและเริ่มใช้งาน

### 1. ติดตั้ง Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y nginx libnginx-mod-rtmp ffmpeg

# หรือใช้ script
bash scripts/pod/start-rtmp-services.sh
```

### 2. เริ่ม Services

```bash
# เริ่ม nginx-rtmp
bash scripts/pod/start-rtmp-services.sh

# เริ่ม Main API (port 8010)
bash scripts/pod/start-services-direct.sh
```

### 3. เปิด Frontend

เปิดเบราว์เซอร์ไปที่:
```
http://localhost:8010/static/rtmp-streaming.html
```

## 📡 การใช้งาน RTMP

### Push RTMP Stream

ใช้ OBS Studio หรือ FFmpeg:

```bash
# ใช้ FFmpeg
ffmpeg -re -i input.mp4 -c copy -f flv rtmp://localhost:1935/live/test_stream

# หรือใช้ OBS Studio
# RTMP URL: rtmp://localhost:1935/live
# Stream Key: test_stream
```

### HLS URLs

- **Clean Stream** (ไม่มี CC): `http://localhost:8080/hls/clean/test_stream.m3u8`
- **CC Stream** (มี Close Caption): `http://localhost:8080/hls/cc/test_stream.m3u8`

## 🔌 API Endpoints

### Stream Management

```bash
# เริ่ม stream session
POST /api/rtmp/stream/start
{
  "stream_key": "test_stream",
  "stream_name": "test_stream",
  "language": "th",
  "model_size": "base"
}

# หยุด stream
POST /api/rtmp/stream/stop/{stream_id}

# ดึงสถานะ stream
GET /api/rtmp/stream/status/{stream_id}

# ดึงรายการ streams
GET /api/rtmp/streams
```

### Transcriptions

```bash
# ดึง transcriptions
GET /api/rtmp/stream/{stream_id}/transcriptions
```

### Burn-in (Close Caption)

```bash
# เริ่ม burn-in
POST /api/rtmp/stream/{stream_id}/burnin/start

# อัปเดต captions
POST /api/rtmp/stream/{stream_id}/burnin/update
{
  "caption_segments": [
    {
      "start": 0.0,
      "end": 3.0,
      "text": "สวัสดีครับ"
    }
  ]
}

# หยุด burn-in
POST /api/rtmp/stream/{stream_id}/burnin/stop
```

### Search

```bash
# ค้นหาข้อความ
GET /api/rtmp/stream/{stream_id}/search?query=สวัสดี&case_sensitive=false

# ดึง timeline
GET /api/rtmp/stream/{stream_id}/timeline

# ค้นหาตามช่วงเวลา
GET /api/rtmp/stream/{stream_id}/time-range?start_time=0&end_time=60
```

## 🔄 Flow การทำงาน

1. **RTMP Ingest**: Client push stream ไปที่ `rtmp://localhost:1935/live/stream_key`
2. **nginx-rtmp**: รับ stream และ relay ไป 2 paths:
   - Clean stream → `rtmp://localhost:1936/clean/stream` → HLS
   - CC stream → `rtmp://localhost:1937/cc/stream` → HLS (พร้อม burn-in)
3. **Transcription**: Service แยกเสียงจาก HLS segments และทำ transcription ทุก 3 วินาที
4. **Burn-in**: FFmpeg overlay Close Caption บนวิดีโอ
5. **Storage**: บันทึก transcriptions และ captions ลง storage
6. **Search**: ค้นหาข้อความจาก captions และหาเวลาที่บันทึก

## 🎯 Features

### ✅ Real-time Transcription
- แยกเสียงจาก HLS segments ทุก 3 วินาที
- ใช้ Whisper model สำหรับ transcription
- รองรับภาษาไทยและภาษาอื่นๆ

### ✅ Close Caption Burn-in
- ใช้ FFmpeg drawtext filter
- Overlay ข้อความบนวิดีโอ
- รองรับการอัปเดต captions แบบ real-time

### ✅ Search & Timeline
- ค้นหาข้อความจาก captions
- ดึง timeline ทั้งหมด
- ค้นหาตามช่วงเวลา

## 🐛 Troubleshooting

### nginx ไม่ start
```bash
# ตรวจสอบ config
sudo nginx -t

# ดู logs
sudo tail -f /var/log/nginx/error.log
```

### RTMP ไม่รับ stream
```bash
# ตรวจสอบ port
netstat -tuln | grep 1935

# ตรวจสอบ nginx status
curl http://localhost:8080/stat
```

### Transcription ไม่ทำงาน
```bash
# ตรวจสอบว่า Whisper service ทำงานอยู่
curl http://localhost:8002/health

# ตรวจสอบ logs
tail -f /tmp/main-api.log
```

## 📝 Notes

- HLS segments ถูกเก็บไว้ที่ `/tmp/hls/`
- Transcriptions ถูกบันทึกใน `storage/captions/`
- ใช้ Python + HTML + JS (ไม่ต้อง React) เพื่อให้ง่ายและเร็ว
- รองรับการทดสอบแบบ Full Function ก่อนย้ายไป Server ใหม่

