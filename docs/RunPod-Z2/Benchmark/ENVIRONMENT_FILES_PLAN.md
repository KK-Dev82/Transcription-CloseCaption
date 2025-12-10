# 📋 แผนการจัดการไฟล์ Environment Variables

**วันที่**: 2025-12-10  
**ปัญหา**: ใน server มีทั้ง `.env.runpod` และ `env.runpod` ทำให้เกิดความสับสน

---

## 🔍 สถานะปัจจุบัน

### ไฟล์ที่มีใน Server:
1. **`.env.runpod`** (มี dot) - ใช้โดย scripts
2. **`env.runpod`** (ไม่มี dot) - ไฟล์ source ใน repo

### Scripts ที่ใช้:
- `scripts/pod/start-service-daemon.sh` → `source .env.runpod`
- `scripts/pod/check-pod.sh` → `source .env.runpod`
- `scripts/pod/setup-pod.sh` → สร้าง `.env.runpod`
- และอื่นๆ → ใช้ `.env.runpod` ทั้งหมด

---

## ✅ แผนการแก้ไข

### Option 1: ใช้ `env.runpod` เป็นหลัก (แนะนำ)

**ข้อดี:**
- แก้ไขได้ง่ายใน repo (ไม่ต้องแก้ dot file)
- Git สามารถ track ได้
- ไม่ต้อง sync ไฟล์

**การแก้ไข:**
1. แก้ไข scripts ให้ใช้ `env.runpod` แทน `.env.runpod`
2. หรือสร้าง symlink: `ln -s env.runpod .env.runpod`

### Option 2: Sync `env.runpod` → `.env.runpod`

**ข้อดี:**
- ไม่ต้องแก้ scripts
- ใช้ไฟล์เดิมที่ scripts รู้จัก

**การแก้ไข:**
1. สร้าง script `sync-env.sh` เพื่อ copy `env.runpod` → `.env.runpod`
2. รัน script ก่อน restart service

---

## 📝 แนะนำ: ใช้ Option 1 (Symlink)

**ขั้นตอน:**
1. บน server: `ln -sf env.runpod .env.runpod`
2. ตรวจสอบ: `ls -la | grep env.runpod`
3. Restart service

**ข้อดี:**
- ไม่ต้องแก้ scripts
- แก้ไข `env.runpod` ใน repo แล้ว sync ไป `.env.runpod` อัตโนมัติ
- Git track `env.runpod` ได้

---

## 🚀 การใช้งาน

### แก้ไข Configuration:
1. แก้ไขไฟล์ `env.runpod` ใน repo
2. Commit & Push
3. Pull บน server
4. Restart service (จะใช้ `.env.runpod` ซึ่งเป็น symlink ไปยัง `env.runpod`)

---

## ✅ Checklist

- [ ] สร้าง symlink บน 4080s: `ln -sf env.runpod .env.runpod`
- [ ] สร้าง symlink บน 4000-ada: `ln -sf env.runpod .env.runpod`
- [ ] ตรวจสอบว่า symlink ทำงาน: `ls -la | grep env.runpod`
- [ ] Restart workers บนทั้ง 2 servers
- [ ] ตรวจสอบว่าใช้ prefetch_count=1 แล้ว
- [ ] ทดสอบ 10 tasks บนทั้ง 2 servers

---

## 🔗 Related Files

- `env.runpod`: ไฟล์ source ใน repo
- `.env.runpod`: Symlink ไปยัง `env.runpod` (บน server)
- `scripts/pod/start-service-daemon.sh`: Load `.env.runpod`

