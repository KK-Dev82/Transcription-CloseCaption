# 🚀 Staging Deployment Checklist

## **Pre-Deployment**

### **1. ตรวจสอบ Code Changes**
- [ ] `app/services/file_service.py` - เพิ่ม `os.chmod(file_path, 0o644)`
- [ ] `app/api/websocket.py` - เพิ่ม pong message handler
- [ ] `test-files/` - ไฟล์ทดสอบใหม่
- [ ] `scripts/` - scripts สำหรับจัดการ permission

### **2. ตรวจสอบ Docker Images**
- [ ] `Dockerfile.optimized` - ใช้ port 8001
- [ ] `docker-compose.yml` - configuration ถูกต้อง
- [ ] `whisper-service/Dockerfile.linux` - สำหรับ staging

### **3. ตรวจสอบ Environment Variables**
- [ ] `env.staging` - configuration ถูกต้อง
- [ ] ACR credentials - login สำเร็จ
- [ ] Staging server access - เข้าถึงได้

## **Deployment Process**

### **1. Build Images**
```bash
# รัน build script
./scripts/build-staging.sh

# ตรวจสอบ images
docker images | grep kksenateacr
```

### **2. Deploy to Staging**
```bash
# Deploy ไป staging server
./scripts/deploy-staging.sh

# ตรวจสอบ deployment
kubectl get pods -n staging
kubectl get services -n staging
```

### **3. ตรวจสอบ Health**
```bash
# ตรวจสอบ API
curl -f https://staging-ph2.bms.senate.go.th/transcribe/health

# ตรวจสอบ stats
curl -f https://staging-ph2.bms.senate.go.th/transcribe/stats
```

## **Post-Deployment Testing**

### **1. Permission Testing**
```bash
# รัน permission test
./scripts/test-staging-permission.sh

# หรือทดสอบผ่าน browser
https://staging-ph2.bms.senate.go.th/transcribe/test-files/test_permission_fix.html
```

### **2. Functionality Testing**
- [ ] File upload ทำงาน
- [ ] Transcription ทำงาน
- [ ] WebSocket ทำงาน
- [ ] Permission ถูกต้อง

### **3. Performance Testing**
- [ ] Response time < 2s
- [ ] Memory usage < 8GB
- [ ] CPU usage < 80%

## **Rollback Plan**

### **1. หากเกิดปัญหา**
```bash
# Rollback ไป version เก่า
kubectl rollout undo deployment/transcription-api -n staging
kubectl rollout undo deployment/transcription-whisper -n staging
```

### **2. ตรวจสอบ Logs**
```bash
# ดู logs
kubectl logs -f deployment/transcription-api -n staging
kubectl logs -f deployment/transcription-whisper -n staging
```

## **Monitoring**

### **1. Health Checks**
- [ ] API health check
- [ ] Database connectivity
- [ ] Redis connectivity
- [ ] RabbitMQ connectivity

### **2. Metrics**
- [ ] Response time
- [ ] Error rate
- [ ] Memory usage
- [ ] CPU usage

### **3. Alerts**
- [ ] Error rate > 5%
- [ ] Response time > 5s
- [ ] Memory usage > 90%
- [ ] CPU usage > 90%

## **Documentation**

### **1. Update Documentation**
- [ ] README.md
- [ ] API documentation
- [ ] Deployment guide
- [ ] Troubleshooting guide

### **2. Test Results**
- [ ] Permission test results
- [ ] Performance test results
- [ ] Security test results

## **Sign-off**

- [ ] Development Team
- [ ] QA Team
- [ ] DevOps Team
- [ ] Product Owner

---

**Deployment Date:** _______________
**Deployed By:** _______________
**Version:** _______________
**Status:** _______________
