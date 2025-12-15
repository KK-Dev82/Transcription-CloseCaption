#!/bin/bash
# Comprehensive Resource Check Script
# ตรวจสอบ logs, resources, และ system status อย่างละเอียด

set -e

SSH_HOST="${1:-4000-ada-sc}"
PROJECT_DIR="/workspace/transcription-close-caption-service"

echo "=========================================="
echo "🔍 Comprehensive Resource Check"
echo "Server: $SSH_HOST"
echo "Time: $(date)"
echo "=========================================="
echo ""

# Function to run command on remote server
run_remote() {
    ssh "$SSH_HOST" "$@"
}

echo "📊 1. SYSTEM RESOURCES"
echo "----------------------------------------"
run_remote "
echo '--- CPU Usage ---'
top -bn1 | grep 'Cpu(s)' | head -1
echo ''
echo '--- Memory Usage ---'
free -h
echo ''
echo '--- Disk Usage ---'
df -h | grep -E '^/dev|Filesystem'
echo ''
echo '--- Load Average ---'
uptime
"

echo ""
echo "🎮 2. GPU RESOURCES"
echo "----------------------------------------"
run_remote "
if command -v nvidia-smi &> /dev/null; then
    echo '--- GPU Status ---'
    nvidia-smi --query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits
    echo ''
    echo '--- GPU Processes ---'
    nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader
else
    echo '⚠️  nvidia-smi not found'
fi
"

echo ""
echo "🔄 3. SERVICE STATUS"
echo "----------------------------------------"
run_remote "
cd $PROJECT_DIR 2>/dev/null || cd /workspace/transcription-service 2>/dev/null || echo '⚠️  Project directory not found'
echo '--- Python Processes ---'
ps aux | grep -E 'uvicorn|python.*main|python.*worker' | grep -v grep | head -10
echo ''
echo '--- Service Health ---'
curl -s http://localhost:8010/health 2>/dev/null || curl -s http://localhost:8001/health 2>/dev/null || echo '⚠️  Service not responding'
"

echo ""
echo "💾 4. STORAGE CONFIGURATION"
echo "----------------------------------------"
run_remote "
cd $PROJECT_DIR 2>/dev/null || cd /workspace/transcription-service 2>/dev/null || echo '⚠️  Project directory not found'
echo '--- Storage Type ---'
grep -E 'STORAGE_TYPE|SQLITE_DB_PATH|JSON_STORAGE_DIR' .env 2>/dev/null || echo '⚠️  .env file not found'
echo ''
echo '--- SQLite Database ---'
if [ -f storage/database.db ]; then
    echo '✅ SQLite database exists'
    ls -lh storage/database.db
    echo ''
    echo '--- Database Size ---'
    sqlite3 storage/database.db 'SELECT COUNT(*) as total_tasks FROM transcriptions;' 2>/dev/null || echo '⚠️  Cannot query database'
    echo ''
    echo '--- Recent Tasks (last 5) ---'
    sqlite3 storage/database.db 'SELECT task_id, status, created_at, updated_at FROM transcriptions ORDER BY updated_at DESC LIMIT 5;' 2>/dev/null || echo '⚠️  Cannot query database'
else
    echo '⚠️  SQLite database not found'
fi
echo ''
echo '--- JSON Storage ---'
if [ -d storage/transcriptions ]; then
    echo '✅ JSON storage directory exists'
    echo 'Total task directories:'
    ls -1 storage/transcriptions 2>/dev/null | wc -l
else
    echo '⚠️  JSON storage directory not found'
fi
"

echo ""
echo "📋 5. RABBITMQ QUEUE STATUS"
echo "----------------------------------------"
run_remote "
cd $PROJECT_DIR 2>/dev/null || cd /workspace/transcription-service 2>/dev/null || echo '⚠️  Project directory not found'
if command -v rabbitmqctl &> /dev/null; then
    echo '--- Queue Status ---'
    rabbitmqctl list_queues name messages consumers 2>/dev/null | grep -E 'transcription|audio|chunk' || echo '⚠️  Cannot query RabbitMQ'
else
    echo '⚠️  rabbitmqctl not found'
    echo '--- RabbitMQ Process ---'
    ps aux | grep rabbitmq | grep -v grep || echo '⚠️  RabbitMQ not running'
fi
"

echo ""
echo "📝 6. RECENT LOGS (Last 50 lines)"
echo "----------------------------------------"
run_remote "
cd $PROJECT_DIR 2>/dev/null || cd /workspace/transcription-service 2>/dev/null || echo '⚠️  Project directory not found'
echo '--- API Service Logs ---'
if [ -f /tmp/transcription-service.log ]; then
    tail -50 /tmp/transcription-service.log
elif [ -f logs/api.log ]; then
    tail -50 logs/api.log
else
    echo '⚠️  API logs not found'
fi
echo ''
echo '--- Worker Logs ---'
if [ -f /tmp/video-worker.log ]; then
    tail -50 /tmp/video-worker.log
elif [ -f logs/worker.log ]; then
    tail -50 logs/worker.log
else
    echo '⚠️  Worker logs not found'
fi
"

echo ""
echo "⚠️  7. ERROR LOGS (Last 20 lines)"
echo "----------------------------------------"
run_remote "
cd $PROJECT_DIR 2>/dev/null || cd /workspace/transcription-service 2>/dev/null || echo '⚠️  Project directory not found'
echo '--- Recent Errors ---'
if [ -f /tmp/transcription-service.log ]; then
    grep -i 'error\|exception\|failed\|timeout' /tmp/transcription-service.log | tail -20
elif [ -f logs/api.log ]; then
    grep -i 'error\|exception\|failed\|timeout' logs/api.log | tail -20
else
    echo '⚠️  Logs not found'
fi
"

echo ""
echo "🔧 8. ENVIRONMENT VARIABLES"
echo "----------------------------------------"
run_remote "
cd $PROJECT_DIR 2>/dev/null || cd /workspace/transcription-service 2>/dev/null || echo '⚠️  Project directory not found'
echo '--- Key Environment Variables ---'
env | grep -E 'STORAGE_TYPE|GPU_CONCURRENCY|WHISPER_BATCH_SIZE|TRANSCRIPTION_MAX_WORKERS|MAX_QUEUE|RABBITMQ' | sort
"

echo ""
echo "📈 9. RECENT TASK STATISTICS"
echo "----------------------------------------"
run_remote "
cd $PROJECT_DIR 2>/dev/null || cd /workspace/transcription-service 2>/dev/null || echo '⚠️  Project directory not found'
if [ -f storage/database.db ]; then
    echo '--- Task Status Summary ---'
    sqlite3 storage/database.db 'SELECT status, COUNT(*) as count FROM transcriptions GROUP BY status;' 2>/dev/null || echo '⚠️  Cannot query database'
    echo ''
    echo '--- Tasks by Date (Last 7 days) ---'
    sqlite3 storage/database.db \"SELECT DATE(created_at) as date, COUNT(*) as count FROM transcriptions WHERE created_at >= datetime('now', '-7 days') GROUP BY DATE(created_at) ORDER BY date DESC;\" 2>/dev/null || echo '⚠️  Cannot query database'
fi
"

echo ""
echo "🌐 10. NETWORK & PORTS"
echo "----------------------------------------"
run_remote "
echo '--- Listening Ports ---'
netstat -tlnp 2>/dev/null | grep -E '8010|8001|5672|15672' || ss -tlnp 2>/dev/null | grep -E '8010|8001|5672|15672' || echo '⚠️  Cannot check ports'
"

echo ""
echo "=========================================="
echo "✅ Resource Check Complete"
echo "=========================================="

