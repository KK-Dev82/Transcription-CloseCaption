#!/bin/bash
# Compact resource monitor: CPU | GPU0 | GPU1 | PWR | RAM (แบบ nvidia-smi dmon แต่รวม CPU/RAM)
#
# Usage:
#   ./scripts/watch_resources.sh [interval_sec] [--log FILE]
#
# คำสั่ง watch (แบบ nvidia-smi dmon — แสดง CPU | GPU0 | GPU1 | PWR | RAM):
#   watch -n 1 './scripts/watch_resources.sh --once'

INTERVAL=1
LOG_FILE=""
MODE="loop"
while [ $# -gt 0 ]; do
    case "$1" in
        --log|-l) LOG_FILE="$2"; shift 2 ;;
        --once|-1) MODE="once"; shift ;;
        [0-9]*) INTERVAL="$1"; shift ;;
        *) shift ;;
    esac
done

# โหมด once: แสดง 1 บรรทัดแล้วจบ (ใช้กับ watch -n 1 '...')
if [ "$MODE" = "once" ]; then
    prev=$(awk '/^cpu /{u=$2+$4; t=$2+$3+$4+$5; print u,t}' /proc/stat 2>/dev/null)
    sleep 1
    curr=$(awk '/^cpu /{u=$2+$4; t=$2+$3+$4+$5; print u,t}' /proc/stat 2>/dev/null)
    cpu=$(echo "$prev $curr" | awk '{du=$3-$1; dt=$4-$2; if(dt>0) printf "%.0f", du/dt*100; else print 0}')
    ram=$(awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} END{printf "%.0f", (t-a)/t*100}' /proc/meminfo 2>/dev/null)
    if command -v nvidia-smi &>/dev/null; then
        g=$(nvidia-smi --query-gpu=utilization.gpu,power.draw --format=csv,noheader,nounits 2>/dev/null)
        g0=$(echo "$g" | sed -n '1p' | cut -d',' -f1 | tr -d ' ')
        g1=$(echo "$g" | sed -n '2p' | cut -d',' -f1 | tr -d ' ')
        pwr=$(echo "$g" | awk -F',' '{s+=$2} END{printf "%.0f", s}')
        [ -z "$g1" ] && g1="-"
    else
        g0="-"; g1="-"; pwr="-"
    fi
    printf "CPU %-5s | GPU0 %-5s | GPU1 %-5s | PWR %-6s | RAM %s%%\n" "${cpu}%" "${g0}%" "${g1}%" "${pwr}W" "$ram"
    exit 0
fi

# เริ่ม log (CSV)
if [ -n "$LOG_FILE" ]; then
    mkdir -p "$(dirname "$LOG_FILE")"
    [ ! -f "$LOG_FILE" ] && echo "timestamp,cpu,gpu0,gpu1,pwr_w,ram_pct" > "$LOG_FILE"
    echo "📝 Logging to: $LOG_FILE"
fi

# Header
printf "%-8s | %-6s | %-6s | %-8s | %-6s\n" "CPU" "GPU0" "GPU1" "PWR" "RAM"
printf "%s\n" "--------|--------|--------|----------|--------"

prev=""
while true; do
    # CPU (%) - ต้องอ่าน 2 ครั้งเพื่อคำนวณ
    curr=$(awk '/^cpu /{u=$2+$4; t=$2+$3+$4+$5; print u,t}' /proc/stat 2>/dev/null)
    if [ -n "$prev" ] && [ -n "$curr" ]; then
        cpu=$(echo "$prev $curr" | awk '{du=$3-$1; dt=$4-$2; if(dt>0) printf "%.0f", du/dt*100; else print 0}')
    else
        cpu="-"
    fi
    prev=$curr
    
    # RAM (%)
    ram=$(awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} END{printf "%.0f", (t-a)/t*100}' /proc/meminfo 2>/dev/null || echo "-")
    
    # GPU0, GPU1, Power (W)
    if command -v nvidia-smi &>/dev/null; then
        gpu_data=$(nvidia-smi --query-gpu=utilization.gpu,power.draw --format=csv,noheader,nounits 2>/dev/null)
        gpu0=$(echo "$gpu_data" | sed -n '1p' | cut -d',' -f1 | tr -d ' ')
        gpu1=$(echo "$gpu_data" | sed -n '2p' | cut -d',' -f1 | tr -d ' ')
        pwr0=$(echo "$gpu_data" | sed -n '1p' | cut -d',' -f2 | tr -d ' ')
        pwr1=$(echo "$gpu_data" | sed -n '2p' | cut -d',' -f2 | tr -d ' ')
        pwr=$(echo "$pwr0 $pwr1" | awk '{printf "%.0f", $1+$2}')
        [ -z "$gpu1" ] && gpu1="-"
    else
        gpu0="-"; gpu1="-"; pwr="-"
    fi
    
    printf "\r%-8s | %-6s | %-6s | %-8s | %-6s  " \
        "${cpu}%" "${gpu0}%" "${gpu1}%" "${pwr}W" "${ram}%"
    
    # บันทึก log (CSV)
    if [ -n "$LOG_FILE" ]; then
        ts=$(date '+%Y-%m-%d %H:%M:%S')
        echo "$ts,$cpu,$gpu0,$gpu1,$pwr,$ram" >> "$LOG_FILE"
    fi
    
    sleep "$INTERVAL"
done
