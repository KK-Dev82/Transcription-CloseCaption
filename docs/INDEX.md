# 📚 Documentation Index

**อัพเดทล่าสุด**: 2024-12-19

เอกสารทั้งหมดถูกจัดหมวดหมู่ตามการใช้งานจริง

---

## 🔴 ESSENTIAL - จำเป็นต้องอ่าน (5 ไฟล์)

เอกสารที่ควรอ่านก่อนเริ่มใช้งาน:

1. **README.md** - เอกสารหลักของโปรเจค
2. **RESET_DATABASE.md** - วิธี reset database (ใช้เมื่อมีปัญหา)
3. **TROUBLESHOOTING.md** - แก้ไขปัญหาที่พบบ่อย
4. **CLEANUP_AND_SQLITE.md** - การจัดการ SQLite และ cleanup
5. **DASHBOARD_TABS_EXPLANATION.md** - คำอธิบาย Dashboard tabs

---

## 🟡 OPERATIONAL - สำหรับการใช้งานประจำ (8 ไฟล์)

เอกสารสำหรับการใช้งานประจำ:

### Database & Storage
- **SQLITE_MIGRATION.md** - Migration จาก JSON ไป SQLite
- **CLEANUP_AND_SQLITE.md** - Cleanup และ SQLite management

### Deployment & Setup
- **POD_DEPLOYMENT_CHECKLIST.md** - Checklist สำหรับ deploy บน Pod
- **STAGING_DEPLOYMENT_GUIDE.md** - Guide สำหรับ staging deployment
- **RUNPOD_SSH_SETUP.md** - Setup SSH สำหรับ RunPod

### Testing & Monitoring
- **TESTING_CHECKLIST.md** - Checklist สำหรับ testing
- **QUICK_TEST_GUIDE.md** - Quick test guide
- **TRANSCRIPTION_DIAGNOSTIC_GUIDE.md** - Diagnostic guide

---

## 🟢 REFERENCE - อ้างอิง (15 ไฟล์)

เอกสารสำหรับอ้างอิงเมื่อต้องการข้อมูลเฉพาะ:

### Architecture & Design
- **QUEUE_ARCHITECTURE_FINAL.md** - Queue architecture
- **WORKER_ARCHITECTURE_EXPLANATION.md** - Worker architecture
- **SIGNALR_WEBSOCKET_ARCHITECTURE.md** - SignalR/WebSocket architecture
- **STAGING_VPN_ARCHITECTURE.md** - VPN architecture

### Implementation Guides
- **PROGRESS_TRACKING_IMPLEMENTATION_SUMMARY.md** - Progress tracking
- **AUDIO_EXTRACTION_TIME_NULL_SUPPORT.md** - Audio extraction
- **VIDEO_WORKER_CONCURRENCY_CONFIG.md** - Video worker config

### Analysis & Planning
- **TRANSCRIPTION_METRICS_ANALYSIS.md** - Metrics analysis
- **STAGING_IMPROVEMENTS_PLAN.md** - Staging improvements
- **PRODUCTION_IMPROVEMENTS_PLAN.md** - Production improvements
- **SAAS_READINESS_ASSESSMENT.md** - SaaS readiness

### Performance
- **TRANSCRIPTION_PERFORMANCE_OPTIMIZATION.md** - Performance optimization
- **SEARCH_PERFORMANCE_ANALYSIS.md** - Search performance

---

## 🔵 ARCHIVE - เก็บไว้สำหรับอ้างอิง (30+ ไฟล์)

เอกสารเก่าที่เก็บไว้สำหรับอ้างอิง แต่ไม่จำเป็นต้องอ่าน:

### Historical/Completed Tasks
- **STUCK_TASKS_FIX.md** - แก้ไขปัญหา stuck tasks (เสร็จแล้ว)
- **WORKER_RABBITMQ_CONNECTION_FIX.md** - แก้ไข RabbitMQ connection (เสร็จแล้ว)
- **VIDEO_WORKER_CRASH_ANALYSIS.md** - Analysis worker crash (เสร็จแล้ว)
- **AIO_PIKA_MIGRATION_PLAN.md** - Migration plan (เสร็จแล้ว)

### Old Guides (อาจล้าสมัย)
- **RTX_4000_ADA_BENCHMARK_GUIDE.md** - Benchmark guide
- **RTX5080_SETUP_GUIDE.md** - Setup guide
- **GPU_BENCHMARK_SETUP_GUIDE.md** - GPU benchmark
- **GPU_PERFORMANCE_COMPARISON_PLAN.md** - GPU comparison

### Analysis Documents
- **TRANSCRIPTION_CHUNK_MAPPING_ANALYSIS.md** - Chunk mapping analysis
- **POSTGRESQL_STATUS_FIELDS_ANALYSIS.md** - PostgreSQL analysis
- **REDIS_ANALYSIS.md** - Redis analysis
- **AIO_PIKA_REDIS_STREAMS_ANALYSIS.md** - aio-pika analysis

### Implementation Plans (อาจเสร็จแล้ว)
- **MANDATORY_TRANSCRIPTION_STRATEGY.md** - Transcription strategy
- **DOCUMENT_MAPPING_IMPLEMENTATION_GUIDE.md** - Document mapping
- **INITIAL_PROMPT_USAGE_GUIDE.md** - Initial prompt guide

---

## 💡 คำแนะนำ

### สำหรับ Developer ใหม่
1. อ่าน **README.md** ก่อน
2. อ่าน **TROUBLESHOOTING.md** เมื่อมีปัญหา
3. อ่าน **DASHBOARD_TABS_EXPLANATION.md** เพื่อเข้าใจ Dashboard

### สำหรับ Deployment
1. อ่าน **POD_DEPLOYMENT_CHECKLIST.md**
2. อ่าน **STAGING_DEPLOYMENT_GUIDE.md**
3. อ่าน **RESET_DATABASE.md** เมื่อมีปัญหา database

### สำหรับ Troubleshooting
1. อ่าน **TROUBLESHOOTING.md** ก่อน
2. อ่าน **TRANSCRIPTION_DIAGNOSTIC_GUIDE.md**
3. ตรวจสอบ logs และ error messages

---

## 🗑️ เอกสารที่สามารถลบได้ (ถ้าต้องการ)

เอกสารเหล่านี้เป็น historical records ที่อาจไม่จำเป็น:

- ไฟล์ที่ขึ้นต้นด้วย `POD_*` (ยกเว้น POD_DEPLOYMENT_CHECKLIST.md)
- ไฟล์ที่ขึ้นต้นด้วย `STAGING_*` (ยกเว้น STAGING_DEPLOYMENT_GUIDE.md)
- ไฟล์ `*_ANALYSIS.md` ที่เป็น analysis เก่า
- ไฟล์ `*_PLAN.md` ที่เสร็จแล้ว

**หมายเหตุ**: ควรเก็บไว้ก่อนลบ เพื่ออ้างอิงในอนาคต

---

## 📝 การอัพเดท INDEX นี้

เมื่อเพิ่มเอกสารใหม่:
1. จัดหมวดหมู่ตามการใช้งาน
2. อัพเดทวันที่ "อัพเดทล่าสุด"
3. เพิ่มคำอธิบายสั้นๆ

