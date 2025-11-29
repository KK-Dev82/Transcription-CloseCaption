#!/bin/bash

# Script สำหรับตรวจสอบ CPU และ RAM ของ Staging Server
# ใช้เพื่อปรับ Resource Worker ได้ถูกต้อง
# Usage: ./scripts/check-staging-resources.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  📊 Staging Server Resource Monitoring${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# 1. System Information
echo -e "${CYAN}🖥️  System Information:${NC}"
echo "────────────────────────────────────────────────────────"
echo -n "Hostname: "
hostname || echo "N/A"
echo -n "OS: "
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "$PRETTY_NAME"
else
    uname -s
fi
echo -n "Kernel: "
uname -r
echo -n "Architecture: "
uname -m
echo ""

# 2. CPU Information
echo -e "${CYAN}⚙️  CPU Information:${NC}"
echo "────────────────────────────────────────────────────────"
CPU_CORES=$(nproc 2>/dev/null || echo "N/A")
echo "Total CPU Cores: $CPU_CORES"

if [ -f /proc/cpuinfo ]; then
    CPU_MODEL=$(grep -m 1 "model name" /proc/cpuinfo | cut -d ':' -f 2 | sed 's/^ *//' || echo "N/A")
    echo "CPU Model: $CPU_MODEL"
fi

# CPU Usage (1 second average)
if command -v top &> /dev/null; then
    echo "CPU Usage (current):"
    top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print "  Idle: " 100-$1 "% | Used: " $1 "%"}'
fi

# Load Average
if [ -f /proc/loadavg ]; then
    LOAD=$(cat /proc/loadavg | awk '{print $1 " " $2 " " $3}')
    echo "Load Average (1m, 5m, 15m): $LOAD"
    
    # Calculate load per core
    if [ "$CPU_CORES" != "N/A" ]; then
        LOAD_1M=$(cat /proc/loadavg | awk '{print $1}')
        LOAD_PER_CORE=$(echo "$LOAD_1M / $CPU_CORES" | bc -l 2>/dev/null | awk '{printf "%.2f", $1}')
        echo "  Load per Core (1m): $LOAD_PER_CORE"
        
        if (( $(echo "$LOAD_PER_CORE > 1.0" | bc -l 2>/dev/null || echo 0) )); then
            echo -e "  ${YELLOW}⚠️  Warning: Load average is high!${NC}"
        fi
    fi
fi
echo ""

# 3. Memory Information
echo -e "${CYAN}💾 Memory Information:${NC}"
echo "────────────────────────────────────────────────────────"
if [ -f /proc/meminfo ]; then
    TOTAL_MEM=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    FREE_MEM=$(grep MemFree /proc/meminfo | awk '{print $2}')
    AVAILABLE_MEM=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
    CACHED_MEM=$(grep -i "Cached:" /proc/meminfo | head -1 | awk '{print $2}')
    BUFFERS_MEM=$(grep Buffers /proc/meminfo | awk '{print $2}')
    
    TOTAL_MEM_GB=$(echo "scale=2; $TOTAL_MEM / 1024 / 1024" | bc)
    FREE_MEM_GB=$(echo "scale=2; $FREE_MEM / 1024 / 1024" | bc)
    AVAILABLE_MEM_GB=$(echo "scale=2; $AVAILABLE_MEM / 1024 / 1024" | bc)
    USED_MEM_GB=$(echo "scale=2; ($TOTAL_MEM - $FREE_MEM - $CACHED_MEM - $BUFFERS_MEM) / 1024 / 1024" | bc)
    USED_PERCENT=$(echo "scale=1; ($TOTAL_MEM - $FREE_MEM - $CACHED_MEM - $BUFFERS_MEM) * 100 / $TOTAL_MEM" | bc)
    
    echo "Total Memory: ${TOTAL_MEM_GB} GB"
    echo "Used Memory: ${USED_MEM_GB} GB ($USED_PERCENT%)"
    echo "Available Memory: ${AVAILABLE_MEM_GB} GB"
    echo "Free Memory: ${FREE_MEM_GB} GB"
    
    # Memory warning
    if (( $(echo "$USED_PERCENT > 80" | bc -l) )); then
        echo -e "  ${RED}⚠️  Warning: Memory usage is high (>80%)!${NC}"
    elif (( $(echo "$USED_PERCENT > 60" | bc -l) )); then
        echo -e "  ${YELLOW}⚠️  Warning: Memory usage is moderate (>60%)${NC}"
    fi
fi

# Swap Information
if [ -f /proc/meminfo ]; then
    SWAP_TOTAL=$(grep SwapTotal /proc/meminfo | awk '{print $2}')
    SWAP_FREE=$(grep SwapFree /proc/meminfo | awk '{print $2}')
    if [ "$SWAP_TOTAL" != "0" ]; then
        SWAP_USED=$(echo "scale=2; ($SWAP_TOTAL - $SWAP_FREE) / 1024 / 1024" | bc)
        SWAP_TOTAL_GB=$(echo "scale=2; $SWAP_TOTAL / 1024 / 1024" | bc)
        SWAP_PERCENT=$(echo "scale=1; ($SWAP_TOTAL - $SWAP_FREE) * 100 / $SWAP_TOTAL" | bc)
        echo ""
        echo "Swap Total: ${SWAP_TOTAL_GB} GB"
        echo "Swap Used: ${SWAP_USED} GB ($SWAP_PERCENT%)"
        
        if (( $(echo "$SWAP_PERCENT > 50" | bc -l) )); then
            echo -e "  ${RED}⚠️  Warning: Swap usage is high!${NC}"
        fi
    fi
fi
echo ""

# 4. Disk Information
echo -e "${CYAN}💿 Disk Information:${NC}"
echo "────────────────────────────────────────────────────────"
if command -v df &> /dev/null; then
    df -h / | tail -1 | awk '{print "Root Filesystem: " $4 " available out of " $2 " (" $5 " used)"}'
    df -h / | tail -1 | awk '{print "Mount point: " $6}'
    
    # Check disk usage percentage
    DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -gt 90 ]; then
        echo -e "  ${RED}⚠️  Warning: Disk usage is critical (>90%)!${NC}"
    elif [ "$DISK_USAGE" -gt 80 ]; then
        echo -e "  ${YELLOW}⚠️  Warning: Disk usage is high (>80%)${NC}"
    fi
fi
echo ""

# 5. Docker Containers Resource Usage
echo -e "${CYAN}🐳 Docker Containers Resource Usage:${NC}"
echo "────────────────────────────────────────────────────────"
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo "Running Containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "  No running containers"
    
    echo ""
    echo "Container Resource Statistics (last 10 seconds):"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || echo "  Unable to get stats"
else
    echo "  Docker is not available"
fi
echo ""

# 6. Recommended Resource Configuration
echo -e "${CYAN}📋 Recommended Resource Configuration:${NC}"
echo "────────────────────────────────────────────────────────"

if [ "$CPU_CORES" != "N/A" ] && [ -f /proc/meminfo ]; then
    TOTAL_MEM=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_MEM_GB=$(echo "scale=2; $TOTAL_MEM / 1024 / 1024" | bc)
    
    # Calculate recommended resources
    # Reserve 20% for system (minimum 1.5GB for system)
    AVAILABLE_CPU=$(echo "scale=1; $CPU_CORES * 0.8" | bc | awk '{printf "%.1f", $1}')
    AVAILABLE_MEM=$(echo "scale=2; $TOTAL_MEM_GB * 0.8" | bc)
    AVAILABLE_MEM_INT=$(echo "scale=0; $AVAILABLE_MEM / 1" | bc)
    
    echo "Available Resources (80% of total, 20% reserved for system):"
    echo "  CPU: ${AVAILABLE_CPU} cores (out of $CPU_CORES)"
    echo "  Memory: ${AVAILABLE_MEM_INT} GB (out of ${TOTAL_MEM_GB} GB total)"
    echo ""
    
    # Adjust configuration based on available resources
    # For small servers (4 cores, <8GB RAM), use lighter configuration
    if [ "$AVAILABLE_MEM_INT" -lt 8 ]; then
        echo -e "${YELLOW}⚠️  Small server detected - Using lightweight configuration${NC}"
        echo ""
        
        # Lightweight configuration optimized for 4 cores / ~6GB available
        # Total: 3.0 CPU, 6GB RAM (within limits - perfect fit!)
        API_CPU="1.0"
        API_MEM=1.5
        
        WORKER_COUNT=2
        WORKER_CPU="0.4"
        WORKER_MEM=1
        
        WHISPER_CPU="1.0"
        WHISPER_MEM=1.5
        
        REDIS_CPU="0.2"
        REDIS_MEM=1
        
        echo "Recommended Lightweight Configuration:"
        echo "  API Service:"
        echo "    cpus: '${API_CPU}'"
        echo "    memory: ${API_MEM}G"
        echo ""
        echo "  Video Workers ($WORKER_COUNT workers):"
        echo "    cpus: '${WORKER_CPU}' per worker"
        echo "    memory: ${WORKER_MEM}G per worker"
        echo ""
        echo "  Whisper Service:"
        echo "    cpus: '${WHISPER_CPU}'"
        echo "    memory: ${WHISPER_MEM}G"
        echo ""
        echo "  Redis:"
        echo "    cpus: '${REDIS_CPU}'"
        echo "    memory: ${REDIS_MEM}G"
        echo ""
        
        TOTAL_CPU_ALLOC=$(echo "scale=1; $API_CPU + ($WORKER_CPU * $WORKER_COUNT) + $WHISPER_CPU + $REDIS_CPU" | bc)
        TOTAL_MEM_ALLOC=$(echo "$API_MEM + ($WORKER_MEM * $WORKER_COUNT) + $WHISPER_MEM + $REDIS_MEM" | bc)
        
    else
        # Standard configuration for larger servers
        API_CPU="2.0"
        API_MEM=6
        
        WORKER_COUNT=3
        WORKER_CPU=$(echo "scale=1; ($AVAILABLE_CPU - 2.0 - 2.0 - 0.5) / $WORKER_COUNT" | bc | awk '{if ($1 < 0.3) print "0.3"; else printf "%.1f", $1}')
        WORKER_MEM=$(echo "scale=0; ($AVAILABLE_MEM_INT - 6 - 8 - 2) / $WORKER_COUNT" | bc | awk '{if ($1 < 1) print "1"; else print $1}')
        
        WHISPER_CPU="2.0"
        WHISPER_MEM=8
        
        REDIS_CPU="0.5"
        REDIS_MEM=2
        
        echo "Recommended Standard Configuration:"
        echo "  API Service:"
        echo "    cpus: '${API_CPU}'"
        echo "    memory: ${API_MEM}G"
        echo ""
        echo "  Video Workers ($WORKER_COUNT workers):"
        echo "    cpus: '${WORKER_CPU}' per worker"
        echo "    memory: ${WORKER_MEM}G per worker"
        echo ""
        echo "  Whisper Service:"
        echo "    cpus: '${WHISPER_CPU}'"
        echo "    memory: ${WHISPER_MEM}G"
        echo ""
        echo "  Redis:"
        echo "    cpus: '${REDIS_CPU}'"
        echo "    memory: ${REDIS_MEM}G"
        echo ""
        
        TOTAL_CPU_ALLOC=$(echo "scale=1; $API_CPU + ($WORKER_CPU * $WORKER_COUNT) + $WHISPER_CPU + $REDIS_CPU" | bc)
        TOTAL_MEM_ALLOC=$(echo "$API_MEM + ($WORKER_MEM * $WORKER_COUNT) + $WHISPER_MEM + $REDIS_MEM" | bc)
    fi
    
    echo "Total Allocated Resources:"
    echo "  CPU: ${TOTAL_CPU_ALLOC} cores (${AVAILABLE_CPU} available)"
    echo "  Memory: ${TOTAL_MEM_ALLOC} GB (${AVAILABLE_MEM_INT} GB available)"
    echo ""
    
    # Check if allocation exceeds available
    CPU_OK=$(echo "$TOTAL_CPU_ALLOC <= $AVAILABLE_CPU" | bc -l)
    MEM_OK=$(echo "$TOTAL_MEM_ALLOC <= $AVAILABLE_MEM_INT" | bc)
    
    if [ "$CPU_OK" -eq 0 ] || [ "$MEM_OK" -eq 0 ]; then
        echo -e "  ${RED}⚠️  Warning: Allocated resources exceed available resources!${NC}"
        echo "  Please reduce worker count or resource allocation"
    else
        CPU_USAGE_PCT=$(echo "scale=1; ($TOTAL_CPU_ALLOC * 100) / $AVAILABLE_CPU" | bc)
        MEM_USAGE_PCT=$(echo "scale=1; ($TOTAL_MEM_ALLOC * 100) / $AVAILABLE_MEM_INT" | bc)
        echo "  Resource Usage:"
        echo "    CPU: ${CPU_USAGE_PCT}% of available"
        echo "    Memory: ${MEM_USAGE_PCT}% of available"
        
        if (( $(echo "$CPU_USAGE_PCT > 90" | bc -l) )) || (( $(echo "$MEM_USAGE_PCT > 90" | bc -l) )); then
            echo -e "  ${YELLOW}⚠️  Warning: Resource usage is high (>90%)${NC}"
        fi
    fi
fi
echo ""

# 7. Top Processes
echo -e "${CYAN}🔝 Top 10 Processes by CPU Usage:${NC}"
echo "────────────────────────────────────────────────────────"
if command -v ps &> /dev/null; then
    ps aux --sort=-%cpu | head -11 | awk '{printf "%-8s %6s %6s%% %10s %s\n", $1, $2, $3, $4, substr($0, index($0,$11))}'
fi
echo ""

echo -e "${CYAN}🔝 Top 10 Processes by Memory Usage:${NC}"
echo "────────────────────────────────────────────────────────"
if command -v ps &> /dev/null; then
    ps aux --sort=-%mem | head -11 | awk '{printf "%-8s %6s %6s%% %10s %s\n", $1, $2, $4, $3, substr($0, index($0,$11))}'
fi
echo ""

echo -e "${GREEN}✅ Resource check completed!${NC}"
echo ""

