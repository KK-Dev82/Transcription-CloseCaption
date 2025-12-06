#!/bin/bash

# Script สำหรับเตรียม Proof-of-Concept: aio-pika Migration
# เก็บ worker เดิม (pika) ไว้และเตรียมโครงสร้างสำหรับ worker ใหม่

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKERS_DIR="$PROJECT_DIR/app/workers"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔄 Preparing Proof-of-Concept: aio-pika Migration          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

cd "$PROJECT_DIR"

# Step 1: Backup original worker
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Step 1: Backup original worker..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "$WORKERS_DIR/video_worker.py" ]; then
    if [ -f "$WORKERS_DIR/video_worker_pika.py" ]; then
        echo "⚠️  video_worker_pika.py มีอยู่แล้ว"
        read -p "ต้องการ overwrite หรือไม่? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ ข้ามการ backup"
        else
            cp "$WORKERS_DIR/video_worker.py" "$WORKERS_DIR/video_worker_pika.py"
            echo "✅ Backup สำเร็จ: video_worker.py → video_worker_pika.py"
        fi
    else
        cp "$WORKERS_DIR/video_worker.py" "$WORKERS_DIR/video_worker_pika.py"
        echo "✅ Backup สำเร็จ: video_worker.py → video_worker_pika.py"
    fi
else
    echo "❌ ไม่พบ video_worker.py"
    exit 1
fi

# Step 2: Rename class in video_worker_pika.py
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Step 2: Rename class in video_worker_pika.py..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "$WORKERS_DIR/video_worker_pika.py" ]; then
    # Use sed to replace class name (careful with exact match)
    if grep -q "^class VideoWorker:" "$WORKERS_DIR/video_worker_pika.py"; then
        sed -i.bak 's/^class VideoWorker:/class VideoWorkerPika:/' "$WORKERS_DIR/video_worker_pika.py"
        rm -f "$WORKERS_DIR/video_worker_pika.py.bak"
        echo "✅ Rename class: VideoWorker → VideoWorkerPika"
    elif grep -q "^class VideoWorkerPika:" "$WORKERS_DIR/video_worker_pika.py"; then
        echo "✅ Class already renamed to VideoWorkerPika"
    else
        echo "⚠️  ไม่พบ class VideoWorker ในไฟล์"
    fi
    
    # Update main() function comment
    if grep -q '"""Main function สำหรับรัน worker"""' "$WORKERS_DIR/video_worker_pika.py"; then
        sed -i.bak 's/"""Main function สำหรับรัน worker"""/"""Main function สำหรับรัน worker (pika version)"""/' "$WORKERS_DIR/video_worker_pika.py"
        rm -f "$WORKERS_DIR/video_worker_pika.py.bak"
        echo "✅ Update main() function comment"
    fi
else
    echo "❌ ไม่พบ video_worker_pika.py"
    exit 1
fi

# Step 3: Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Preparation Complete                                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📁 Files:"
echo "   - $WORKERS_DIR/video_worker_pika.py (backup of original)"
echo ""
echo "📝 Next Steps:"
echo "   1. Create video_worker_async.py (async worker)"
echo "   2. Create video_worker.py (wrapper)"
echo "   3. Update requirements.txt (already done)"
echo "   4. Test both workers"
echo ""

