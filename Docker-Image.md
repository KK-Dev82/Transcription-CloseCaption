# 1. Build → เข้า Docker Engine
docker buildx build --platform linux/amd64 \
  -f Dockerfile.prod \
  -t kksenateacr.azurecr.io/kk-transcription:release-v1.1.0 \
  --cache-from type=local,src=/Volumes/TS960GJDM850-Media/Library/Docker-Cache \
  --cache-to type=local,dest=/Volumes/TS960GJDM850-Media/Library/Docker-Cache \
  --load .

# 2. Push → ขึ้น Azure (ไม่ต้อง save เป็นไฟล์)
docker push kksenateacr.azurecr.io/kk-transcription:release-v1.1.0

# 3. Save → เก็บเป็น tar.gz (ถ้าต้องการ transfer ไป server ด้วยมือ)
docker save kksenateacr.azurecr.io/kk-transcription:release-v1.1.0 \
  | gzip > "/Volumes/.../transcription-close-caption-service-docker-image/kk-transcription-release-v1.1.0.tar.gz"