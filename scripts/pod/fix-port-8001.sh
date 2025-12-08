#!/bin/bash
# Script สำหรับแก้ไขปัญหา Port 8001 ถูกใช้งานอยู่แล้ว
#
# วิธีใช้งาน:
#   bash scripts/pod/fix-port-8001.sh

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "🔧 Fixing Port 8001 Issue"
echo "========================="
echo ""

# Check if port 8001 is in use
print_status "Checking port 8001..."

# Method 1: Check using lsof
if command -v lsof > /dev/null 2>&1; then
    PORT_PID=$(lsof -ti:8001 2>/dev/null || echo "")
    if [ -n "$PORT_PID" ]; then
        print_warning "⚠️  Port 8001 is in use by PID: $PORT_PID"
        PROCESS_INFO=$(ps -p "$PORT_PID" -o comm=,args= 2>/dev/null || echo "unknown")
        print_status "   Process: $PROCESS_INFO"
        echo ""
        read -p "Kill process $PORT_PID? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill "$PORT_PID" 2>/dev/null || kill -9 "$PORT_PID" 2>/dev/null
            sleep 2
            if ! lsof -ti:8001 > /dev/null 2>&1; then
                print_success "✅ Process killed, port 8001 is now free"
            else
                print_error "❌ Failed to kill process"
            fi
        fi
    else
        print_success "✅ Port 8001 is free"
    fi
fi

# Method 2: Check using pgrep for uvicorn
print_status "Checking for uvicorn processes..."
UVICORN_PIDS=$(pgrep -f "python.*uvicorn.*app.main" || echo "")

if [ -n "$UVICORN_PIDS" ]; then
    print_warning "⚠️  Found uvicorn processes:"
    for pid in $UVICORN_PIDS; do
        PROCESS_INFO=$(ps -p "$pid" -o pid=,comm=,args= 2>/dev/null || echo "unknown")
        print_status "   PID $pid: $PROCESS_INFO"
    done
    echo ""
    read -p "Kill all uvicorn processes? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for pid in $UVICORN_PIDS; do
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
            print_status "   Killed PID $pid"
        done
        sleep 2
        print_success "✅ All uvicorn processes killed"
    fi
else
    print_success "✅ No uvicorn processes found"
fi

echo ""

# Method 3: Use stop-pod.sh if available
if [ -f "scripts/pod/stop-pod.sh" ]; then
    print_status "💡 Alternative: Use stop-pod.sh to stop all services"
    echo "   bash scripts/pod/stop-pod.sh"
    echo ""
fi

# Final check
print_status "Final check..."
if command -v lsof > /dev/null 2>&1; then
    if lsof -ti:8001 > /dev/null 2>&1; then
        print_error "❌ Port 8001 is still in use"
        print_status "💡 Try: bash scripts/pod/stop-pod.sh"
    else
        print_success "✅ Port 8001 is now free"
    fi
else
    if pgrep -f "python.*uvicorn.*app.main" > /dev/null; then
        print_error "❌ uvicorn processes still running"
        print_status "💡 Try: bash scripts/pod/stop-pod.sh"
    else
        print_success "✅ No uvicorn processes running"
    fi
fi

echo ""
print_status "💡 Now you can start services:"
echo "   bash scripts/pod/start-pod.sh"

