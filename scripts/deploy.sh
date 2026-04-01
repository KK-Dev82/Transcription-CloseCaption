#!/bin/bash
# Deploy/Update Transcription Service
# รันบน server (10.200.22.64) หลัง CI/CD build เสร็จ
#
# Usage:
#   bash scripts/pod/deploy-update.sh
#   bash scripts/pod/deploy-update.sh --skip-login   # ข้าม az login (ถ้า login แล้ว)

set -e

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
SKIP_LOGIN=false

for arg in "$@"; do
    case $arg in
        --skip-login) SKIP_LOGIN=true ;;
    esac
done

echo "🚀 Deploying Transcription Service"
echo "   Compose: $COMPOSE_FILE"
echo ""

# 1. Login ACR (ถ้าไม่ skip)
if [ "$SKIP_LOGIN" = false ]; then
    echo "🔑 Logging in to Azure Container Registry..."
    az acr login --name kksenateacr
    echo ""
fi

# 2. Pull image ใหม่
echo "📥 Pulling latest image..."
docker compose -f "$COMPOSE_FILE" pull transcription
echo ""

# 3. Restart container
echo "🔄 Restarting container..."
docker compose -f "$COMPOSE_FILE" down
docker compose -f "$COMPOSE_FILE" up -d
echo ""

# 4. รอ service start
echo "⏳ Waiting for service to start (40s)..."
sleep 40

# 5. ตรวจสอบ
echo "✅ Checking..."
echo "   STORAGE_TYPE: $(docker exec transcription-service bash -c 'echo $STORAGE_TYPE' 2>/dev/null || echo 'N/A')"
echo "   Workers: $(docker exec transcription-service ps aux 2>/dev/null | grep 'rq worker' | grep -v grep | wc -l)"
echo "   Health: $(curl -s http://localhost:8010/health 2>/dev/null || echo 'N/A')"
echo ""
echo "🎉 Deploy complete!"
