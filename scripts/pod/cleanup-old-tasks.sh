#!/bin/bash
# Script สำหรับ Cleanup Tasks เก่าที่ค้างมานาน
# Mark tasks ที่ค้างมานานกว่า X ชั่วโมงเป็น failed

set -e

PROJECT_DIR="/workspace/transcription-service"
MAX_AGE_HOURS="${1:-24}"  # Default: 24 hours
MAX_AGE_SECONDS=$((MAX_AGE_HOURS * 3600))

echo "🧹 Cleaning up old tasks (older than $MAX_AGE_HOURS hours)..."

STORAGE_DIR="$PROJECT_DIR/storage/transcriptions"
if [ ! -d "$STORAGE_DIR" ]; then
    echo "❌ Storage directory not found: $STORAGE_DIR"
    exit 1
fi

cleaned=0
failed=0

for task_dir in "$STORAGE_DIR"/*/; do
    if [ ! -d "$task_dir" ]; then
        continue
    fi
    
    task_id=$(basename "$task_dir")
    metadata_file="$task_dir/metadata.json"
    
    if [ ! -f "$metadata_file" ]; then
        continue
    fi
    
    # Get task status and age
    status=$(python3 -c "import json; d=json.load(open('$metadata_file')); print(d.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    
    # Skip if already completed or failed
    if [ "$status" = "completed" ] || [ "$status" = "failed" ]; then
        continue
    fi
    
    # Check file age
    mtime=$(stat -c %Y "$metadata_file" 2>/dev/null || stat -f %m "$metadata_file" 2>/dev/null)
    now=$(date +%s)
    age=$((now - mtime))
    
    if [ $age -gt $MAX_AGE_SECONDS ]; then
        age_hours=$((age / 3600))
        echo "  Marking $task_id as failed (age: ${age_hours}h, status: $status)"
        
        # Update metadata to mark as failed
        python3 << PYTHON_SCRIPT
import json
import sys

metadata_file = "$metadata_file"
try:
    with open(metadata_file, 'r') as f:
        data = json.load(f)
    
    data['status'] = 'failed'
    data['error_message'] = f'Task timeout: exceeded {age_hours} hours (cleaned up)'
    data['cleaned_at'] = $(date +%s)
    
    with open(metadata_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Marked {task_id} as failed")
    sys.exit(0)
except Exception as e:
    print(f"❌ Error updating {task_id}: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT
        
        if [ $? -eq 0 ]; then
            cleaned=$((cleaned + 1))
        else
            failed=$((failed + 1))
        fi
    fi
done

echo ""
echo "✅ Cleanup completed:"
echo "  - Cleaned: $cleaned tasks"
echo "  - Failed: $failed tasks"
