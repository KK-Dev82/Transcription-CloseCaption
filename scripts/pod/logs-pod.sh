#!/bin/bash
# Script สำหรับดู Logs ของ Services ทั้งหมด
# วิธีใช้งาน: bash scripts/pod/logs-pod.sh [lines]

LINES=${1:-30}

# Colors
CYAN='\033[0;36m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}📋 Pod Services Logs (last $LINES lines each)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 1. Whisper API Logs
echo -e "${BLUE}📝 1. Whisper API Logs (/tmp/whisper.log)${NC}"
echo "────────────────────────────────────────────────────────────────────────────────"
if [ -f "/tmp/whisper.log" ]; then
    tail -n "$LINES" /tmp/whisper.log
else
    echo -e "${YELLOW}ℹ️  Log file not found${NC}"
fi
echo ""

# 2. Video Worker Logs
echo -e "${BLUE}📝 2. Video Worker Logs (/tmp/video-worker.log)${NC}"
echo "────────────────────────────────────────────────────────────────────────────────"
if [ -f "/tmp/video-worker.log" ]; then
    tail -n "$LINES" /tmp/video-worker.log
else
    echo -e "${YELLOW}ℹ️  Log file not found${NC}"
fi
echo ""

# 3. Main API Logs
echo -e "${BLUE}📝 3. Main API Logs (/tmp/main-api.log)${NC}"
echo "────────────────────────────────────────────────────────────────────────────────"
if [ -f "/tmp/main-api.log" ]; then
    tail -n "$LINES" /tmp/main-api.log
else
    echo -e "${YELLOW}ℹ️  Log file not found${NC}"
fi
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}💡 ดู logs แบบ real-time:${NC}"
echo "   - Whisper: tail -f /tmp/whisper.log"
echo "   - Worker: tail -f /tmp/video-worker.log"  
echo "   - API: tail -f /tmp/main-api.log"
echo ""
