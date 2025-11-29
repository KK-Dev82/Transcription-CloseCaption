# 🔐 RunPod Registry Auth Setup Guide

คู่มือการตั้งค่า Registry Auth ใน RunPod สำหรับ ACR (Azure Container Registry)

---

## 📋 Overview

RunPod Registry Credential form มีแค่:
- **Credential Name** - ชื่อ credential (ตั้งชื่อเอง)
- **Username** - ACR username
- **Password** - ACR password

**หมายเหตุ:** Registry URL จะใช้จาก Container Image URL โดยอัตโนมัติ

---

## 🚀 Step-by-Step Setup

### Step 1: รัน Script เพื่อดึง ACR Credentials

**บน MacOS Localhost:**

```bash
# ไปที่ project directory
cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service

# รัน script
bash scripts/pod/get-acr-credentials.sh
```

**Script จะ:**
1. ตรวจสอบ Azure CLI
2. Login Azure (ถ้ายังไม่ login)
3. Enable Admin User (ถ้ายังไม่เปิด)
4. ดึง Username และ Password
5. แสดง credentials สำหรับใช้ใน RunPod

**Output ตัวอย่าง:**
```
🔐 Getting ACR Credentials for RunPod Registry Auth...

📋 ACR Name: kksenateacr

═══════════════════════════════════════════════════════════════
Option 1: Admin Credentials (ง่ายที่สุด)
═══════════════════════════════════════════════════════════════

🔧 Enabling Admin User...
✅ Username: kksenateacr
✅ Password: Abc123XyzPasswordHere456

📝 ใช้ใน RunPod Template:
   Registry URL: kksenateacr.azurecr.io
   Username: kksenateacr
   Password: Abc123XyzPasswordHere456
```

---

### Step 2: สร้าง Registry Credential ใน RunPod

1. **ไปที่ RunPod Template ที่กำลังสร้าง**
   - ไปที่ **"Templates"** → **"Create New Template"** หรือแก้ไข Template ที่มีอยู่

2. **คลิก "+ Select Registry Auth"**
   - อยู่ใต้ Container Image field

3. **คลิก "Create New"**
   - จะเปิด modal "Create Registry Credential"

4. **กรอกข้อมูลใน Modal:**

   | Field | Value | หมายเหตุ |
   |-------|-------|----------|
   | **Credential Name** | `ACR-KKSenate` (หรือชื่ออื่น) | ตั้งชื่อเอง |
   | **Username** | `kksenateacr` | จาก script output |
   | **Password** | `<password>` | จาก script output |

5. **คลิก "Save"**

---

### Step 3: ตั้งค่า Container Image

**ใน Template Configuration:**

**Container Image:**
```
kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

**หมายเหตุ:** 
- Registry URL (`kksenateacr.azurecr.io`) จะถูกใช้โดยอัตโนมัติ
- RunPod จะใช้ Registry Credential ที่สร้างไว้ (จาก Credential Name) เพื่อ authenticate

---

### Step 4: ตรวจสอบ

1. **Save Template**
2. **Deploy Pod จาก Template**
3. **ตรวจสอบว่า Pod pull image ได้:**
   - ดู logs ใน RunPod Console
   - ควรไม่มี error "unauthorized"

---

## 🔧 Troubleshooting

### Issue 1: Script ไม่พบ Azure CLI

**อาการ:**
```
❌ Azure CLI not found
```

**แก้ไข:**
```bash
# ติดตั้ง Azure CLI (MacOS)
brew install azure-cli

# หรือ (Linux)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

---

### Issue 2: Script ไม่สามารถ Login Azure

**อาการ:**
```
Error: Please run 'az login' to setup account
```

**แก้ไข:**
```bash
# Login Azure
az login

# เลือก subscription (ถ้ามีหลายตัว)
az account set --subscription <subscription-id>
```

---

### Issue 3: ยังมี Error "unauthorized"

**อาการ:**
```
error creating container: unauthorized
```

**แก้ไข:**

1. **ตรวจสอบว่า Registry Credential ถูกเลือก:**
   - ไปที่ Template → Registry Auth
   - ตรวจสอบว่าเลือก Credential ที่สร้างไว้แล้ว

2. **ตรวจสอบ Username/Password:**
   ```bash
   # ทดสอบ login
   docker login kksenateacr.azurecr.io -u <username> -p <password>
   
   # ถ้า login สำเร็จ แสดงว่า credentials ถูกต้อง
   ```

3. **ตรวจสอบว่า Image มีอยู่จริง:**
   ```bash
   az acr repository show-tags --name kksenateacr --repository kk-transcription-runpod-base
   ```

4. **ตรวจสอบว่า Admin User เปิดอยู่:**
   ```bash
   az acr show --name kksenateacr --query adminUserEnabled
   # ควรเป็น: true
   ```

---

## 📝 Quick Reference

### รัน Script

```bash
# บน MacOS
cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service
bash scripts/pod/get-acr-credentials.sh
```

### ข้อมูลที่ต้องใช้ใน RunPod

| Field | Value |
|-------|-------|
| **Credential Name** | `ACR-KKSenate` (ตั้งชื่อเอง) |
| **Username** | `kksenateacr` (จาก script) |
| **Password** | `<password>` (จาก script) |

### Container Image

```
kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

---

## 🔗 Related Documents

- **Custom Template Configuration:** [CUSTOM_TEMPLATE_CONFIGURATION.md](./CUSTOM_TEMPLATE_CONFIGURATION.md)
- **Pod Scripts:** [scripts/pod/README.md](../../scripts/pod/README.md)

---

**Last Updated:** 2024-12-19

