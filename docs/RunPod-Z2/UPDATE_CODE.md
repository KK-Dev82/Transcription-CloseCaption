# 🔄 การอัปเดต Code บน RunPod Pod Server

คู่มือการอัปเดต code บน RunPod Pod Container หลังจากมีการแก้ไขไฟล์

---

## 📋 Overview

เมื่อมีการอัปเดต code (เช่น แก้ไข `start-services-direct.sh`, `requirements.txt`, หรือ code อื่นๆ) บน Pod Server มี **2 วิธีหลัก**:

1. **Git Pull** (แนะนำ) - อัปเดต code โดยไม่ต้อง clone ใหม่
2. **Clone ใหม่** - ลบและ clone repository ใหม่ (ใช้เมื่อมีปัญหา)

---

## 🚀 วิธีที่ 1: Git Pull (แนะนำ)

### ขั้นตอน

```bash
# 1. เข้าไปที่ repository directory
cd /workspace/transcription-service

# 2. ตรวจสอบ branch ปัจจุบัน
git branch

# 3. Pull latest changes
git pull origin <branch-name>

# ตัวอย่าง: ถ้าใช้ staging branch
git pull origin staging

# หรือถ้าใช้ main branch
git pull origin main
```

### ตัวอย่างการใช้งาน

```bash
# SSH เข้า Pod
ssh root@<runpod-ip> -p <port>

# ไปที่ repository
cd /workspace/transcription-service

# ตรวจสอบ branch
git branch
# Output: * staging

# Pull latest changes
git pull origin staging

# ตรวจสอบว่ามีการเปลี่ยนแปลง
git log --oneline -5
```

---

## 🔄 วิธีที่ 2: Clone ใหม่ (เมื่อมีปัญหา)

### ขั้นตอน

```bash
# 1. Backup (ถ้าต้องการ)
cp -r /workspace/transcription-service /workspace/transcription-service-backup

# 2. ลบ repository เก่า
rm -rf /workspace/transcription-service

# 3. Clone ใหม่
cd /workspace
git clone <repo-url> transcription-service

# 4. Switch branch (ถ้าต้องการ)
cd transcription-service
git checkout staging
```

### ตัวอย่างการใช้งาน

```bash
# SSH เข้า Pod
ssh root@<runpod-ip> -p <port>

# Backup (optional)
cp -r /workspace/transcription-service /workspace/transcription-service-backup

# ลบ repository เก่า
rm -rf /workspace/transcription-service

# Clone ใหม่
cd /workspace
git clone https://github.com/your-org/transcription-close-caption-service.git transcription-service

# Switch branch (ถ้าต้องการ)
cd transcription-service
git checkout staging
```

---

## ⚠️ ข้อควรระวัง

### 1. Services ที่กำลังทำงาน

**⚠️ สำคัญ:** ก่อนอัปเดต code ควร **stop services** ก่อน

```bash
# Stop services
pkill -f python
pkill -f redis

# หรือถ้าใช้ Docker Compose (ไม่ใช้ใน Direct Mode)
# docker compose -f docker-compose.runpod.yml down
```

### 2. Environment Variables

**⚠️ สำคัญ:** `.env.runpod` จะไม่ถูก commit ใน Git

```bash
# Backup .env.runpod ก่อน pull
cp /workspace/transcription-service/.env.runpod /tmp/.env.runpod.backup

# Pull code
git pull origin staging

# Restore .env.runpod (ถ้าถูกลบ)
cp /tmp/.env.runpod.backup /workspace/transcription-service/.env.runpod
```

### 3. Python Dependencies

**⚠️ สำคัญ:** หลัง pull code ควร **reinstall dependencies** ถ้ามีการเปลี่ยนแปลง `requirements.txt`

```bash
# Pull code
git pull origin staging

# Reinstall dependencies (ถ้า requirements.txt เปลี่ยน)
pip3 install --no-cache-dir -r requirements.txt
```

---

## 🔄 Workflow แนะนำ: อัปเดต Code และ Restart Services

### Step-by-Step

```bash
# 1. Stop services
pkill -f python
pkill -f redis

# 2. Backup .env.runpod (optional)
cp /workspace/transcription-service/.env.runpod /tmp/.env.runpod.backup

# 3. Pull latest code
cd /workspace/transcription-service
git pull origin staging

# 4. Reinstall dependencies (ถ้า requirements.txt เปลี่ยน)
pip3 install --no-cache-dir -r requirements.txt

# 5. Restore .env.runpod (ถ้าถูกลบ)
if [ ! -f ".env.runpod" ]; then
    cp /tmp/.env.runpod.backup .env.runpod
fi

# 6. Start services ใหม่
bash scripts/pod/start-services-direct.sh
```

---

## 📝 สร้าง Script สำหรับอัปเดต

สร้าง script `update-code.sh` เพื่ออัปเดต code อัตโนมัติ:

```bash
#!/bin/bash
# Script สำหรับอัปเดต code บน RunPod Pod Server

set -e

REPO_DIR="/workspace/transcription-service"
BRANCH="${1:-staging}"  # Default: staging

echo "🔄 Updating code on RunPod Pod Server..."
echo "📅 $(date)"
echo ""

# Check if repository exists
if [ ! -d "$REPO_DIR" ]; then
    echo "❌ Repository not found at $REPO_DIR"
    echo "💡 Please clone repository first:"
    echo "   cd /workspace"
    echo "   git clone <repo-url> transcription-service"
    exit 1
fi

cd "$REPO_DIR"

# Stop services
echo "🛑 Stopping services..."
pkill -f python || echo "⚠️  No Python processes found"
pkill -f redis || echo "⚠️  No Redis processes found"
sleep 2
echo "✅ Services stopped"
echo ""

# Backup .env.runpod
if [ -f ".env.runpod" ]; then
    echo "💾 Backing up .env.runpod..."
    cp .env.runpod /tmp/.env.runpod.backup
    echo "✅ Backup created"
fi
echo ""

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "📋 Current branch: $CURRENT_BRANCH"
echo "📋 Target branch: $BRANCH"
echo ""

# Switch branch (ถ้าต้องการ)
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    echo "🔄 Switching to branch: $BRANCH"
    git checkout "$BRANCH" || {
        echo "⚠️  Failed to switch branch. Continuing with current branch..."
    }
fi
echo ""

# Pull latest changes
echo "📥 Pulling latest changes..."
git pull origin "$BRANCH" || {
    echo "❌ Failed to pull changes"
    exit 1
}
echo "✅ Code updated"
echo ""

# Check if requirements.txt changed
if git diff HEAD@{1} HEAD --name-only | grep -q "requirements.txt"; then
    echo "📦 requirements.txt changed, reinstalling dependencies..."
    pip3 install --no-cache-dir -r requirements.txt
    echo "✅ Dependencies reinstalled"
else
    echo "📦 requirements.txt unchanged, skipping dependency reinstall"
fi
echo ""

# Restore .env.runpod (ถ้าถูกลบ)
if [ ! -f ".env.runpod" ] && [ -f "/tmp/.env.runpod.backup" ]; then
    echo "📝 Restoring .env.runpod..."
    cp /tmp/.env.runpod.backup .env.runpod
    echo "✅ .env.runpod restored"
fi
echo ""

# Start services
echo "🚀 Starting services..."
bash scripts/pod/start-services-direct.sh
```

**วิธีใช้งาน:**

```bash
# อัปเดตจาก staging branch (default)
bash /workspace/transcription-service/scripts/pod/update-code.sh

# อัปเดตจาก main branch
bash /workspace/transcription-service/scripts/pod/update-code.sh main
```

---

## 🔍 ตรวจสอบการเปลี่ยนแปลง

### ดูว่ามีอะไรเปลี่ยนแปลง

```bash
cd /workspace/transcription-service

# ดู commit history
git log --oneline -10

# ดูไฟล์ที่เปลี่ยนแปลง
git diff HEAD@{1} HEAD --name-only

# ดูรายละเอียดการเปลี่ยนแปลง
git diff HEAD@{1} HEAD
```

### ตรวจสอบว่า code อัปเดตแล้ว

```bash
# ตรวจสอบ version หรือ commit hash
cd /workspace/transcription-service
git log -1 --oneline

# ตรวจสอบว่า script ถูกอัปเดต
head -5 scripts/pod/start-services-direct.sh
```

---

## 📋 สรุป: เมื่อไหร่ควรใช้วิธีไหน?

| สถานการณ์ | วิธีที่แนะนำ |
|-----------|-------------|
| **อัปเดต code ปกติ** | Git Pull |
| **แก้ไข bug หรือ feature ใหม่** | Git Pull |
| **เปลี่ยน branch** | Git Pull + Checkout |
| **มีปัญหา Git conflict** | Clone ใหม่ |
| **Repository เสียหาย** | Clone ใหม่ |
| **ต้องการ clean state** | Clone ใหม่ |

---

## 🔗 Related Documents

- **Quick Start:** [QUICK_START.md](./QUICK_START.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- **Direct Mode Setup:** [DIRECT_MODE_SETUP.md](./DIRECT_MODE_SETUP.md)

---

**Last Updated:** 2024-12-19

