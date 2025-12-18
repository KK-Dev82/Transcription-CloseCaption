#!/bin/bash

# Script to test transcription with /uploads/v10-1.mp4

# Configuration
API_PORT="${API_PORT:-8010}"
API_URL="http://localhost:${API_PORT}/transcribe"
VIDEO_FILE="/workspace/transcription-service/uploads/v10-1.mp4"
LANGUAGE="th"
MODEL_SIZE="base"
CHUNK_DURATION=30 # seconds
USE_CHUNKING="true" # Enable chunking for large files
DISPLAY_MODE="full_text"
TIMEOUT_SECONDS=300 # 5 minutes for monitoring

# --- Helper Functions ---
print_header() {
    echo -e "\n\033[0;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
    echo -e "\033[0;34m$1\033[0m"
    echo -e "\033[0;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
}

print_status() {
    echo -e "\033[0;34mℹ️  $1\033[0m"
}

print_success() {
    echo -e "\033[0;32m✅ $1\033[0m"
}

print_warning() {
    echo -e "\033[1;33m⚠️  $1\033[0m"
}

print_error() {
    echo -e "\033[0;31m❌ $1\033[0m"
}

# --- Main Script ---
print_header "🧪 Test Transcription with v10-1.mp4"

# Check if video file exists
if [ ! -f "$VIDEO_FILE" ]; then
    print_error "❌ Video file not found: $VIDEO_FILE"
    exit 1
fi
print_success "✅ Video file found: $VIDEO_FILE"
print_status "   File size: $(du -h "$VIDEO_FILE" | awk '{print $1}')"

# 1. Upload Video File
print_header "1. Uploading Video File"
UPLOAD_RESPONSE=$(curl -s -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "file=@$VIDEO_FILE" \
    "http://localhost:${API_PORT}/upload")

UPLOAD_SUCCESS=$(echo "$UPLOAD_RESPONSE" | jq -r '.success')
UPLOADED_FILE_PATH=$(echo "$UPLOAD_RESPONSE" | jq -r '.file_path')
UPLOADED_FILE_NAME=$(echo "$UPLOAD_RESPONSE" | jq -r '.file_name')

if [ "$UPLOAD_SUCCESS" = "true" ]; then
    print_success "✅ File uploaded successfully"
    print_status "   File Path: $UPLOADED_FILE_PATH"
    print_status "   File Name: $UPLOADED_FILE_NAME"
else
    print_error "❌ Failed to upload file: $UPLOAD_RESPONSE"
    exit 1
fi

# 2. Start Transcription
print_header "2. Starting Transcription"
TRANSCRIPTION_PAYLOAD=$(jq -n \
    --arg filePath "$UPLOADED_FILE_PATH" \
    --arg lang "$LANGUAGE" \
    --arg model "$MODEL_SIZE" \
    --arg chunkDur "$CHUNK_DURATION" \
    --arg useChunk "$USE_CHUNKING" \
    --arg displayMode "$DISPLAY_MODE" \
    '{file_path: $filePath, language: $lang, model_size: $model, chunk_duration: ($chunkDur | tonumber), use_chunking: ($useChunk | fromjson), display_mode: $displayMode}')

TRANSCRIPTION_RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$TRANSCRIPTION_PAYLOAD" \
    "$API_URL")

TASK_ID=$(echo "$TRANSCRIPTION_RESPONSE" | jq -r '.task_id')
TRANSCRIPTION_STATUS=$(echo "$TRANSCRIPTION_RESPONSE" | jq -r '.status')

if [ "$TRANSCRIPTION_STATUS" = "pending" ] || [ "$TRANSCRIPTION_STATUS" = "processing" ]; then
    print_success "✅ Transcription started"
    print_status "   Task ID: $TASK_ID"
    print_status "   Status URL: http://localhost:${API_PORT}/transcribe/$TASK_ID"
else
    print_error "❌ Failed to start transcription: $TRANSCRIPTION_RESPONSE"
    exit 1
fi

# 3. Monitoring Progress
print_header "3. Monitoring Progress"
ELAPSED_TIME=0
CURRENT_STATUS="pending"
CURRENT_PROGRESS=0
CURRENT_STAGE="None"
LAST_PROGRESS=-1
LAST_COMPLETED_CHUNKS=-1

while [ "$CURRENT_STATUS" != "completed" ] && [ "$CURRENT_STATUS" != "failed" ] && [ "$ELAPSED_TIME" -lt "$TIMEOUT_SECONDS" ]; do
    TASK_STATUS_RESPONSE=$(curl -s "http://localhost:${API_PORT}/transcribe/$TASK_ID")
    CURRENT_STATUS=$(echo "$TASK_STATUS_RESPONSE" | jq -r '.status')
    CURRENT_PROGRESS=$(echo "$TASK_STATUS_RESPONSE" | jq -r '.progress')
    CURRENT_STAGE=$(echo "$TASK_STATUS_RESPONSE" | jq -r '.current_stage')
    CURRENT_STAGE_DESC=$(echo "$TASK_STATUS_RESPONSE" | jq -r '.current_stage_description')
    TOTAL_CHUNKS=$(echo "$TASK_STATUS_RESPONSE" | jq -r '.total_chunks // 0')
    COMPLETED_CHUNKS=$(echo "$TASK_STATUS_RESPONSE" | jq -r '.completed_chunks // 0')

    # Print only if progress or chunks changed
    if [ "$CURRENT_PROGRESS" != "$LAST_PROGRESS" ] || [ "$COMPLETED_CHUNKS" != "$LAST_COMPLETED_CHUNKS" ]; then
        print_status "   [${ELAPSED_TIME}s] Status: $CURRENT_STATUS, Progress: $CURRENT_PROGRESS%, Stage: ${CURRENT_STAGE_DESC:-$CURRENT_STAGE}"
        if [ "$TOTAL_CHUNKS" != "0" ] && [ "$TOTAL_CHUNKS" != "null" ]; then
            print_status "   Chunks: $COMPLETED_CHUNKS/$TOTAL_CHUNKS completed"
        fi
        LAST_PROGRESS=$CURRENT_PROGRESS
        LAST_COMPLETED_CHUNKS=$COMPLETED_CHUNKS
    fi
    
    if [ "$CURRENT_STATUS" = "completed" ]; then
        print_success "✅ Transcription completed!"
        break
    elif [ "$CURRENT_STATUS" = "failed" ]; then
        print_error "❌ Transcription failed!"
        break
    fi

    sleep 5
    ELAPSED_TIME=$((ELAPSED_TIME + 5))
done

if [ "$CURRENT_STATUS" != "completed" ] && [ "$CURRENT_STATUS" != "failed" ]; then
    print_warning "⚠️  Timeout waiting for completion"
fi

# 4. Final Result
print_header "4. Final Result"
FINAL_RESULT=$(curl -s "http://localhost:${API_PORT}/transcribe/$TASK_ID")
FINAL_STATUS=$(echo "$FINAL_RESULT" | jq -r '.status')
FINAL_PROGRESS=$(echo "$FINAL_RESULT" | jq -r '.progress')
FINAL_TOTAL_CHUNKS=$(echo "$FINAL_RESULT" | jq -r '.total_chunks // 0')
FINAL_COMPLETED_CHUNKS=$(echo "$FINAL_RESULT" | jq -r '.completed_chunks // 0')

if [ "$FINAL_STATUS" = "completed" ]; then
    print_success "✅ ✅ Transcription status: $FINAL_STATUS"
    print_status "   Progress: $FINAL_PROGRESS%"
    print_status "   Chunks: $FINAL_COMPLETED_CHUNKS/$FINAL_TOTAL_CHUNKS"
    FULL_TEXT=$(echo "$FINAL_RESULT" | jq -r '.full_text // ""')
    if [ -n "$FULL_TEXT" ]; then
        TEXT_LENGTH=$(echo "$FULL_TEXT" | wc -c)
        print_status "   Text length: $TEXT_LENGTH characters"
        echo "$FINAL_RESULT" | jq '.full_text' | head -c 200
        echo "..."
    fi
else
    print_error "❌ ❌ Transcription status: $FINAL_STATUS"
    print_status "   Progress: $FINAL_PROGRESS%"
    print_status "   Chunks: $FINAL_COMPLETED_CHUNKS/$FINAL_TOTAL_CHUNKS"
    ERROR_MSG=$(echo "$FINAL_RESULT" | jq -r '.error_message // ""')
    if [ -n "$ERROR_MSG" ]; then
        print_error "   Error: $ERROR_MSG"
    fi
fi

print_status "   💡 Check full result: curl http://localhost:${API_PORT}/transcribe/$TASK_ID"

