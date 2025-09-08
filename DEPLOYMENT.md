# 🚀 Deployment Guide

## Prerequisites

### 1. Azure Container Registry (ACR)
- สร้าง ACR instance ใน Azure
- เปิดใช้งาน admin user
- เก็บ credentials ไว้

### 2. GitHub Secrets
ตั้งค่า secrets ใน GitHub repository:

```
ACR_LOGIN_SERVER=your-registry-name.azurecr.io
ACR_USERNAME=your-registry-username
ACR_PASSWORD=your-registry-password
```

### 3. Environment Files
- `env.staging` - สำหรับ staging environment
- `env.production` - สำหรับ production environment

## 🏗️ Build Process

### Automatic Build (GitHub Actions)
เมื่อ push ไปยัง `staging` branch:
1. Build main application image
2. Build whisper service image
3. Push images ไปยัง ACR
4. สร้าง `docker-compose.staging.acr.yml`

### Manual Build
```bash
# Build และ push ไปยัง ACR
docker build -t your-registry.azurecr.io/kk-transcription:latest .
docker build -t your-registry.azurecr.io/kk-transcription-whisper:latest ./whisper-service

# Login to ACR
docker login your-registry.azurecr.io

# Push images
docker push your-registry.azurecr.io/kk-transcription:latest
docker push your-registry.azurecr.io/kk-transcription-whisper:latest
```

## 🚀 Deployment

### Staging Deployment
```bash
# ใช้ docker-compose.staging.acr.yml
docker-compose -f docker-compose.staging.acr.yml up -d

# หรือใช้ staging compose file
docker-compose -f docker-compose.staging.yml up -d
```

### Production Deployment
```bash
# ใช้ production compose file
docker-compose -f docker-compose.yml up -d
```

## 📋 Environment Variables

### Required Secrets
- `ACR_LOGIN_SERVER` - ACR registry URL
- `ACR_USERNAME` - ACR username
- `ACR_PASSWORD` - ACR password

### Application Environment
- `ENVIRONMENT` - staging/production
- `STORAGE_TYPE` - sqlite/postgres
- `RABBITMQ_HOST` - RabbitMQ host
- `REDIS_HOST` - Redis host

## 🔧 Configuration Files

### Docker Compose Files
- `docker-compose.yml` - Production
- `docker-compose.dev.yml` - Development
- `docker-compose.staging.yml` - Staging (local build)
- `docker-compose.staging.acr.yml` - Staging (ACR images)

### Environment Files
- `env.staging` - Staging configuration
- `env.production` - Production configuration

## 🐛 Troubleshooting

### Build Errors
1. ตรวจสอบ ACR credentials
2. ตรวจสอบ Dockerfile syntax
3. ตรวจสอบ GitHub secrets

### Deployment Errors
1. ตรวจสอบ image tags
2. ตรวจสอบ environment variables
3. ตรวจสอบ port conflicts

### Health Check Failures
1. ตรวจสอบ service logs
2. ตรวจสอบ resource limits
3. ตรวจสอบ network connectivity

## 📊 Monitoring

### Health Endpoints
- API: `http://localhost:8001/health`
- Whisper: `http://localhost:8002/health`

### Management Interfaces
- RabbitMQ: `http://localhost:15672` (admin/admin123)
- Redis: `redis-cli -h localhost -p 6379`

## 🔄 GitFlow Workflow

### Development
```bash
git checkout -b feature/your-feature
# ทำการพัฒนา
git commit -m "feat: add new feature"
git push origin feature/your-feature
```

### Staging
```bash
git checkout staging
git merge feature/your-feature
git push origin staging
# GitHub Actions จะ build และ push ไปยัง ACR
```

### Production
```bash
git checkout main
git merge staging
git tag v1.0.0
git push origin main --tags
```

## 📝 Notes

- ใช้ `docker-compose.staging.acr.yml` สำหรับ staging ที่ใช้ ACR images
- ใช้ `docker-compose.staging.yml` สำหรับ staging ที่ build local
- ตรวจสอบ resource limits ใน staging environment
- ใช้ health checks เพื่อตรวจสอบ service status
