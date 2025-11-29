# 📁 Scripts Directory

Scripts สำหรับการ Build, Deploy และ Manage Transcription Service

## 📂 Structure

```
scripts/
├── local/          # Local development scripts
├── staging/        # Staging deployment scripts
├── pod/            # RunPod & HP Z2 scripts
├── utility/        # Utility scripts (models, etc.)
└── test/           # Test scripts
```

---

## 🚀 Quick Start

### Local Development
```bash
# Build และ run services
bash scripts/local/build-run-local.sh
```

### Staging Deployment
```bash
# Build และ push ไป ACR
bash scripts/staging/build-and-push-acr.sh

# Deploy ไป staging
bash scripts/staging/deploy-staging.sh
```

### RunPod Setup
```bash
# Build Custom Base Image
bash scripts/pod/build-and-push-runpod-base.sh

# Setup RunPod Pod
bash scripts/pod/setup-runpod.sh
```

### Download Models
```bash
# Download Whisper models
bash scripts/utility/download-models.sh --all
```

---

## 📚 Documentation

- [Local Scripts](./local/README.md) - Local development scripts
- [Staging Scripts](./staging/README.md) - Staging deployment scripts
- [Pod Scripts](./pod/README.md) - RunPod & HP Z2 scripts
- [Utility Scripts](./utility/README.md) - Utility scripts

---

## 🔗 Related Files

- `docker-compose.local.yml` - Local Docker Compose
- `docker-compose.staging.yml` - Staging Docker Compose
- `docker-compose.runpod.yml` - RunPod Docker Compose
- `Dockerfile.runpod-base` - Custom Base Image

