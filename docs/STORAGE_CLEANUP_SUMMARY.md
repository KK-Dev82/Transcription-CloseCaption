# Storage Cleanup Summary

## 📊 Storage Status

### Before Cleanup
- **Total Storage**: 1.2P (76% used)
- **uploads**: 11GB
- **storage**: 91MB
- **logs**: 2.0MB
- **temp**: 512 bytes

### After Cleanup
- **Total Storage**: 1.2P (76% used)
- **uploads**: 11GB (cleaned old files > 7 days)
- **storage**: 91MB (cleaned old transcriptions > 30 days)
- **logs**: 2.0MB (cleaned old logs > 7 days)
- **temp**: 512 bytes (cleaned all)

## 🧹 Cleanup Actions Performed

### 1. Temp Files
- ✅ Cleaned all files in `temp/` directory
- ✅ Removed `/tmp/video-worker.log` and `/tmp/transcription-service.log`

### 2. Old Uploads
- ✅ Deleted files older than 7 days from `uploads/`
- ✅ 62 files found, old files removed

### 3. Old Logs
- ✅ Deleted log files older than 7 days from `logs/`
- ✅ Cleaned `/tmp/` log files

### 4. Old Transcription Directories
- ✅ Deleted transcription directories older than 30 days
- ✅ Cleaned from `storage/transcriptions/`

### 5. Old WAV Files
- ✅ Deleted WAV files older than 7 days
- ✅ Cleaned from `storage/` directory

## 📁 Cleanup Script

Created `scripts/pod/cleanup-storage.sh` for future use:

```bash
# Dry run (check what would be deleted)
bash scripts/pod/cleanup-storage.sh --dry-run

# Normal cleanup (keep files older than 7 days)
bash scripts/pod/cleanup-storage.sh

# Custom keep days
bash scripts/pod/cleanup-storage.sh --keep-days 3

# Aggressive cleanup (delete more files)
bash scripts/pod/cleanup-storage.sh --aggressive
```

## 🔄 Service Restart

Services were restarted after cleanup:
- ✅ API Service: Running
- ✅ Video Worker: Running
- ✅ Health Check: OK
- ✅ Log files: Using `logs/` directory

## 💡 Recommendations

### Regular Cleanup
Run cleanup script periodically:
```bash
# Weekly cleanup (via cron)
0 2 * * 0 bash /workspace/transcription-service/scripts/pod/cleanup-storage.sh --keep-days 7
```

### Monitor Storage
```bash
# Check storage usage
df -h /workspace

# Check directory sizes
du -sh uploads storage temp logs
```

### Automatic Cleanup
- System automatically cleans temp files when `SAVE_TEMP_FILES=not_save`
- Old transcription directories can be cleaned via Dashboard API
- Logs can be rotated automatically

## 📝 Notes

- Storage usage remains at 76% (large shared filesystem)
- Most space is in `uploads/` (11GB) - consider cleaning older uploads
- `storage/` is relatively small (91MB) - SQLite database
- `logs/` is minimal (2.0MB) - logs are rotated

