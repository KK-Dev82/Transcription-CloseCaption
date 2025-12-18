#!/bin/bash
# ติดตั้ง Redis ใน user space (ไม่ต้องใช้ sudo)

set -e

REDIS_VERSION="7.2.3"
REDIS_DIR="$HOME/redis"
REDIS_BIN="$REDIS_DIR/bin"

echo "=================================================================================="
echo "📦 Installing Redis in user space"
echo "=================================================================================="

# สร้าง directory
mkdir -p "$REDIS_DIR"
cd "$REDIS_DIR"

# Download Redis source
if [ ! -f "redis-${REDIS_VERSION}.tar.gz" ]; then
    echo "📥 Downloading Redis ${REDIS_VERSION}..."
    wget "https://download.redis.io/releases/redis-${REDIS_VERSION}.tar.gz" || {
        echo "❌ Failed to download Redis"
        exit 1
    }
fi

# Extract
if [ ! -d "redis-${REDIS_VERSION}" ]; then
    echo "📦 Extracting Redis..."
    tar -xzf "redis-${REDIS_VERSION}.tar.gz"
fi

cd "redis-${REDIS_VERSION}"

# Compile Redis
if [ ! -f "src/redis-server" ]; then
    echo "🔨 Compiling Redis..."
    make || {
        echo "❌ Failed to compile Redis"
        echo "💡 Make sure you have: build-essential, gcc, make"
        exit 1
    }
fi

# Copy binaries
mkdir -p "$REDIS_BIN"
cp src/redis-server "$REDIS_BIN/"
cp src/redis-cli "$REDIS_BIN/"

# Add to PATH
if ! echo "$PATH" | grep -q "$REDIS_BIN"; then
    echo "export PATH=\"$REDIS_BIN:\$PATH\"" >> ~/.bashrc
    export PATH="$REDIS_BIN:$PATH"
fi

echo "✅ Redis installed successfully!"
echo "📍 Redis binary: $REDIS_BIN/redis-server"
echo "📍 Redis CLI: $REDIS_BIN/redis-cli"

# Test
if "$REDIS_BIN/redis-server" --version > /dev/null 2>&1; then
    echo "✅ Redis server is working"
else
    echo "❌ Redis server test failed"
    exit 1
fi

echo "=================================================================================="
echo "🚀 Starting Redis..."
echo "=================================================================================="

# Start Redis
"$REDIS_BIN/redis-server" --daemonize yes --port 6379 \
    --appendonly yes \
    --maxmemory 2gb \
    --maxmemory-policy allkeys-lru \
    --dir "$REDIS_DIR/data" || {
    echo "⚠️  Redis may already be running"
}

sleep 2

# Test connection
if "$REDIS_BIN/redis-cli" ping > /dev/null 2>&1; then
    echo "✅ Redis started successfully!"
    "$REDIS_BIN/redis-cli" ping
else
    echo "❌ Redis failed to start"
    exit 1
fi

echo "=================================================================================="
echo "✅ Redis installation complete!"
echo "=================================================================================="

