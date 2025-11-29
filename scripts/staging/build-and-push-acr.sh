#!/bin/bash

# Build and Push to ACR from Local Machine
# This script builds Docker images locally and pushes to Azure Container Registry
# Usage: ./scripts/build-and-push-acr.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ACR_NAME="kksenateacr"
IMAGE_TAG="alpha-dev"
REGISTRY_URL="${ACR_NAME}.azurecr.io"
MAIN_IMAGE_NAME="kk-transcription"
WHISPER_IMAGE_NAME="kk-transcription-whisper"

echo -e "${BLUE}🚀 Building and pushing images to ACR from local machine...${NC}"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI is not installed. Please install it first.${NC}"
    echo "Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Check if logged in to Azure
echo -e "${YELLOW}🔐 Checking Azure login status...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to Azure. Please login...${NC}"
    az login
fi

# Login to ACR
echo -e "${YELLOW}🔐 Logging in to Azure Container Registry...${NC}"
az acr login --name ${ACR_NAME} || {
    echo -e "${RED}❌ Failed to login to ACR. Please check your ACR credentials.${NC}"
    exit 1
}

# Set up Docker Buildx with multi-platform support
echo -e "${YELLOW}🔧 Setting up Docker Buildx with multi-platform support...${NC}"
# ลบ builder เก่า (ถ้ามี) และสร้างใหม่เพื่อแน่ใจว่ามี QEMU emulation
docker buildx rm acr-builder 2>/dev/null || true
docker buildx create --use --name acr-builder --driver docker-container --bootstrap --platform linux/amd64,linux/arm64 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Builder already exists, checking platform support...${NC}"
    docker buildx use acr-builder
    docker buildx inspect --bootstrap
}
echo -e "${GREEN}✅ Buildx builder ready with multi-platform support${NC}"

# Build and push main API image (FORCE linux/amd64 only)
echo -e "${BLUE}📦 Building main API image (linux/amd64): ${REGISTRY_URL}/${MAIN_IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo -e "${YELLOW}⚠️  Building for linux/amd64 platform only...${NC}"
docker buildx build \
    --platform linux/amd64 \
    --load=false \
    -f Dockerfile \
    -t ${REGISTRY_URL}/${MAIN_IMAGE_NAME}:${IMAGE_TAG} \
    --push \
    --progress=plain \
    . || {
    echo -e "${RED}❌ Failed to build and push main API image${NC}"
    exit 1
}
echo -e "${GREEN}✅ Main API image built and pushed successfully!${NC}"

# Verify manifest
echo -e "${YELLOW}🔍 Verifying image manifest...${NC}"
docker manifest inspect ${REGISTRY_URL}/${MAIN_IMAGE_NAME}:${IMAGE_TAG} | grep -A 5 "platform" || {
    echo -e "${YELLOW}⚠️  Could not verify manifest, but push completed${NC}"
}

# Build and push Whisper service image (FORCE linux/amd64 only)
echo -e "${BLUE}📦 Building Whisper service image (linux/amd64): ${REGISTRY_URL}/${WHISPER_IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo -e "${YELLOW}⚠️  Building for linux/amd64 platform only...${NC}"
cd whisper-service
docker buildx build \
    --platform linux/amd64 \
    --load=false \
    -f Dockerfile.linux \
    -t ${REGISTRY_URL}/${WHISPER_IMAGE_NAME}:${IMAGE_TAG} \
    --push \
    --progress=plain \
    . || {
    echo -e "${RED}❌ Failed to build and push Whisper service image${NC}"
    cd ..
    exit 1
}
cd ..

# Verify manifest
echo -e "${YELLOW}🔍 Verifying Whisper image manifest...${NC}"
docker manifest inspect ${REGISTRY_URL}/${WHISPER_IMAGE_NAME}:${IMAGE_TAG} | grep -A 5 "platform" || {
    echo -e "${YELLOW}⚠️  Could not verify manifest, but push completed${NC}"
}

# Clean up buildx builder (optional)
echo -e "${YELLOW}🧹 Cleaning up buildx builder...${NC}"
docker buildx prune -f

echo -e "${GREEN}✅ All images built and pushed successfully!${NC}"
echo -e "${BLUE}🔗 Registry: ${REGISTRY_URL}${NC}"
echo -e "${BLUE}🏷️  Tag: ${IMAGE_TAG}${NC}"
echo ""
echo -e "${GREEN}📋 Pushed images:${NC}"
echo -e "  - ${REGISTRY_URL}/${MAIN_IMAGE_NAME}:${IMAGE_TAG}"
echo -e "  - ${REGISTRY_URL}/${WHISPER_IMAGE_NAME}:${IMAGE_TAG}"

