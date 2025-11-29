# 📁 Staging Scripts

Scripts สำหรับการ Build, Deploy และ Monitor บน Staging Environment

## 📋 Scripts

### `build-and-push-acr.sh`
**Build และ Push images ไป Azure Container Registry (ACR)**
- Build Main API image
- Build Whisper service images (ARM64, Linux)
- Push images ไป ACR
- Tag images ด้วย version

**Usage:**
```bash
bash scripts/staging/build-and-push-acr.sh
```

**Prerequisites:**
- Azure CLI installed
- Login ACR: `az acr login --name kksenateacr`

---

### `build-staging.sh`
**Build images สำหรับ Staging**
- Build images พร้อม staging tags
- ใช้สำหรับ build ก่อน deploy

**Usage:**
```bash
bash scripts/staging/build-staging.sh
```

---

### `deploy-staging.sh`
**Deploy services ไป Staging Server**
- Pull images จาก ACR
- Deploy services ด้วย docker-compose.staging.yml
- ตรวจสอบ health checks

**Usage:**
```bash
bash scripts/staging/deploy-staging.sh
```

**Prerequisites:**
- SSH access ไป staging server
- ACR credentials configured

---

### `check-staging-resources.sh`
**ตรวจสอบ Resources บน Staging Server**
- ตรวจสอบ Docker containers
- ตรวจสอบ Disk space
- ตรวจสอบ Memory usage
- ตรวจสอบ Network connectivity
- ตรวจสอบ Service health

**Usage:**
```bash
bash scripts/staging/check-staging-resources.sh
```

---

### `staging-deployment-checklist.md`
**Checklist สำหรับการ Deploy ไป Staging**
- Pre-deployment checks
- Deployment steps
- Post-deployment verification

**Usage:**
- อ่านและทำตาม checklist ก่อน deploy

---

## 🔗 Related Files

- `docker-compose.staging.yml` - Docker Compose สำหรับ staging
- `.env.staging` - Environment variables สำหรับ staging

---

## 📝 Deployment Workflow

1. **Build และ Push Images:**
   ```bash
   bash scripts/staging/build-and-push-acr.sh
   ```

2. **Deploy ไป Staging:**
   ```bash
   bash scripts/staging/deploy-staging.sh
   ```

3. **ตรวจสอบ Resources:**
   ```bash
   bash scripts/staging/check-staging-resources.sh
   ```

