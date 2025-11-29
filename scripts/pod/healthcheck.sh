#!/bin/bash
# Health check script สำหรับ Custom Base Image

# Check API health
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    exit 0
fi

# Check Whisper health
if curl -f http://localhost:8002/health > /dev/null 2>&1; then
    exit 0
fi

# If both fail, return error
exit 1

