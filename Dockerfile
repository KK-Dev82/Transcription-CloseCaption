# Multi-stage build สำหรับลดขนาด image
FROM python:3.11-slim as builder

# ตั้งค่า environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# ติดตั้ง build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    cmake \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# สร้าง working directory
WORKDIR /app

# คัดลอก requirements และติดตั้ง Python dependencies (ไม่ติดตั้ง PyTorch)
COPY docs/requirements-core.txt .
RUN pip install --no-cache-dir --user -r requirements-core.txt

# Production stage
FROM python:3.11-slim

# ตั้งค่า environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/bin:$PATH"

# ติดตั้ง runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    libsndfile1 \
    libportaudio2 \
    libasound2-dev \
    portaudio19-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# สร้าง working directory
WORKDIR /app

# คัดลอก Python packages จาก builder stage
COPY --from=builder /root/.local /root/.local

# ลบ cache และ files ที่ไม่จำเป็นเพื่อลดขนาด image
RUN find /root/.local -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type f -name "*.pyc" -delete 2>/dev/null || true \
    && find /root/.local -type f -name "*.pyo" -delete 2>/dev/null || true \
    && find /root/.local -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type d -name "doc" -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type f -name "*.md" -delete 2>/dev/null || true \
    && find /root/.local -type f -name "*.txt" -path "*/LICENSE*" -delete 2>/dev/null || true \
    && find /root/.local -type f -name "*.rst" -delete 2>/dev/null || true

# คัดลอก source code
COPY . .

# สร้างโฟลเดอร์ที่จำเป็น
RUN mkdir -p uploads temp storage models test-files

# คัดลอก entrypoint script (path ภายใน container ไม่เกี่ยวกับ host OS)
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# ตั้งค่า permissions
RUN chmod +x main.py

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# ใช้ entrypoint script (path ภายใน container)
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# รัน application
CMD ["sh", "-c", "if [ \"$ENVIRONMENT\" = \"development\" ]; then uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --log-level info; else uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level info; fi"]
