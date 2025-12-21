# RTMP Services (Optional)

โฟลเดอร์นี้เก็บ RTMP-related services ที่เป็น **optional features** สำหรับทดสอบเท่านั้น

## Services

- `rtmp_stream_service.py` - จัดการ RTMP streams และ transcription
- `ffmpeg_burnin_service.py` - Burn-in Close Caption ด้วย FFmpeg
- `caption_search_service.py` - ค้นหาข้อความจาก Close Caption

## การใช้งาน

Services เหล่านี้จะถูก import แบบ optional ใน dashboard:

```python
try:
    from app.services.rtmp import RTMPStreamService, FFmpegBurninService, CaptionSearchService
except ImportError:
    # Services ไม่พร้อมใช้งาน (optional)
    pass
```

## หมายเหตุ

- Services เหล่านี้ **ไม่จำเป็น** สำหรับ Pod GPU ที่ใช้ transcription service หลัก
- ใช้สำหรับทดสอบ RTMP streaming → HLS → Transcription → Close Caption เท่านั้น
- ถ้าไม่ต้องการใช้ สามารถลบ folder นี้ได้โดยไม่กระทบกับระบบหลัก

