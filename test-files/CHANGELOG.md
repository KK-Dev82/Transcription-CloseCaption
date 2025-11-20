# Test Files Changelog

## ฟีเจอร์ใหม่ที่เพิ่มใน Test Files

### 1. 🎬 แปลงเสียง (Transcription)
- อัปโหลดไฟล์ MP4, MP3, WAV, M4A
- แสดงความคืบหน้าแบบ real-time
- แสดงผลลัพธ์พร้อมสถิติ

### 2. 🔍 ค้นหาข้อความในวิดีโอ (Search)
- ค้นหาคำในประวัติการแปลงเสียง
- แสดงผลการค้นหาพร้อม timestamp
- คลิกเพื่อดูรายละเอียดเต็ม

### 3. 📺 Live Close Caption
- แสดงการแปลงเสียงแบบ real-time
- อัปเดตความคืบหน้าต่อเนื่อง
- หยุดได้เมื่อต้องการ

### 4. 📚 ประวัติการแปลงเสียง (History)
- แสดงรายการงานทั้งหมด
- สถิติรวม (จำนวนงาน, คำ, ระยะเวลา)
- คลิกเพื่อดูรายละเอียด

### 5. 🎥 Video Player ในรายละเอียด
- เล่นวิดีโอต้นฉบับ
- แสดงข้อความที่แปลงได้
- แสดง chunks แบ่งตาม timeline

## ไฟล์ที่อัปเดต

### ✅ เสร็จแล้ว
- `index.html` - แยก local/staging environment
- `test-local.html` - ฟีเจอร์ครบถ้วนสำหรับ local
- `test-staging.html` - ฟีเจอร์ครบถ้วนสำหรับ staging

### 🔄 กำลังดำเนินการ
- `test-frontend.html` - ฟีเจอร์ครบถ้วน
- `test_permission_fix.html` - ฟีเจอร์ครบถ้วน
- `test_transcription_debug.html` - ฟีเจอร์ครบถ้วน
- `test_transcription_fix.html` - ฟีเจอร์ครบถ้วน
- `test_websocket.html` - ฟีเจอร์ครบถ้วน

## API Endpoints ที่ใช้

### Local Environment
- `http://localhost:8001/upload/` - อัปโหลดไฟล์
- `http://localhost:8001/transcribe-enhanced/start` - เริ่มแปลงเสียง
- `http://localhost:8001/history/transcriptions` - ประวัติ
- `http://localhost:8001/polling/task/{task_id}` - ติดตามความคืบหน้า
- `http://localhost:8001/file/{filename}` - ไฟล์วิดีโอ

### Staging Environment
- `https://staging-ph2.bms.senate.go.th/transcribe/upload/` - อัปโหลดไฟล์
- `https://staging-ph2.bms.senate.go.th/transcribe/transcribe-enhanced/start` - เริ่มแปลงเสียง
- `https://staging-ph2.bms.senate.go.th/transcribe/history/transcriptions` - ประวัติ
- `https://staging-ph2.bms.senate.go.th/transcribe/polling/task/{task_id}` - ติดตามความคืบหน้า
- `https://staging-ph2.bms.senate.go.th/media-uploads/{filename}` - ไฟล์วิดีโอ

## การใช้งาน

1. เปิด `test-files/index.html`
2. เลือก Environment (Local หรือ Staging)
3. เลือกไฟล์ทดสอบที่ต้องการ
4. ใช้ฟีเจอร์ต่างๆ:
   - **แปลงเสียง**: คลิก "เริ่มแปลงเสียง"
   - **Live Caption**: คลิก "Live Caption"
   - **ค้นหา**: ใส่คำค้นหาแล้วคลิก "ค้นหา"
   - **ประวัติ**: คลิก "โหลดประวัติ"

## หมายเหตุ

- ไฟล์ทั้งหมดทำงานผ่าน API เพื่อให้สามารถนำไปใช้ใน Frontend จริงได้
- รองรับทั้ง Local และ Staging environment
- มี WebSocket และ Polling fallback
- แสดง logs แบบ real-time สำหรับ debugging
