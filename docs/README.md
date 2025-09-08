# 📚 Transcription & Close Caption Service Documentation

## 🎯 Overview

Complete documentation for the Transcription & Close Caption Service API - ระบบแปลงเสียงเป็นข้อความและสร้าง close caption แบบ real-time พร้อมการปรับปรุงความแม่นยำภาษาไทย

**Version:** 1.2.0  
**API Base URL:** `http://localhost:8001`  
**Swagger UI:** `http://localhost:8001/docs`

## 📋 Table of Contents

### 🚀 Getting Started
- [API Reference](api/README.md) - Complete API documentation
- [Quick Start Guide](#quick-start)
- [Authentication & Security](#security)

### 🎨 Frontend Integration
- [Frontend Integration Guide](frontend/integration.md) - React, Vue, Angular examples
- [JavaScript/TypeScript Client](frontend/integration.md#javascripttypescript-client)
- [React Components](frontend/integration.md#react-components-examples)

### 🔔 Real-time Updates
- [Webhook Documentation](webhook/README.md) - Real-time notifications
- [WebSocket Guide](#websocket)
- [Progress Tracking](api/README.md#progress-tracking)

### 💡 Examples & Use Cases
- [Code Examples](examples/README.md) - Python, Node.js, cURL examples
- [Advanced Use Cases](examples/README.md#advanced-use-cases)
- [Performance Testing](examples/README.md#performance-testing)

### 🚀 Deployment
- [Docker Setup](#docker-setup)
- [Production Configuration](#production)
- [Scaling Guidelines](#scaling)

## 🚀 Quick Start

### 1. Basic Workflow

```bash
# 1. Upload file
curl -X POST -F "file=@video.mp4" http://localhost:8001/upload/

# 2. Start enhanced transcription
curl -X POST -H "Content-Type: application/json" \
  -d '{"file_path":"uploads/uuid_video.mp4", "language":"th"}' \
  http://localhost:8001/transcribe-enhanced/start

# 3. Track progress
curl http://localhost:8001/progress/transcription/{task_id}

# 4. Get results
curl http://localhost:8001/transcribe-enhanced/status/{task_id}
```

### 2. With Webhooks (Recommended)

```bash
# 1. Subscribe to webhook
curl -X POST -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.com/webhook",
    "events": ["transcription.completed", "transcription.progress"]
  }' \
  http://localhost:8001/webhook/subscribe

# 2. Upload & start transcription (same as above)
# 3. Receive real-time notifications at your webhook URL
```

## 🎯 Key Features

### ⚡ Performance Optimized
- **Fast Processing:** Base model + Thai post-processing (3-5 minutes for 10-minute video)
- **Concurrent Support:** Multiple transcriptions simultaneously
- **Progress Tracking:** Real-time progress updates

### 🇹🇭 Thai Language Excellence
- **NLP Enhancement:** 62,068 Thai words dictionary
- **Auto Correction:** Common mistakes fixing
- **Confidence Scoring:** Quality assessment

### 🔄 Real-time Integration
- **Webhook Notifications:** Event-driven updates
- **WebSocket Support:** Live streaming transcription
- **Progress API:** Detailed status tracking

### 📊 Production Ready
- **Error Handling:** Comprehensive error management
- **Retry Logic:** Automatic retry mechanisms
- **Monitoring:** Health checks and statistics

## 📊 API Endpoints Overview

| Category | Endpoint | Description |
|----------|----------|-------------|
| **Core** | `/upload/` | Upload video/audio files |
| | `/transcribe-enhanced/start` | Start optimized transcription |
| | `/progress/transcription/{id}` | Real-time progress tracking |
| **Webhooks** | `/webhook/subscribe` | Subscribe to notifications |
| | `/webhook/events` | List supported events |
| **Thai NLP** | `/thai/correct-text` | Text correction service |
| | `/thai/test-corrections` | Test correction quality |
| **Video** | `/video/segment` | Video segmentation + transcription |
| | `/video/trim` | Video trimming |
| **Captions** | `/caption/generate` | Generate SRT subtitles |
| **Live** | `/live/start` | Live streaming transcription |
| **System** | `/health` | System health check |

## 🔐 Security

### API Security
- **CORS Support:** Configurable origins
- **Input Validation:** File type and size limits
- **Error Handling:** No sensitive data exposure

### Webhook Security
- **HMAC Signatures:** SHA-256 verification
- **Custom Headers:** Authorization support
- **Retry Logic:** 3 attempts with exponential backoff

## 🐳 Docker Setup

### Development

```bash
# Clone repository
git clone <repository-url>
cd transcription-close-caption-service

# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Check services
curl http://localhost:8001/health
```

### Production

```bash
# Set environment variables
export STORAGE_TYPE=sqlite
export WHISPER_MODEL=base

# Start production environment
docker-compose up -d

# Monitor logs
docker-compose logs -f api
```

## 📈 Scaling

### Horizontal Scaling
- **API Instances:** Load balancer + multiple API containers
- **Worker Scaling:** Multiple video-worker instances
- **Queue System:** RabbitMQ for task distribution

### Performance Tuning
- **Model Selection:** `base` (fast) vs `large-v3` (accurate)
- **Chunk Size:** Balance between speed and accuracy
- **Concurrent Limits:** Based on available resources

### Resource Requirements

| Component | CPU | RAM | Storage |
|-----------|-----|-----|---------|
| API Server | 2 cores | 4GB | 10GB |
| Video Worker | 4 cores | 8GB | 50GB |
| Whisper Service | 2 cores | 4GB | 5GB |
| **Recommended Total** | **16 cores** | **32GB** | **100GB** |

## 🔍 Monitoring

### Health Checks
```bash
# System health
curl http://localhost:8001/health

# Statistics
curl http://localhost:8001/stats

# Active tasks
curl http://localhost:8001/progress/all-active
```

### Performance Metrics
- **Processing Speed:** ~2-3x real-time for base model
- **Accuracy:** 85-95% for Thai content (with NLP enhancement)
- **Concurrent Capacity:** 4-6 simultaneous transcriptions

## 🚨 Troubleshooting

### Common Issues

**1. Upload Fails**
```bash
# Check file size (max 2GB)
# Verify file format support
curl http://localhost:8001/upload/ -F "file=@test.mp4" -v
```

**2. Progress Stuck**
```bash
# Check worker status
docker-compose logs video-worker-1
docker-compose logs video-worker-2

# Restart workers if needed
docker-compose restart video-worker-1 video-worker-2
```

**3. Webhook Not Received**
```bash
# Test webhook
curl -X POST -H "Content-Type: application/json" \
  -d '{"subscription_id":"uuid","event_type":"test"}' \
  http://localhost:8001/webhook/test

# Check webhook stats
curl http://localhost:8001/webhook/stats
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Restart services
docker-compose restart api
```

## 📞 Support & Contributing

### Getting Help
- **Documentation:** Check relevant sections above
- **API Reference:** Use `/docs` endpoint
- **Examples:** See `examples/` directory

### Contributing
1. Fork the repository
2. Create feature branch
3. Add tests for new features
4. Update documentation
5. Submit pull request

## 🔗 Quick Links

- **[Complete API Reference](api/README.md)** - All endpoints and parameters
- **[Frontend Integration](frontend/integration.md)** - React, Vue, Angular guides  
- **[Webhook Guide](webhook/README.md)** - Real-time notifications
- **[Code Examples](examples/README.md)** - Python, Node.js, cURL samples
- **[Swagger UI](http://localhost:8001/docs)** - Interactive API documentation

---

## 📄 License

MIT License - see LICENSE file for details.

## 📧 Contact

For technical support or questions, please refer to the documentation sections above or check the API's `/docs` endpoint for the most up-to-date information.
