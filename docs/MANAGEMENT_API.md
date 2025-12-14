# Management API Documentation

## 📋 Overview

Management API เป็นชุด endpoints สำหรับการจัดการ remote server แทนที่การใช้ SSH โดยตรง เพื่อเพิ่มความเสถียรและความปลอดภัยของระบบ

## 🎯 เป้าหมาย

- **แทนที่ SSH**: ไม่ต้องใช้ SSH connection โดยตรง
- **เพิ่มความเสถียร**: ใช้ HTTP API แทน SSH connection ที่อาจไม่เสถียร
- **ความปลอดภัย**: มี whitelist ของ commands ที่อนุญาต
- **ง่ายต่อการใช้งาน**: Dashboard สามารถเรียก API ได้โดยตรง

## 📡 API Endpoints

### 1. Execute Command

Execute command บน server (แทนที่ SSH command execution)

**Endpoint:** `POST /api/management/execute`

**Request Body:**
```json
{
  "command": "nvidia-smi",
  "timeout": 30,
  "working_dir": "/workspace/transcription-service",
  "environment": {
    "ENV_VAR": "value"
  }
}
```

**Response:**
```json
{
  "success": true,
  "exit_code": 0,
  "stdout": "NVIDIA-SMI output...",
  "stderr": "",
  "execution_time": 0.5
}
```

### 2. System Information

Get system information (CPU, Memory, Disk, GPU)

**Endpoint:** `GET /api/management/system-info`

### 3. Get Logs

Get log file contents

**Endpoint:** `GET /api/management/logs`

### 4. List Scripts

List available management scripts

**Endpoint:** `GET /api/management/scripts`

### 5. Execute Script

Execute a management script

**Endpoint:** `POST /api/management/scripts/{script_name}/execute`

## 🔄 Migration from SSH

### Before (SSH):
```python
import subprocess
result = subprocess.run(
    ["ssh", "4000-ada-sc", "nvidia-smi"],
    capture_output=True,
    text=True
)
```

### After (API):
```python
import aiohttp
async with aiohttp.ClientSession() as session:
    async with session.post(
        "http://213.173.108.6:14237/api/management/execute",
        json={"command": "nvidia-smi"}
    ) as response:
        result = await response.json()
```

## 🚀 Next Steps

1. **Update Dashboard**: แก้ไข dashboard ให้ใช้ Management API แทน SSH
2. **Add Authentication**: เพิ่ม authentication/authorization สำหรับ production
3. **Expand Whitelist**: เพิ่ม commands ที่จำเป็นใน whitelist
