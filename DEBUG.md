# 🐛 Debug Guide

## Build vs Push Separation

### Build Job
- **Purpose**: Build Docker images locally
- **Output**: Image IDs (ไม่ push ไปยัง ACR)
- **Debug**: ตรวจสอบ build errors, Dockerfile issues

### Push Job
- **Purpose**: Push images ไปยัง ACR
- **Dependencies**: ต้องรอ build job สำเร็จก่อน
- **Debug**: ตรวจสอบ ACR credentials, network issues

## 🔍 Debugging Steps

### 1. Build Job Fails
```bash
# ตรวจสอบใน GitHub Actions logs:
# - Dockerfile syntax errors
# - Build context issues
# - Missing dependencies
# - Platform compatibility
```

**Common Issues:**
- `Dockerfile` syntax errors
- Missing files in build context
- Platform architecture mismatches
- Memory/resource limits

### 2. Push Job Fails
```bash
# ตรวจสอบใน GitHub Actions logs:
# - ACR login issues
# - Network connectivity
# - Image tag conflicts
# - Registry permissions
```

**Common Issues:**
- Invalid ACR credentials
- Network timeouts
- Registry quota exceeded
- Image tag already exists

### 3. Environment Variables
```bash
# ตรวจสอบ GitHub Secrets:
ACR_LOGIN_SERVER=your-registry.azurecr.io
ACR_USERNAME=your-username
ACR_PASSWORD=your-password
```

## 🛠️ Manual Testing

### Test Build Locally
```bash
# Build main application
docker build -t kk-transcription:test .

# Build whisper service
docker build -t kk-transcription-whisper:test ./whisper-service

# Test images
docker run --rm kk-transcription:test --help
docker run --rm kk-transcription-whisper:test --help
```

### Test ACR Push
```bash
# Login to ACR
docker login your-registry.azurecr.io

# Tag images
docker tag kk-transcription:test your-registry.azurecr.io/kk-transcription:test
docker tag kk-transcription-whisper:test your-registry.azurecr.io/kk-transcription-whisper:test

# Push images
docker push your-registry.azurecr.io/kk-transcription:test
docker push your-registry.azurecr.io/kk-transcription-whisper:test
```

## 📊 Workflow Status

### Build Job Status
- ✅ **Success**: Images built successfully
- ❌ **Failed**: Check build logs for errors
- ⏳ **Running**: Build in progress

### Push Job Status
- ✅ **Success**: Images pushed to ACR
- ❌ **Failed**: Check ACR credentials and network
- ⏳ **Waiting**: Waiting for build job to complete

## 🔧 Troubleshooting

### Build Errors
1. **Dockerfile Issues**:
   ```dockerfile
   # ตรวจสอบ syntax
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   ```

2. **Context Issues**:
   ```yaml
   # ตรวจสอบ build context
   context: .
   file: ./Dockerfile
   ```

3. **Platform Issues**:
   ```yaml
   # ตรวจสอบ platform
   platforms: linux/amd64
   ```

### Push Errors
1. **ACR Login**:
   ```bash
   # ตรวจสอบ credentials
   echo $ACR_PASSWORD | docker login $ACR_LOGIN_SERVER --username $ACR_USERNAME --password-stdin
   ```

2. **Network Issues**:
   ```bash
   # ตรวจสอบ connectivity
   ping your-registry.azurecr.io
   curl -I https://your-registry.azurecr.io/v2/
   ```

3. **Registry Issues**:
   ```bash
   # ตรวจสอบ registry status
   az acr show --name your-registry
   ```

## 📝 Logs Analysis

### Build Logs
- Look for `ERROR` or `FAILED` messages
- Check Docker build output
- Verify file paths and context

### Push Logs
- Look for authentication errors
- Check network connectivity
- Verify image tags and registry URL

## 🚀 Quick Fixes

### Common Build Fixes
1. **Fix Dockerfile syntax**
2. **Add missing files to context**
3. **Update platform specifications**
4. **Increase resource limits**

### Common Push Fixes
1. **Update ACR credentials**
2. **Check network connectivity**
3. **Verify registry permissions**
4. **Clear image cache**

## 📞 Support

หากยังมีปัญหา:
1. ตรวจสอบ GitHub Actions logs
2. ทดสอบ build/push locally
3. ตรวจสอบ ACR status
4. ดู troubleshooting guide
