#!/bin/bash

# Build and Push to ACR for Staging Environment
# This script builds Docker images for Linux (AMD64) architecture

set -e

# Configuration
ACR_NAME="kksenateacr"
IMAGE_TAG="alpha-dev"
REGISTRY_URL="${ACR_NAME}.azurecr.io"

echo "🚀 Building and pushing images to ACR..."

# 1. Build Main API Image (ไม่ติดตั้ง PyTorch)
echo "📦 Building main API image..."
docker buildx build \
    --platform linux/amd64 \
    -f Dockerfile.optimized \
    -t ${REGISTRY_URL}/kk-transcription:${IMAGE_TAG} \
    --push \
    .

# 2. Build Whisper Service Image
echo "📦 Building Whisper service image..."
cd whisper-service
docker buildx build \
    --platform linux/amd64 \
    -f Dockerfile.linux \
    -t ${REGISTRY_URL}/kk-transcription-whisper:${IMAGE_TAG} \
    --push \
    .
cd ..

echo "✅ All images built and pushed successfully!"
echo "🔗 Registry: ${REGISTRY_URL}"
echo "🏷️  Tag: ${IMAGE_TAG}"

# List pushed images
echo "📋 Pushed images:"
echo "  - ${REGISTRY_URL}/kk-transcription:${IMAGE_TAG}"
echo "  - ${REGISTRY_URL}/kk-transcription-whisper:${IMAGE_TAG}"
