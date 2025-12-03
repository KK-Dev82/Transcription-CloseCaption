#!/bin/bash
# Script สำหรับตรวจสอบปัญหา Connection Issues (Server disconnected, Connection reset)
#
# วิธีใช้งาน:
#   ssh pytorch-pod "bash -s" < scripts/pod/check-connection-issues.sh
#   หรือ
#   bash scripts/pod/check-connection-issues.sh (บน Pod)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PROJECT_DIR="/workspace/transcription-service"
LOG_FILE="/tmp/transcription-service.log"
SERVICE_PORT="8010"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 Connection Issues Diagnostic Tool                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Checking for: Server disconnected, Connection reset by peer"
echo ""

cd "$PROJECT_DIR" 2>/dev/null || echo "⚠️  Project directory not found, continuing..."

# 1. Service Status
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 1️⃣  Service Status                                          │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

PID=$(pgrep -f "uvicorn.*app.main:app.*${SERVICE_PORT}" | head -1)
if [ ! -z "$PID" ]; then
    echo -e "${GREEN}✅ Service is RUNNING${NC}"
    echo "   PID: $PID"
    
    # Check CPU and Memory
    if command -v ps > /dev/null; then
        CPU=$(ps -p $PID -o %cpu --no-headers 2>/dev/null | xargs || echo "N/A")
        MEM=$(ps -p $PID -o %mem --no-headers 2>/dev/null | xargs || echo "N/A")
        RSS=$(ps -p $PID -o rss --no-headers 2>/dev/null | xargs || echo "N/A")
        echo "   CPU: ${CPU}%"
        echo "   Memory: ${MEM}% (RSS: ${RSS} KB)"
    fi
    
    # Check if service is responsive
    if curl -s -f http://localhost:${SERVICE_PORT}/health > /dev/null 2>&1; then
        echo -e "   ${GREEN}✅ Health check: OK${NC}"
    else
        echo -e "   ${RED}❌ Health check: FAILED${NC}"
    fi
else
    echo -e "${RED}❌ Service is NOT running${NC}"
fi
echo ""

# 2. Active Connections
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 2️⃣  Active Connections (Port ${SERVICE_PORT})                │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if command -v netstat > /dev/null; then
    CONN_COUNT=$(netstat -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep ESTABLISHED | wc -l || echo "0")
    echo "   Established connections: ${CONN_COUNT}"
    
    if [ "$CONN_COUNT" -gt 0 ]; then
        echo ""
        echo "   Top connections:"
        netstat -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep ESTABLISHED | head -10 | sed 's/^/   | /'
    fi
    
    TIME_WAIT=$(netstat -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep TIME_WAIT | wc -l || echo "0")
    if [ "$TIME_WAIT" -gt 0 ]; then
        echo ""
        echo -e "   ${YELLOW}⚠️  TIME_WAIT connections: ${TIME_WAIT}${NC}"
        echo "   (These are recently closed connections)"
    fi
elif command -v ss > /dev/null; then
    CONN_COUNT=$(ss -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep ESTAB | wc -l || echo "0")
    echo "   Established connections: ${CONN_COUNT}"
    
    if [ "$CONN_COUNT" -gt 0 ]; then
        echo ""
        echo "   Top connections:"
        ss -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep ESTAB | head -10 | sed 's/^/   | /'
    fi
else
    echo "   ⚠️  netstat/ss not available"
fi
echo ""

# 3. System Resources
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 3️⃣  System Resources                                         │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

# Memory
if command -v free > /dev/null; then
    TOTAL_MEM=$(free -h | grep Mem | awk '{print $2}')
    USED_MEM=$(free -h | grep Mem | awk '{print $3}')
    AVAIL_MEM=$(free -h | grep Mem | awk '{print $7}')
    MEM_PERCENT=$(free | grep Mem | awk '{printf "%.1f", ($3/$2) * 100.0}')
    
    echo "   Memory: ${USED_MEM} / ${TOTAL_MEM} used (${MEM_PERCENT}%)"
    echo "   Available: ${AVAIL_MEM}"
    
    if (( $(echo "$MEM_PERCENT > 90" | bc -l) )); then
        echo -e "   ${RED}❌ Memory usage is HIGH (>90%)${NC}"
    elif (( $(echo "$MEM_PERCENT > 80" | bc -l) )); then
        echo -e "   ${YELLOW}⚠️  Memory usage is HIGH (>80%)${NC}"
    else
        echo -e "   ${GREEN}✅ Memory usage is OK${NC}"
    fi
fi

# CPU Load
if [ -f /proc/loadavg ]; then
    LOAD=$(cat /proc/loadavg | awk '{print $1}')
    CPU_CORES=$(nproc 2>/dev/null || echo "1")
    LOAD_PERCENT=$(echo "scale=0; $LOAD * 100 / $CPU_CORES" | bc 2>/dev/null || echo "0")
    
    echo ""
    echo "   Load Average: ${LOAD} (${CPU_CORES} cores)"
    echo "   Load Percentage: ${LOAD_PERCENT}%"
    
    if (( $(echo "$LOAD_PERCENT > 200" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "   ${RED}❌ System is OVERLOADED (>200%)${NC}"
    elif (( $(echo "$LOAD_PERCENT > 150" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "   ${YELLOW}⚠️  System is HEAVILY LOADED (>150%)${NC}"
    else
        echo -e "   ${GREEN}✅ System load is OK${NC}"
    fi
fi

# File descriptors
if [ ! -z "$PID" ]; then
    FD_COUNT=$(ls -1 /proc/$PID/fd 2>/dev/null | wc -l || echo "0")
    FD_LIMIT=$(ulimit -n 2>/dev/null || echo "1024")
    FD_PERCENT=$(echo "scale=1; $FD_COUNT * 100 / $FD_LIMIT" | bc 2>/dev/null || echo "0")
    
    echo ""
    echo "   File Descriptors: ${FD_COUNT} / ${FD_LIMIT} (${FD_PERCENT}%)"
    
    if (( $(echo "$FD_PERCENT > 80" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "   ${YELLOW}⚠️  File descriptor usage is HIGH (>80%)${NC}"
    fi
fi

echo ""

# 4. Log Analysis - Connection Errors
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 4️⃣  Log Analysis - Connection Errors (Last 1000 lines)       │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(du -h "$LOG_FILE" | cut -f1)
    LOG_LINES=$(wc -l < "$LOG_FILE" 2>/dev/null || echo "0")
    
    echo "   Log file: $LOG_FILE"
    echo "   Size: $LOG_SIZE"
    echo "   Total lines: $LOG_LINES"
    echo ""
    
    # Count errors
    ERROR_COUNT=$(tail -1000 "$LOG_FILE" 2>/dev/null | grep -iE "error|exception|traceback|failed|disconnect|reset" | wc -l || echo "0")
    CONN_ERROR_COUNT=$(tail -1000 "$LOG_FILE" 2>/dev/null | grep -iE "disconnect|connection reset|connection refused|connection error|timeout" | wc -l || echo "0")
    
    echo "   Errors (last 1000 lines): ${ERROR_COUNT}"
    echo "   Connection errors: ${CONN_ERROR_COUNT}"
    echo ""
    
    if [ "$CONN_ERROR_COUNT" -gt 0 ]; then
        echo -e "   ${RED}❌ Connection errors found!${NC}"
        echo ""
        echo "   Recent connection errors:"
        tail -1000 "$LOG_FILE" 2>/dev/null | grep -iE "disconnect|connection reset|connection refused|connection error|timeout" | tail -10 | sed 's/^/   | /' || echo "   (none found)"
    else
        echo -e "   ${GREEN}✅ No recent connection errors${NC}"
    fi
    
    echo ""
    echo "   Recent errors (last 20 lines):"
    tail -1000 "$LOG_FILE" 2>/dev/null | grep -iE "error|exception|traceback|failed" | tail -20 | sed 's/^/   | /' | head -10 || echo "   (no errors found)"
else
    echo -e "   ${YELLOW}⚠️  Log file not found: $LOG_FILE${NC}"
fi
echo ""

# 5. Recent Log Entries
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 5️⃣  Recent Log Entries (Last 30 lines)                      │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LOG_FILE" ]; then
    tail -30 "$LOG_FILE" 2>/dev/null | sed 's/^/   | /' || echo "   (empty)"
else
    echo "   ⚠️  Log file not found"
fi
echo ""

# 6. Network Statistics
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 6️⃣  Network Statistics                                       │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if [ -f /proc/net/sockstat ]; then
    TCP_INUSE=$(grep TCP /proc/net/sockstat | awk '{print $3}')
    TCP_ORPHAN=$(grep TCP /proc/net/sockstat | awk '{print $7}')
    TCP_TW=$(grep TCP /proc/net/sockstat | awk '{print $9}')
    
    echo "   TCP sockets in use: ${TCP_INUSE}"
    echo "   TCP orphan: ${TCP_ORPHAN}"
    echo "   TCP time wait: ${TCP_TW}"
    
    if [ ! -z "$TCP_ORPHAN" ] && [ "$TCP_ORPHAN" -gt 100 ]; then
        echo -e "   ${YELLOW}⚠️  High number of orphan sockets (>100)${NC}"
    fi
    
    if [ ! -z "$TCP_TW" ] && [ "$TCP_TW" -gt 1000 ]; then
        echo -e "   ${YELLOW}⚠️  High number of TIME_WAIT sockets (>1000)${NC}"
        echo "   (May indicate connection churn)"
    fi
fi

if [ -f /proc/net/sockstat6 ]; then
    TCP6_INUSE=$(grep TCP /proc/net/sockstat6 | awk '{print $3}')
    if [ ! -z "$TCP6_INUSE" ] && [ "$TCP6_INUSE" -gt 0 ]; then
        echo "   TCP6 sockets in use: ${TCP6_INUSE}"
    fi
fi
echo ""

# 7. Recommendations
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 📊 Diagnostic Summary & Recommendations                      │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

RECOMMENDATIONS=()

# Check if service is running
if [ -z "$PID" ]; then
    RECOMMENDATIONS+=("❌ Service is not running - Start service: bash scripts/pod/start-service-daemon.sh")
fi

# Check memory
if [ ! -z "$MEM_PERCENT" ] && (( $(echo "$MEM_PERCENT > 90" | bc -l 2>/dev/null || echo "0") )); then
    RECOMMENDATIONS+=("⚠️  Memory usage is very high - Consider reducing concurrent requests or increasing memory")
fi

# Check connections
if [ ! -z "$CONN_COUNT" ] && [ "$CONN_COUNT" -gt 50 ]; then
    RECOMMENDATIONS+=("⚠️  High number of concurrent connections (${CONN_COUNT}) - May need to limit concurrent requests")
fi

# Check errors
if [ "$CONN_ERROR_COUNT" -gt 10 ]; then
    RECOMMENDATIONS+=("❌ High number of connection errors (${CONN_ERROR_COUNT}) - Check service stability")
    RECOMMENDATIONS+=("💡 Consider: 1) Restart service 2) Check logs for patterns 3) Reduce concurrent requests")
fi

# Check TIME_WAIT
if [ ! -z "$TCP_TW" ] && [ "$TCP_TW" -gt 1000 ]; then
    RECOMMENDATIONS+=("⚠️  High TIME_WAIT sockets (${TCP_TW}) - May indicate connection churn or need to tune TCP settings")
fi

if [ ${#RECOMMENDATIONS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ No critical issues detected${NC}"
    echo ""
    echo "💡 If you're still experiencing connection issues:"
    echo "   1. Check client-side network settings"
    echo "   2. Check firewall/security groups"
    echo "   3. Monitor logs in real-time: tail -f $LOG_FILE"
    echo "   4. Consider reducing concurrent request rate"
else
    echo "Issues detected:"
    for rec in "${RECOMMENDATIONS[@]}"; do
        echo "   • $rec"
    done
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Diagnostic complete!"
echo ""
echo "💡 Useful commands:"
echo "   View logs: tail -f $LOG_FILE"
echo "   Check status: bash scripts/pod/check-service-status.sh"
echo "   Restart service: bash scripts/pod/start-service-daemon.sh"
echo ""

