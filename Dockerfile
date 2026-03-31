# ============================================================================
# Transcription Service Image
# Base: kk-base (OS + CUDA + PyTorch + pip packages)
# This: Application code only (~3 MB)
#
# Build:
#   docker buildx build --platform linux/amd64 \
#     -t kksenateacr.azurecr.io/kk-transcription:latest \
#     --load .
#
# Rebuild เมื่อแก้โค้ด (เร็วมาก — push แค่ ~3 MB):
#   docker buildx build --platform linux/amd64 \
#     -t kksenateacr.azurecr.io/kk-transcription:v1.0.1 \
#     --load .
#   docker push kksenateacr.azurecr.io/kk-transcription:v1.0.1
# ============================================================================

FROM kksenateacr.azurecr.io/kk-base:ubuntu2404-cuda128-torch280

COPY . /workspace/transcription-service
WORKDIR /workspace/transcription-service

# ติดตั้ง packages ที่ base image ยังไม่มี (psycopg2 สำหรับ PostgreSQL storage)
RUN pip install --no-cache-dir psycopg2-binary>=2.9.9 2>/dev/null || true

RUN chmod +x scripts/pod/*.sh scripts/utility/*.sh 2>/dev/null || true

EXPOSE 8010 8002

CMD ["bash", "-c", "./scripts/pod/start-pod.sh && ./scripts/pod/start-rq-workers.sh && tail -f /dev/null"]
