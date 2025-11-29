# 🎯 RunPod Custom Template Configuration

คู่มือการสร้าง Custom Template ใน RunPod โดยใช้ Custom Base Image

---

## 📋 Overview

หลังจาก Build และ Push Custom Base Image ไป ACR แล้ว คุณสามารถสร้าง Custom Template ใน RunPod เพื่อใช้งานได้ง่ายขึ้น

**Image URL:**
```
kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

---

## 🚀 Step-by-Step: สร้าง Custom Template

### Step 1: เข้า RunPod Console

1. เข้า [RunPod Console](https://www.runpod.io/console/pods)
2. ไปที่ **"Templates"** → **"Create New Template"**

---

### Step 2: ตั้งค่า General Tab

#### Type
- **เลือก:** `Pod` (ไม่ใช่ Serverless)
- **เหตุผล:** ต้องการ persistent environment และ SSH access

#### Compute Type
- **เลือก:** `Nvidia GPU`
- **เหตุผล:** ใช้ GPU สำหรับ Whisper transcription

---

### Step 3: Container Image

**Container Image:**
```
kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

**หรือถ้าใช้ Public Registry:**
```
docker.io/your-username/kk-transcription-runpod-base:latest
```

**หมายเหตุ:**
- ถ้าใช้ Private Registry (ACR) ต้องตั้งค่า **Registry Auth** (ดูด้านล่าง)
- Image นี้มี CUDA + Docker + Azure CLI + Setup Scripts พร้อมแล้ว

---

### Step 4: Registry Auth (⚠️ จำเป็น - ถ้าใช้ ACR)

**⚠️ สำคัญ:** ACR เป็น Private Registry ต้องตั้งค่า Registry Auth ก่อน RunPod จะ pull image ได้

**ดูรายละเอียด:** [RUNPOD_REGISTRY_AUTH_SETUP.md](./RUNPOD_REGISTRY_AUTH_SETUP.md) ⭐

#### Quick Steps:

1. **รัน Script เพื่อดึง ACR Credentials:**
   ```bash
   # บน MacOS
   cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service
   bash scripts/pod/get-acr-credentials.sh
   ```

2. **สร้าง Registry Credential ใน RunPod:**
   - คลิก **"+ Select Registry Auth"** → **"Create New"**
   - **Credential Name:** `ACR-KKSenate` (ตั้งชื่อเอง)
   - **Username:** `<จาก script>` (ปกติคือ `kksenateacr`)
   - **Password:** `<จาก script>`
   - คลิก **"Save"**

**หมายเหตุ:** 
- Registry URL จะใช้จาก Container Image URL โดยอัตโนมัติ (`kksenateacr.azurecr.io`)
- RunPod จะ match Registry URL กับ Credential ที่สร้างไว้

#### Option 2: ใช้ Service Principal (Production - แนะนำ)

1. **สร้าง Service Principal:**
   ```bash
   # Get Subscription ID
   SUBSCRIPTION_ID=$(az account show --query id -o tsv)
   
   # Get Resource Group
   RESOURCE_GROUP=$(az acr show --name kksenateacr --query resourceGroup -o tsv)
   
   # Get ACR Resource ID
   ACR_ID=$(az acr show --name kksenateacr --query id -o tsv)
   
   # สร้าง Service Principal
   az ad sp create-for-rbac \
     --name "runpod-transcription-deployer" \
     --role AcrPull \
     --scopes $ACR_ID
   ```

2. **Output จะเป็น:**
   ```json
   {
     "appId": "12345678-1234-1234-1234-123456789abc",
     "password": "AbCdEf~GhIjKl123456",
     "tenant": "87654321-4321-4321-4321-cba987654321"
   }
   ```

3. **ตั้งค่าใน RunPod Template:**
   - **Registry URL:** `kksenateacr.azurecr.io`
   - **Username:** `<appId>` (จาก output ด้านบน)
   - **Password:** `<password>` (จาก output ด้านบน)

**หมายเหตุ:** Service Principal ปลอดภัยกว่า Admin Credentials เพราะมีสิทธิ์แค่ Pull (AcrPull) ไม่สามารถ Push หรือ Delete ได้

---

### Step 5: Container Disk

**แนะนำ: 50 GB**

**เหตุผล:**
- Docker images: ~5-10GB
- Models: ~3-5GB
- Temporary files: ~10-20GB
- Working space: ~10-20GB

**Minimum:** 30GB  
**Recommended:** 50GB  
**For large models:** 100GB

---

### Step 6: Volume Disk (Optional)

**แนะนำ: 20-50 GB**

**เหตุผล:**
- Models จะถูกเก็บใน `/workspace/models`
- Volume จะไม่ถูกลบเมื่อ Pod ถูก terminate
- ช่วยลดเวลา download models เมื่อ restart Pod

**หมายเหตุ:** ถ้าไม่ใช้ Volume, models จะถูก download ใหม่ทุกครั้งที่ build image

---

### Step 7: Volume Mount Path

**ค่า:**
```
/workspace
```

**Default:** `/workspace` (ไม่ต้องเปลี่ยน)

---

### Step 8: Expose HTTP Ports

**Ports:**
```
8001,8002
```

**หรือถ้าต้องการ Jupyter (optional):**
```
8888,8001,8002
```

**Ports:**
- `8001` - Transcription API (จำเป็น)
- `8002` - Whisper Service (จำเป็น)
- `8888` - Jupyter/Development (optional)

**หมายเหตุ:** RunPod จำกัด HTTP ports สูงสุด 10 ports

---

### Step 9: Expose TCP Ports

**Ports:**
```
22
```

**Ports:**
- `22` - SSH (จำเป็น)

**⚠️ สำคัญ:** 
- Port `8001, 8002` ไม่ต้องใส่ใน TCP Ports (ใช้ HTTP Ports แทน)
- ถ้ามี error "Exposed ports cannot be same" ให้ใช้แค่ `22` เท่านั้น

---

### Step 10: Start Command (Optional)

**ถ้าต้องการ override default command:**

```
/workspace/start-services.sh
```

**หมายเหตุ:** Custom Base Image มี default command อยู่แล้ว (`CMD ["/workspace/start-services.sh"]`) แต่ถ้าต้องการ override สามารถใส่ได้

---

### Step 11: Environment Variables (Optional)

**สำหรับ Local Testing (MacOS → RunPod):**

| Key | Value | Notes |
|-----|-------|-------|
| `RABBITMQ_HOST` | `localhost` | ใช้ผ่าน SSH Tunnel |
| `RABBITMQ_PORT` | `5672` | RabbitMQ port |
| `RABBITMQ_USER` | `senate` | RabbitMQ username |
| `RABBITMQ_PASSWORD` | `qP2VtHz6fAX4xDksEpMrLT` | RabbitMQ password |
| `REDIS_URL` | `redis://redis:6379` | ใช้ local container |
| `WHISPER_PROVIDER` | `builtin` | Default: builtin |
| `WHISPER_FALLBACK_ENABLED` | `false` | Disable fallback |
| `GROQ_API_KEY` | `<your-key>` | Optional - for Groq fallback |

**สำหรับ Staging:**

| Key | Value | Notes |
|-----|-------|-------|
| `RABBITMQ_HOST` | `10.200.22.61` | Backend server IP |
| `RABBITMQ_PORT` | `5672` | RabbitMQ port |
| `RABBITMQ_USER` | `senate` | RabbitMQ username |
| `RABBITMQ_PASSWORD` | `qP2VtHz6fAX4xDksEpMrLT` | RabbitMQ password |
| `REDIS_URL` | `redis://10.200.22.61:6379` | Backend Redis (หรือใช้ local container) |
| `WHISPER_PROVIDER` | `builtin` | Default: builtin |

**หมายเหตุ:** Environment Variables เหล่านี้จะถูก override โดย `.env.runpod` เมื่อรัน docker-compose

---

### Step 12: README Tab (Optional)

**เพิ่ม README สำหรับ Template:**

```markdown
# Transcription Service Custom Template

Custom Base Image สำหรับ Transcription Service บน RunPod

## Features

- ✅ CUDA 12.1.0 (libraries)
- ✅ Docker + Docker Compose
- ✅ Azure CLI
- ✅ Setup Scripts พร้อมใช้งาน

## Quick Start

1. Deploy Pod จาก Template นี้
2. SSH เข้า Pod
3. Clone repository: `git clone <repo-url> /workspace/transcription-service`
4. Services จะ start อัตโนมัติ

## Ports

- `8001` - Transcription API
- `8002` - Whisper Service
- `22` - SSH

## Environment Variables

ดูใน General Tab สำหรับ Environment Variables ที่แนะนำ
```

---

## 📝 สรุป Configuration

### Required Settings

| Setting | Value |
|---------|-------|
| **Type** | `Pod` |
| **Compute Type** | `Nvidia GPU` |
| **Container Image** | `kksenateacr.azurecr.io/kk-transcription-runpod-base:latest` |
| **Container Disk** | `50 GB` |
| **Volume Disk** | `20 GB` (optional) |
| **Volume Mount Path** | `/workspace` |
| **HTTP Ports** | `8001,8002` |
| **TCP Ports** | `22` |

### Optional Settings

| Setting | Value | Notes |
|---------|-------|-------|
| **Registry Auth** | ACR credentials | ถ้าใช้ Private Registry |
| **Start Command** | `/workspace/start-services.sh` | Override default command |
| **Environment Variables** | ดูด้านบน | สำหรับ configuration |

---

## 🚀 หลังจากสร้าง Template

### Step 1: Deploy Pod จาก Template

1. ไปที่ **"Pods"** → **"Deploy"**
2. เลือก **Custom Template** ที่เพิ่งสร้าง
3. เลือก GPU: **RTX 4080** (แนะนำ) หรือ RTX 4070/4090
4. คลิก **"Deploy"**

### Step 2: SSH เข้า Pod

```bash
ssh root@<runpod-ip> -p <port>
```

### Step 3: Clone Repository

```bash
cd /workspace
git clone <repo-url> transcription-service
```

**หมายเหตุ:** Custom Base Image จะ start services อัตโนมัติเมื่อ container เริ่มทำงาน

### Step 4: ตรวจสอบ Services

```bash
# ตรวจสอบ Docker containers
docker ps

# ตรวจสอบ API health
curl http://localhost:8001/health

# ตรวจสอบ Whisper health
curl http://localhost:8002/health

# ตรวจสอบ GPU
nvidia-smi
```

---

## 🔧 Troubleshooting

### Issue 1: Cannot Pull Image from ACR (UNAUTHORIZED)

**อาการ:**
```
error creating container: unauthorized: authentication required
```

**สาเหตุ:**
- ACR เป็น Private Registry ต้องตั้งค่า Registry Auth
- RunPod ไม่สามารถ pull image โดยไม่มี credentials

**แก้ไข:**

1. **ดึง ACR Credentials:**
   ```bash
   bash scripts/pod/get-acr-credentials.sh
   ```

2. **ตั้งค่า Registry Auth ใน RunPod Template:**
   - ไปที่ Template → Registry Auth
   - ใส่ Registry URL, Username, Password

3. **ตรวจสอบว่า Image มีอยู่จริง:**
   ```bash
   az acr repository show-tags --name kksenateacr --repository kk-transcription-runpod-base
   ```

4. **ทดสอบ Login:**
   ```bash
   docker login kksenateacr.azurecr.io -u <username> -p <password>
   docker pull kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
   ```

---

### Issue 2: Services Not Starting

**อาการ:**
```
Services ไม่ start อัตโนมัติ
```

**แก้ไข:**
- ตรวจสอบ logs: `docker logs <container-name>`
- ตรวจสอบว่า repository cloned แล้ว: `ls -la /workspace/transcription-service`
- ตรวจสอบ environment variables

---

### Issue 3: Ports Not Accessible

**อาการ:**
```
Connection refused
```

**แก้ไข:**
- ตรวจสอบว่า expose ports ใน Template
- ตรวจสอบว่า services รันอยู่: `docker ps`
- ตรวจสอบ firewall rules

---

## 🔗 Related Documents

- **Custom Base Image:** [CUSTOM_BASE_IMAGE.md](./CUSTOM_BASE_IMAGE.md)
- **RunPod Setup:** [INSTALLATION_STEPS.md](./INSTALLATION_STEPS.md)
- **Local Testing:** [LOCAL_TESTING.md](./LOCAL_TESTING.md)

---

**Last Updated:** 2024-12-19

