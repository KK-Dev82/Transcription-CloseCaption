#!/bin/bash

# Script: Download Whisper Models
# สำหรับโหลด Whisper models (base, small, medium, large, large-v3) มาไว้ที่ models/
# รองรับทั้ง Docker Compose และ Direct Mode

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Model sizes and their expected sizes (in bytes)
declare -A MODEL_SIZES=(
    ["tiny"]=75000000
    ["base"]=148000000
    ["small"]=488000000
    ["medium"]=1540000000
    ["large"]=3100000000
    ["large-v2"]=3100000000
    ["large-v3"]=3100000000
    ["large-v3-turbo"]=3100000000
)

# Parse arguments
MODELS_TO_DOWNLOAD=()
USE_DOCKER_SCRIPT=false
SKIP_RESTART=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            MODELS_TO_DOWNLOAD=("base" "small" "medium")
            shift
            ;;
        --docker-script)
            USE_DOCKER_SCRIPT=true
            shift
            ;;
        --skip-restart)
            SKIP_RESTART=true
            shift
            ;;
        base|small|medium|large|large-v2|large-v3|large-v3-turbo|tiny)
            MODELS_TO_DOWNLOAD+=("$1")
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            echo ""
            echo "Usage:"
            echo "  bash scripts/utility/download-models.sh [model1] [model2] ... [options]"
            echo ""
            echo "Examples:"
            echo "  bash scripts/utility/download-models.sh base"
            echo "  bash scripts/utility/download-models.sh base small medium"
            echo "  bash scripts/utility/download-models.sh --all"
            echo ""
            echo "Options:"
            echo "  --all              Download base, small, medium"
            echo "  --docker-script    Use whisper.cpp download script (if available)"
            echo "  --skip-restart     Skip restarting containers/services"
            echo ""
            echo "Supported models:"
            echo "  tiny, base, small, medium, large, large-v2, large-v3, large-v3-turbo"
            exit 1
            ;;
    esac
done

# Default to base if no models specified
if [ ${#MODELS_TO_DOWNLOAD[@]} -eq 0 ]; then
    MODELS_TO_DOWNLOAD=("base")
    print_warning "No model specified, defaulting to 'base'"
fi

echo "📥 Starting Whisper Models Download..."
echo "📋 Models to download: ${MODELS_TO_DOWNLOAD[*]}"
echo ""

# Detect environment (Docker Compose or Direct Mode)
DETECTED_MODE="unknown"
if command -v docker &> /dev/null && docker ps &> /dev/null; then
    if [ -f "docker-compose.yml" ] || [ -f "docker-compose.local.yml" ] || [ -f "docker-compose.staging.yml" ]; then
        DETECTED_MODE="docker-compose"
    fi
fi

if [ -d "whisper-service" ] && [ -f "whisper-service/models/download-ggml-model.sh" ]; then
    DETECTED_MODE="direct"
fi

print_status "Detected mode: $DETECTED_MODE"

# สร้าง directory
print_status "Creating models directory..."
mkdir -p models
print_success "Models directory created"

# ตรวจสอบว่า curl หรือ wget มีอยู่หรือไม่
if command -v wget &> /dev/null; then
    DOWNLOAD_CMD="wget"
    DOWNLOAD_FLAGS="-O"
elif command -v curl &> /dev/null; then
    DOWNLOAD_CMD="curl"
    DOWNLOAD_FLAGS="-L -o"
else
    print_error "Neither curl nor wget is installed. Installing..."
    if command -v apt-get &> /dev/null; then
        sudo apt update && sudo apt install -y wget curl
    elif command -v yum &> /dev/null; then
        sudo yum install -y wget curl
    else
        print_error "Cannot install wget/curl automatically. Please install manually."
        exit 1
    fi
    DOWNLOAD_CMD="wget"
    DOWNLOAD_FLAGS="-O"
fi

# Function to download model using direct URL
download_model_direct() {
    local model_size=$1
    local model_file="ggml-${model_size}.bin"
    local model_url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${model_file}"
    
    print_status "Downloading ${model_file} using $DOWNLOAD_CMD..."
    
    if $DOWNLOAD_CMD $DOWNLOAD_FLAGS "models/${model_file}" "$model_url"; then
        print_success "${model_file} downloaded successfully"
        return 0
    else
        print_warning "Failed to download ${model_file} from primary URL"
        
        # Try alternative URLs
        local alternative_urls=(
            "${model_url}?download=true"
            "https://huggingface.co/ggerganov/whisper.cpp/raw/main/${model_file}"
        )
        
        for url in "${alternative_urls[@]}"; do
            print_status "Trying alternative URL: $url"
            if $DOWNLOAD_CMD $DOWNLOAD_FLAGS "models/${model_file}" "$url"; then
                print_success "${model_file} downloaded successfully using alternative URL"
                return 0
            fi
        done
        
        return 1
    fi
}

# Function to download model using whisper.cpp script
download_model_script() {
    local model_size=$1
    local model_file="ggml-${model_size}.bin"
    
    # Check if whisper-service directory exists
    if [ ! -d "whisper-service" ]; then
        print_warning "whisper-service directory not found, falling back to direct download"
        return 1
    fi
    
    local download_script="whisper-service/models/download-ggml-model.sh"
    if [ ! -f "$download_script" ]; then
        print_warning "download-ggml-model.sh not found, falling back to direct download"
        return 1
    fi
    
    print_status "Downloading ${model_file} using whisper.cpp script..."
    
    # Run download script
    if bash "$download_script" "$model_size"; then
        # Copy model to models directory
        local source_path="whisper-service/models/${model_file}"
        if [ -f "$source_path" ]; then
            cp "$source_path" "models/${model_file}"
            print_success "${model_file} downloaded and copied successfully"
            return 0
        else
            print_warning "Model file not found after download, falling back to direct download"
            return 1
        fi
    else
        print_warning "Download script failed, falling back to direct download"
        return 1
    fi
}

# Function to verify model file
verify_model() {
    local model_size=$1
    local model_file="ggml-${model_size}.bin"
    local expected_size=${MODEL_SIZES[$model_size]:-100000000}
    
    if [ ! -f "models/${model_file}" ]; then
        print_error "${model_file} not found"
        return 1
    fi
    
    local file_size_bytes=$(stat -c%s "models/${model_file}" 2>/dev/null || stat -f%z "models/${model_file}" 2>/dev/null || echo "0")
    local file_size=$(du -h "models/${model_file}" | cut -f1)
    local file_type=$(file "models/${model_file}" 2>/dev/null || echo "unknown")
    
    print_success "File size: $file_size ($file_size_bytes bytes)"
    print_success "File type: $file_type"
    
    # Check minimum size (80% of expected)
    local min_size=$((expected_size * 80 / 100))
    if [ $file_size_bytes -lt $min_size ]; then
        print_error "Model file is too small! Expected ~$((expected_size / 1000000))MB, got $file_size"
        print_error "File might be corrupted or incomplete"
        return 1
    fi
    
    # Check if it's ASCII text (should be binary)
    if [[ $file_type == *"ASCII text"* ]]; then
        print_error "Model file is ASCII text, not binary!"
        print_error "This is not a valid Whisper model file"
        return 1
    fi
    
    print_success "Model file validation passed"
    return 0
}

# Download each model
DOWNLOADED_MODELS=()
FAILED_MODELS=()

for model_size in "${MODELS_TO_DOWNLOAD[@]}"; do
    model_file="ggml-${model_size}.bin"
    
    echo ""
    print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_status "Processing: $model_size"
    print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if model already exists
    if [ -f "models/${model_file}" ]; then
        print_warning "${model_file} already exists"
        read -p "Overwrite? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Skipping ${model_file}"
            DOWNLOADED_MODELS+=("$model_size")
            continue
        fi
        rm -f "models/${model_file}"
    fi
    
    # Try to download
    SUCCESS=false
    
    # Try whisper.cpp script first (if enabled and available)
    if [ "$USE_DOCKER_SCRIPT" = true ] || [ "$DETECTED_MODE" = "direct" ]; then
        if download_model_script "$model_size"; then
            SUCCESS=true
        fi
    fi
    
    # Fall back to direct download
    if [ "$SUCCESS" = false ]; then
        if download_model_direct "$model_size"; then
            SUCCESS=true
        fi
    fi
    
    # Verify downloaded file
    if [ "$SUCCESS" = true ]; then
        if verify_model "$model_size"; then
            DOWNLOADED_MODELS+=("$model_size")
            print_success "✅ ${model_file} downloaded and verified successfully"
        else
            print_error "❌ ${model_file} verification failed"
            rm -f "models/${model_file}"
            FAILED_MODELS+=("$model_size")
        fi
    else
        print_error "❌ Failed to download ${model_file}"
        FAILED_MODELS+=("$model_size")
    fi
done

# Summary
echo ""
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Download Summary"
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ${#DOWNLOADED_MODELS[@]} -gt 0 ]; then
    print_success "✅ Successfully downloaded: ${DOWNLOADED_MODELS[*]}"
    echo ""
    print_status "📁 Directory structure:"
    ls -lh models/ | grep "ggml-.*\.bin" || echo "No model files found"
fi

if [ ${#FAILED_MODELS[@]} -gt 0 ]; then
    print_error "❌ Failed to download: ${FAILED_MODELS[*]}"
fi

echo ""

# Restart services (if not skipped)
if [ "$SKIP_RESTART" = false ]; then
    if [ "$DETECTED_MODE" = "docker-compose" ]; then
        print_status "🔄 Restarting Whisper containers..."
        if docker compose restart whisper whisper-live 2>/dev/null || docker-compose restart whisper whisper-live 2>/dev/null; then
            print_success "Whisper containers restarted"
            echo ""
            print_status "📊 Container status:"
            docker compose ps | grep whisper || docker-compose ps | grep whisper || true
        else
            print_warning "Failed to restart Whisper containers (may not be running)"
        fi
    elif [ "$DETECTED_MODE" = "direct" ]; then
        print_warning "Direct Mode detected - services need to be restarted manually"
        print_status "💡 To restart services, run:"
        echo "   bash scripts/pod/stop-services.sh"
        echo "   bash scripts/pod/start-services-direct.sh"
    else
        print_warning "Could not detect environment - skipping service restart"
    fi
fi

echo ""
if [ ${#FAILED_MODELS[@]} -eq 0 ]; then
    print_success "✅ Download completed successfully!"
    echo "🌐 Whisper API: http://localhost:8002/health"
    echo "🌐 Main API: http://localhost:8001/health"
else
    print_warning "⚠️  Download completed with some failures"
    exit 1
fi
