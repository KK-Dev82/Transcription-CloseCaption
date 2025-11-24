# 📊 การวิเคราะห์ Image และ Timeout Issues

## 🔍 1. Image Comparison

### Local Docker Images
```
kk-transcription:local-dev
- Image ID: a51b084b30bc
- Size: 2.7GB
- Created: 16 hours ago
- Status: ✅ มี code ล่าสุด (build จาก local)
```

### ACR Images
```
kksenateacr.azurecr.io/kk-transcription:alpha-dev
- Tag: alpha-dev
- Status: ⚠️ อาจไม่ใช่ code ล่าสุด (build ยังไม่เสร็จ)
```

### Code ปัจจุบัน
- ✅ Timeout: `300` วินาที (5 นาที) สำหรับ Whisper API calls
- ✅ Location: `app/services/whisper_service.py:137`
- ✅ Code ล่าสุด: มี retry mechanism ใน Dockerfile

## ⚠️ 2. ปัญหา Timeout จาก Staging Logs

### Error Pattern
```
HTTPConnectionPool(host='whisper', port=8002): Read timed out. (read timeout=300)
```

### สาเหตุที่เป็นไปได้

#### 1. **Worker 3 ถูกปิดไป**
- ✅ **ยืนยัน**: `docker-compose.staging.yml` ไม่มี `video-worker-3` (commented out)
- **ผลกระทบ**: 
  - มี worker เพียง 2 ตัว (worker-1, worker-2)
  - Workload เพิ่มขึ้น 50% ต่อ worker
  - Whisper service อาจรับ load ไม่ไหว

#### 2. **Whisper Service Resources ไม่เพียงพอ**
```yaml
whisper:
  deploy:
    resources:
      limits:
        memory: 1.5G  # ⚠️ น้อยมาก
        cpus: '1.0'
```

#### 3. **Timeout 300 วินาที อาจไม่พอ**
- Chunks บางตัวอาจใช้เวลานานกว่า 5 นาที
- โดยเฉพาะ chunks ที่มี audio ยาวหรือซับซ้อน

#### 4. **Image บน ACR อาจไม่ใช่ code ล่าสุด**
- Build ยังไม่เสร็จ → Image เก่ายังไม่มี retry mechanism
- Code เก่าอาจมี timeout issues

## 🔧 3. วิธีแก้ไข

### Option 1: เพิ่ม Timeout (Quick Fix)
```python
# app/services/whisper_service.py:137
timeout=600  # เพิ่มเป็น 10 นาที
```

### Option 2: เพิ่ม Retry Mechanism
```python
# app/services/whisper_service.py
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def transcribe_file(self, ...):
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    response = session.post(
        f"{whisper_api_url}/transcribe",
        json=request_data,
        timeout=600  # 10 นาที
    )
```

### Option 3: เพิ่ม Worker 3 กลับมา (ถ้า Resources เพียงพอ)
```yaml
# docker-compose.staging.yml
video-worker-3:
  image: kksenateacr.azurecr.io/kk-transcription:alpha-dev
  # ... config เหมือน worker-1, worker-2
  deploy:
    resources:
      limits:
        memory: 1G
        cpus: '0.4'
```

### Option 4: เพิ่ม Whisper Resources
```yaml
# docker-compose.staging.yml
whisper:
  deploy:
    resources:
      limits:
        memory: 2.5G  # เพิ่มจาก 1.5G
        cpus: '1.5'   # เพิ่มจาก 1.0
```

## 📋 4. Checklist

### ก่อน Deploy Image ใหม่
- [ ] Build เสร็จแล้ว
- [ ] Image push ไปยัง ACR สำเร็จ
- [ ] Image มี code ล่าสุด (retry mechanism)

### หลัง Deploy
- [ ] Pull image ใหม่บน Staging
- [ ] Restart containers
- [ ] ตรวจสอบ logs ว่าไม่มี timeout errors

### ถ้ายังมีปัญหา
- [ ] เพิ่ม timeout เป็น 600 วินาที
- [ ] เพิ่ม retry mechanism
- [ ] ตรวจสอบ Whisper service resources
- [ ] พิจารณาเพิ่ม worker-3 กลับมา

## 🎯 5. สรุป

**ปัญหาหลัก:**
1. ⚠️ Image บน ACR อาจไม่ใช่ code ล่าสุด (build ยังไม่เสร็จ)
2. ⚠️ Worker 3 ถูกปิด → Workload เพิ่มขึ้น 50%
3. ⚠️ Timeout 300 วินาที อาจไม่พอสำหรับ chunks บางตัว
4. ⚠️ Whisper resources (1.5G RAM, 1.0 CPU) อาจไม่เพียงพอ

**แนะนำ:**
1. ✅ รอ build เสร็จ → Push image ใหม่
2. ✅ เพิ่ม timeout เป็น 600 วินาที
3. ✅ เพิ่ม retry mechanism
4. ⚠️ พิจารณาเพิ่ม worker-3 หรือเพิ่ม Whisper resources





