#!/usr/bin/env bash
# Script สำหรับติดตาม Transcription Progress

TASK_ID="${1:-69d75e8f-2ae7-448b-ba3e-325980674ee8}"
BASE_URL="${2:-http://localhost:8010}"

echo "📊 Monitoring Transcription Task: $TASK_ID"
echo "=========================================="
echo ""

while true; do
    RESPONSE=$(curl -s "${BASE_URL}/api/tasks/${TASK_ID}" 2>/dev/null)
    
    if [ $? -eq 0 ] && echo "$RESPONSE" | grep -q "status"; then
        STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null)
        PROGRESS=$(echo "$RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('progress', 0))" 2>/dev/null)
        
        echo -ne "\r⏳ Status: $STATUS | Progress: $PROGRESS%"
        
        if [ "$STATUS" = "completed" ]; then
            echo ""
            echo ""
            echo "✅ Transcription Completed!"
            echo "=========================================="
            echo "$RESPONSE" | python3 -m json.tool 2>/dev/null | head -100
            break
        elif [ "$STATUS" = "failed" ]; then
            echo ""
            echo ""
            echo "❌ Transcription Failed!"
            echo "$RESPONSE" | python3 -m json.tool 2>/dev/null
            break
        fi
    else
        echo -ne "\r❌ Cannot connect to API..."
    fi
    
    sleep 5
done

