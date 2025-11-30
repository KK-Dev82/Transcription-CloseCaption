#!/bin/bash
# Script สำหรับ Stop Transcription Containers เดิม

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "🛑 Stopping Transcription Containers"
echo "📅 $(date)"
echo ""

# Find transcription containers
CONTAINERS=$(docker ps -a --filter "name=transcription" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -z "$CONTAINERS" ]; then
    print_warning "⚠️  No transcription containers found"
    exit 0
fi

print_status "Found transcription containers:"
echo "$CONTAINERS" | while read -r container; do
    if [ -n "$container" ]; then
        STATUS=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
        echo "   - $container ($STATUS)"
    fi
done
echo ""

read -p "Stop all transcription containers? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Operation cancelled."
    exit 0
fi

# Stop containers
echo "$CONTAINERS" | while read -r container; do
    if [ -n "$container" ]; then
        print_status "Stopping $container..."
        docker stop "$container" 2>/dev/null && {
            print_success "✅ Stopped $container"
        } || {
            print_warning "⚠️  Failed to stop $container (may already be stopped)"
        }
    fi
done

# Remove containers (optional)
echo ""
read -p "Remove stopped containers? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "$CONTAINERS" | while read -r container; do
        if [ -n "$container" ]; then
            print_status "Removing $container..."
            docker rm "$container" 2>/dev/null && {
                print_success "✅ Removed $container"
            } || {
                print_warning "⚠️  Failed to remove $container"
            }
        fi
    done
fi

print_success "🎉 Done!"
echo ""
print_status "💡 To start new container:"
echo "   docker-compose -f docker-compose.local-direct.yml up -d"
echo "   docker exec -it transcription-local-base bash"

