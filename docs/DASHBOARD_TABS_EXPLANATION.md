# 📊 Dashboard Tabs Explanation

## ความแตกต่างระหว่าง Tabs

### 1. 📊 Overview Tab
**วัตถุประสงค์:** ดูและจัดการ Tasks ทั้งหมด

**Features:**
- แสดง Tasks ในรูปแบบ **Table** (50 tasks per page)
- **Pagination** สำหรับดู tasks มากๆ
- Filter ตาม Status (All, Pending, Processing, Completed, Failed, Stopped)
- Actions: View transcription, Stop task
- Real-time progress tracking สำหรับ tasks ที่กำลัง process

**ใช้เมื่อ:**
- ต้องการดู tasks ทั้งหมด
- ต้องการจัดการ tasks (stop, clear, delete)
- ต้องการดู transcription results

---

### 2. 📡 Monitoring & Logs Tab
**วัตถุประสงค์:** Monitor ระบบแบบ Real-time

**Features:**
- **Real-time Task Progress:** แสดง tasks ที่กำลัง process พร้อม progress bar
- **System Logs:** แสดง logs อัตโนมัติ (auto-scroll)
- **Server Status:** แสดงสถานะของแต่ละ server (Total, Completed, Processing, Pending, Failed)
- Auto-refresh ทุก 5 วินาที

**ใช้เมื่อ:**
- ต้องการ monitor ระบบแบบ real-time
- ต้องการดู logs
- ต้องการดูสถานะ server

**ความแตกต่างจาก Monitor & Analysis:**
- ✅ **Real-time monitoring** (ไม่ต้องใส่ Batch ID)
- ✅ **System-wide view** (ดูทุก server พร้อมกัน)
- ✅ **Auto-refresh** (อัปเดตอัตโนมัติ)
- ❌ ไม่มีการวิเคราะห์ผลลัพธ์

---

### 3. 📈 Monitor & Analysis Tab
**วัตถุประสงค์:** ติดตามและวิเคราะห์ Transcription Jobs เฉพาะเจาะจง

**Features:**
- ต้องใส่ **Batch ID** หรือ **Task IDs** เพื่อ monitor
- **Progress Tracking:** ติดตาม progress ของ jobs ที่ระบุ
- **Analysis Results:** วิเคราะห์ผลลัพธ์ (average time, success rate, etc.)
- **Export JSON:** Export ผลลัพธ์เป็น JSON
- **Previous Results:** ดูผลลัพธ์ที่บันทึกไว้ก่อนหน้า

**ใช้เมื่อ:**
- ต้องการ monitor **specific batch** หรือ **specific tasks**
- ต้องการ **วิเคราะห์ผลลัพธ์** (performance, accuracy, etc.)
- ต้องการ **export results** เป็น JSON

**ความแตกต่างจาก Monitoring & Logs:**
- ✅ **Targeted monitoring** (ต้องระบุ Batch ID หรือ Task IDs)
- ✅ **Analysis & Reporting** (มี analysis results)
- ✅ **Export functionality** (export JSON)
- ❌ ไม่ auto-refresh (ต้อง start monitoring เอง)
- ❌ ไม่แสดง system logs

---

## สรุปเปรียบเทียบ

| Feature | Overview | Monitoring & Logs | Monitor & Analysis |
|---------|----------|-------------------|-------------------|
| **View Tasks** | ✅ Table (50/page) | ✅ Active tasks only | ✅ Specific tasks |
| **Real-time Updates** | ✅ (processing tasks) | ✅ (ทุก 5 วินาที) | ⚠️ (เมื่อ start monitoring) |
| **System Logs** | ❌ | ✅ | ❌ |
| **Server Status** | ❌ | ✅ | ❌ |
| **Progress Tracking** | ✅ | ✅ | ✅ |
| **Analysis** | ❌ | ❌ | ✅ |
| **Export Results** | ❌ | ❌ | ✅ |
| **Batch ID Required** | ❌ | ❌ | ✅ |
| **Auto-refresh** | ✅ (10 วินาที) | ✅ (5 วินาที) | ⚠️ (เมื่อ start) |

---

## คำแนะนำการใช้งาน

### สำหรับ Admin ทั่วไป
1. **Overview Tab** → ดูและจัดการ tasks
2. **Monitoring & Logs Tab** → Monitor ระบบ real-time

### สำหรับ Performance Analysis
1. **Test Tab** → ส่ง test jobs
2. **Monitor & Analysis Tab** → Monitor และวิเคราะห์ผลลัพธ์

### สำหรับ Troubleshooting
1. **Monitoring & Logs Tab** → ดู logs และ server status
2. **Overview Tab** → ดู tasks ที่มีปัญหา

---

*Last Updated: 2025-12-14*

