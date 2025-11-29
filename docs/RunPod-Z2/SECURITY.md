# 🔒 Security Considerations - Direct Mode vs Docker Image

คำถาม: **Direct Mode vs Docker Image มีปัญหา Source Code Leak ไหม?**

---

## 📋 คำตอบสั้นๆ

### Direct Mode (ปัจจุบัน)
⚠️ **มี Source Code ใน Container/VM**

**ความเสี่ยง:**
- Source code อยู่ใน filesystem ของ container/VM
- ถ้ามีคน SSH เข้าได้ → เห็น source code ทั้งหมด
- ถ้า container/VM ถูก compromise → source code ถูก expose

### Docker Image (Build)
✅ **Source Code ถูก build เป็น image**

**ความปลอดภัย:**
- Source code ถูก compile/build เป็น binary หรือ bytecode
- แต่อย่างไรก็ตาม Python code ยังอยู่ใน image (ไม่ใช่ binary)
- ต้องใช้ obfuscation หรือ compile เป็น binary (เช่น PyInstaller) เพื่อซ่อน source code

---

## 🔍 เปรียบเทียบความเสี่ยง

| Aspect | Direct Mode | Docker Image (Build) |
|--------|-------------|---------------------|
| **Source Code Visibility** | ⚠️ เห็นได้ชัดเจน | ⚠️ เห็นได้ (Python ไม่ compile) |
| **SSH Access** | ⚠️ เห็น source code | ✅ ไม่เห็น (ถ้าไม่ mount volume) |
| **Container Compromise** | ⚠️ Source code expose | ⚠️ Source code expose |
| **Image Inspection** | N/A | ⚠️ สามารถ inspect image ได้ |

---

## 🛡️ วิธีลดความเสี่ยง

### 1. Access Control

**RunPod:**
- ✅ ใช้ SSH key authentication
- ✅ จำกัด IP ที่สามารถ SSH ได้
- ✅ ใช้ strong passwords
- ✅ หมุนเวียน credentials เป็นประจำ

**Z2 (On-Premise):**
- ✅ ใช้ firewall จำกัด SSH access
- ✅ ใช้ SSH key authentication
- ✅ Disable password authentication
- ✅ ใช้ VPN สำหรับ remote access

### 2. Network Security

**RunPod:**
- ✅ ใช้ HTTPS สำหรับ API endpoints
- ✅ ใช้ firewall rules จำกัด ports
- ✅ ใช้ VPN (ถ้าจำเป็น)

**Z2:**
- ✅ ใช้ internal network (ไม่ expose ไป internet)
- ✅ ใช้ firewall rules
- ✅ ใช้ VPN สำหรับ remote access

### 3. Code Protection

**Option 1: Obfuscation (Python)**
```bash
# ใช้ pyarmor หรือ tools อื่นๆ
pip install pyarmor
pyarmor gen app/
```

**Option 2: Compile to Binary**
```bash
# ใช้ PyInstaller
pip install pyinstaller
pyinstaller --onefile app/main.py
```

**Option 3: Docker Image (Build)**
```bash
# Build image และไม่ mount source code
docker build -t transcription-service .
docker run -d transcription-service
```

---

## 🔐 Best Practices

### สำหรับ Development (ยอมรับได้)

**Direct Mode:**
- ✅ ใช้ได้สำหรับ development/testing
- ✅ ง่ายต่อการ debug
- ⚠️ ระวังเรื่อง access control

**Recommendations:**
- ใช้ SSH key authentication
- จำกัด IP ที่สามารถ SSH ได้
- ใช้ strong passwords
- หมุนเวียน credentials เป็นประจำ

### สำหรับ Production (แนะนำ)

**Docker Image (Build):**
- ✅ Source code ถูก build เป็น image
- ✅ ไม่ต้อง mount source code
- ✅ ง่ายต่อการ deploy
- ⚠️ ยังเห็น Python code ได้ (ต้องใช้ obfuscation)

**Recommendations:**
- Build Docker image และ push ไป registry
- Deploy โดยไม่ mount source code
- ใช้ secrets management สำหรับ sensitive data
- ใช้ HTTPS สำหรับ API endpoints
- ใช้ firewall rules จำกัด access

---

## 📝 สรุป

### Direct Mode (Development)

**ข้อดี:**
- ✅ ง่ายต่อการ debug
- ✅ ง่ายต่อการ update code
- ✅ ไม่ต้อง build image

**ข้อเสีย:**
- ⚠️ Source code อยู่ใน container/VM
- ⚠️ ถ้ามีคน SSH เข้าได้ → เห็น source code

**เหมาะสำหรับ:**
- Development
- Testing
- Staging (ถ้ามี access control ดี)

### Docker Image (Production)

**ข้อดี:**
- ✅ Source code ถูก build เป็น image
- ✅ ไม่ต้อง mount source code
- ✅ ง่ายต่อการ deploy

**ข้อเสีย:**
- ⚠️ ยังเห็น Python code ได้ (ต้องใช้ obfuscation)
- ⚠️ ต้อง build image เมื่อ code เปลี่ยน

**เหมาะสำหรับ:**
- Production
- Environments ที่ต้องการความปลอดภัยสูง

---

## 🔗 Related Documents

- **Build vs Direct Mode:** [BUILD_VS_DIRECT_MODE.md](./BUILD_VS_DIRECT_MODE.md)
- **FAQ:** [FAQ.md](./FAQ.md)

---

**Last Updated:** 2024-12-19

