#!/bin/bash
# Monitor Resources: GPU, CPU, RAM
# Usage: ./scripts/monitor_resources.sh <output_dir> <duration_seconds>

OUTPUT_DIR="${1:-/tmp/resource_logs}"
DURATION="${2:-600}"  # default 10 minutes
INTERVAL=2  # seconds between samples

mkdir -p "$OUTPUT_DIR"

echo "🔍 Starting resource monitoring..."
echo "   Output: $OUTPUT_DIR"
echo "   Duration: $DURATION seconds"
echo "   Interval: $INTERVAL seconds"
echo ""

# Files
GPU_LOG="$OUTPUT_DIR/gpu.log"
CPU_LOG="$OUTPUT_DIR/cpu.log"
MEM_LOG="$OUTPUT_DIR/memory.log"
SUMMARY_LOG="$OUTPUT_DIR/summary.log"

# Initialize files
echo "timestamp,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu" > "$GPU_LOG"
echo "timestamp,pid,user,cpu,mem,command" > "$CPU_LOG"
echo "timestamp,total,used,free,available,percent" > "$MEM_LOG"

start_time=$(date +%s)
end_time=$((start_time + DURATION))
sample_count=0

echo "📊 Monitoring started at $(date)" > "$SUMMARY_LOG"
echo "   Duration: $DURATION seconds" >> "$SUMMARY_LOG"
echo "   Interval: $INTERVAL seconds" >> "$SUMMARY_LOG"
echo "" >> "$SUMMARY_LOG"

while [ $(date +%s) -lt $end_time ]; do
    current_time=$(date +%s)
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    elapsed=$((current_time - start_time))
    
    # GPU monitoring (nvidia-smi)
    if command -v nvidia-smi &> /dev/null; then
        gpu_data=$(nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ ! -z "$gpu_data" ]; then
            echo "$timestamp,$gpu_data" >> "$GPU_LOG"
        fi
    fi
    
    # CPU monitoring (top)
    top_data=$(top -bn1 | grep -E "^%Cpu|^%Mem" | head -2)
    if [ ! -z "$top_data" ]; then
        cpu_percent=$(echo "$top_data" | grep "%Cpu" | awk '{print $2}' | sed 's/%us,//')
        mem_percent=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
        echo "$timestamp,$cpu_percent,$mem_percent" >> "$CPU_LOG"
    fi
    
    # Memory monitoring (free)
    mem_data=$(free -h | grep Mem | awk '{print $2","$3","$4","$7}')
    mem_percent=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    echo "$timestamp,$mem_data,$mem_percent" >> "$MEM_LOG"
    
    # Top processes (CPU/RAM)
    if [ $((sample_count % 15)) -eq 0 ]; then  # Every 30 seconds
        top_procs=$(top -bn1 | head -20 | tail -15)
        echo "[$timestamp] Top processes:" >> "$SUMMARY_LOG"
        echo "$top_procs" >> "$SUMMARY_LOG"
        echo "" >> "$SUMMARY_LOG"
    fi
    
    sample_count=$((sample_count + 1))
    
    # Progress
    if [ $((sample_count % 30)) -eq 0 ]; then
        progress=$((elapsed * 100 / DURATION))
        echo "⏱️  Progress: ${progress}% (${elapsed}s/${DURATION}s)"
    fi
    
    sleep $INTERVAL
done

echo "✅ Monitoring completed at $(date)" >> "$SUMMARY_LOG"
echo "   Total samples: $sample_count" >> "$SUMMARY_LOG"

# Generate statistics
echo "" >> "$SUMMARY_LOG"
echo "📊 Statistics:" >> "$SUMMARY_LOG"
echo "   GPU:" >> "$SUMMARY_LOG"
if [ -f "$GPU_LOG" ] && [ $(wc -l < "$GPU_LOG") -gt 1 ]; then
    awk -F',' 'NR>1 {gpu_sum+=$2; mem_sum+=$3; power_sum+=$6; count++} END {printf "      Avg GPU: %.1f%%\n      Avg Memory: %.1f%%\n      Avg Power: %.1fW\n", gpu_sum/count, mem_sum/count, power_sum/count}' "$GPU_LOG" >> "$SUMMARY_LOG"
fi
echo "   CPU/Memory:" >> "$SUMMARY_LOG"
if [ -f "$CPU_LOG" ] && [ $(wc -l < "$CPU_LOG") -gt 1 ]; then
    awk -F',' 'NR>1 {cpu_sum+=$3; count++} END {printf "      Avg CPU: %.1f%%\n", cpu_sum/count}' "$CPU_LOG" >> "$SUMMARY_LOG"
fi
if [ -f "$MEM_LOG" ] && [ $(wc -l < "$MEM_LOG") -gt 1 ]; then
    awk -F',' 'NR>1 {mem_sum+=$6; count++} END {printf "      Avg Memory: %.1f%%\n", mem_sum/count}' "$MEM_LOG" >> "$SUMMARY_LOG"
fi

echo ""
echo "✅ Monitoring completed!"
echo "   Logs saved to: $OUTPUT_DIR"
echo "   Files:"
echo "      - gpu.log"
echo "      - cpu.log"
echo "      - memory.log"
echo "      - summary.log"
