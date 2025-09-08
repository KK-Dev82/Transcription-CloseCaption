FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install fastapi uvicorn pydantic

# Clone and build whisper.cpp
RUN git clone https://github.com/ggml-org/whisper.cpp.git /app/whisper.cpp \
    && cd /app/whisper.cpp \
    && make

# Download base model
RUN cd /app/whisper.cpp \
    && ./models/download-ggml-model.sh base

# Set working directory
WORKDIR /app

# Create directories
RUN mkdir -p /app/models /app/audio /app/output

# Copy models to accessible location
RUN cp /app/whisper.cpp/models/ggml-base.bin /app/models/

# Set PATH
ENV PATH="/app/whisper.cpp:${PATH}"

# Copy Whisper API Service
COPY whisper_api.py /app/whisper_api.py

# Expose port
EXPOSE 8002

# Default command
CMD ["python3", "/app/whisper_api.py"] 