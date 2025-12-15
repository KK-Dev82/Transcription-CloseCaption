#!/bin/bash
# Script สำหรับทำความสะอาด storage และไฟล์ชั่วคราว
#
# Usage:
#   bash scripts/pod/cleanup-storage.sh [options]
#
# Options:
#   --dry-run    Show what would be deleted without actually deleting
#   --keep-days  Number of days to keep files (default: 7)
#   --aggressive Aggressive cleanup (delete more files)

set -e

# Default values
DRY_RUN=false
KEEP_DAYS=7
AGGRESSIVE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --keep-days)
            KEEP_DAYS="$2"
            shift 2
            ;;
        --aggressive)
            AGGRESSIVE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

PROJECT_DIR="/workspace/transcription-service"
cd "$PROJECT_DIR"

echo "🧹 Storage Cleanup Script"
echo "=========================="
echo "Keep days: $KEEP_DAYS"
echo "Dry run: $DRY_RUN"
echo "Aggressive: $AGGRESSIVE"
echo ""

# Function to delete files
delete_files() {
    local pattern="$1"
    local description="$2"
    
    if [ "$DRY_RUN" = true ]; then
        echo "🔍 [DRY RUN] Would delete: $description"
        find $pattern -type f -mtime +$KEEP_DAYS 2>/dev/null | wc -l | xargs echo "   Files found:"
    else
        local count=$(find $pattern -type f -mtime +$KEEP_DAYS 2>/dev/null | wc -l)
        if [ "$count" -gt 0 ]; then
            find $pattern -type f -mtime +$KEEP_DAYS -delete 2>/dev/null
            echo "✅ Deleted $count files: $description"
        else
            echo "ℹ️  No files to delete: $description"
        fi
    fi
}

# Function to delete directories
delete_dirs() {
    local pattern="$1"
    local description="$2"
    
    if [ "$DRY_RUN" = true ]; then
        echo "🔍 [DRY RUN] Would delete: $description"
        find $pattern -type d -mtime +$KEEP_DAYS 2>/dev/null | wc -l | xargs echo "   Directories found:"
    else
        local count=$(find $pattern -type d -mtime +$KEEP_DAYS 2>/dev/null | wc -l)
        if [ "$count" -gt 0 ]; then
            find $pattern -type d -mtime +$KEEP_DAYS -exec rm -rf {} + 2>/dev/null
            echo "✅ Deleted $count directories: $description"
        else
            echo "ℹ️  No directories to delete: $description"
        fi
    fi
}

# Show storage before cleanup
echo "📊 Storage Before Cleanup:"
df -h /workspace | tail -1
echo ""

# 1. Clean temp files
echo "1️⃣  Cleaning temp files..."
if [ "$DRY_RUN" = true ]; then
    echo "🔍 [DRY RUN] Would clean: temp/*"
    find temp -type f 2>/dev/null | wc -l | xargs echo "   Files found:"
else
    rm -rf temp/* 2>/dev/null
    echo "✅ Cleaned temp/"
fi
echo ""

# 2. Clean old uploads
echo "2️⃣  Cleaning old uploads (older than $KEEP_DAYS days)..."
delete_files "uploads" "old uploads"
echo ""

# 3. Clean old logs
echo "3️⃣  Cleaning old logs (older than $KEEP_DAYS days)..."
delete_files "logs" "old log files"
echo ""

# 4. Clean /tmp logs
echo "4️⃣  Cleaning /tmp logs..."
if [ "$DRY_RUN" = true ]; then
    echo "🔍 [DRY RUN] Would delete: /tmp/video-worker.log, /tmp/transcription-service.log"
    ls -lh /tmp/video-worker.log /tmp/transcription-service.log 2>/dev/null || echo "   Files not found"
else
    rm -f /tmp/video-worker.log /tmp/transcription-service.log 2>/dev/null
    echo "✅ Cleaned /tmp logs"
fi
echo ""

# 5. Clean old transcription directories
TRANSCRIPTION_KEEP_DAYS=$((KEEP_DAYS * 4))  # Keep transcriptions longer (30 days default)
echo "5️⃣  Cleaning old transcription directories (older than $TRANSCRIPTION_KEEP_DAYS days)..."
delete_dirs "storage/transcriptions" "old transcription directories"
echo ""

# 6. Clean old WAV files
echo "6️⃣  Cleaning old WAV files (older than $KEEP_DAYS days)..."
delete_files "storage" "old WAV files" -name "*.wav"
echo ""

# 7. Aggressive cleanup (if enabled)
if [ "$AGGRESSIVE" = true ]; then
    echo "7️⃣  Aggressive cleanup..."
    
    # Clean all temp files regardless of age
    if [ "$DRY_RUN" = true ]; then
        echo "🔍 [DRY RUN] Would clean: all temp files"
        find temp -type f 2>/dev/null | wc -l | xargs echo "   Files found:"
    else
        rm -rf temp/* 2>/dev/null
        echo "✅ Cleaned all temp files"
    fi
    
    # Clean old SQLite backups
    if [ "$DRY_RUN" = true ]; then
        echo "🔍 [DRY RUN] Would clean: old SQLite backups"
        find storage -name "*.db-*" -mtime +$KEEP_DAYS 2>/dev/null | wc -l | xargs echo "   Files found:"
    else
        find storage -name "*.db-*" -mtime +$KEEP_DAYS -delete 2>/dev/null
        echo "✅ Cleaned old SQLite backups"
    fi
    echo ""
fi

# Show storage after cleanup
echo "📊 Storage After Cleanup:"
df -h /workspace | tail -1
echo ""

# Show directory sizes
echo "📁 Directory Sizes:"
du -sh uploads storage temp logs 2>/dev/null | sort -h
echo ""

echo "✅ Cleanup complete!"

