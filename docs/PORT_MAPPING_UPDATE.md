# Port Mapping Update

## 📋 Port Changes

### 4000-ada-sc Server

**Old Ports:**
- SSH: `14236`
- API: `14237`

**New Ports:**
- SSH: `13263`
- API: `13264`

## 🔧 Configuration Updates

### 1. Dashboard Server Constants
**File**: `dashboard/server_constants.py`

Updated:
```python
"4000-ada-sc": {
    "name": "4000-ada-sc",
    "api_url": "http://213.173.108.6:13264",  # Changed from 14237
    "color": "#0071e3"
}
```

### 2. SSH Connection
**New SSH Command:**
```bash
ssh -p 13263 4000-ada-sc
```

**Old SSH Command:**
```bash
ssh -p 14236 4000-ada-sc
```

### 3. API Endpoints
**New API URL:**
```
http://213.173.108.6:13264
```

**Old API URL:**
```
http://213.173.108.6:14237
```

## ✅ Verification

### Test SSH Connection
```bash
ssh -p 13263 4000-ada-sc "echo 'SSH connection successful'"
```

### Test API Connection
```bash
curl http://213.173.108.6:13264/health
```

### Test from Dashboard
- Open Dashboard
- Select "4000-ada-sc" server
- Check if connection works

## 📝 Notes

- Internal port (8010) remains unchanged
- Only external port mapping changed
- Service runs on port 8010 internally
- Nginx/port mapping forwards 13264 -> 8010

## 🔄 Migration Steps

1. ✅ Updated `dashboard/server_constants.py`
2. ✅ Committed and pushed changes
3. ⚠️ Restart Dashboard (if needed) to load new config
4. ⚠️ Update any hardcoded URLs in other services

## 🚨 Important

- **SSH**: Use port `13263` (not 14236)
- **API**: Use port `13264` (not 14237)
- **Internal**: Service still runs on port `8010`

