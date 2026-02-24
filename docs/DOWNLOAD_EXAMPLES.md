# ตัวอย่างการใช้งาน Download Endpoints

Base URL ใช้จาก `MAIN_API_URL` หรือ `API_BASE_URL` (เช่น `https://xxx-8010.proxy.runpod.net`)

---

## 1. ดาวน์โหลดไฟล์เดียว (GET)

ใช้ `file_path` จาก `/api/video/list`

```bash
# ตัวอย่าง
curl -o "my_video.mp4" "{BASE}/api/upload/download?file_path=uploads/e7af5d37-ac54-4501-aca9-837304b05019_chapter_video_xxx.mp4"
```

```javascript
// JavaScript/Fetch
const filePath = "uploads/xxx.mp4";  // จาก video list
const url = `${BASE}/api/upload/download?file_path=${encodeURIComponent(filePath)}`;
const a = document.createElement('a');
a.href = url;
a.download = 'video.mp4';
a.click();
```

```python
# Python
import urllib.request
from urllib.parse import urlencode

base = "https://your-pod-8010.proxy.runpod.net"
file_path = "uploads/xxx.mp4"
url = f"{base}/api/upload/download?{urlencode({'file_path': file_path})}"
urllib.request.urlretrieve(url, "downloaded.mp4")
```

---

## 2. ดาวน์โหลดหลายไฟล์เป็น ZIP (POST Selection)

ใช้ `ids` หรือ `file_paths` จาก `/api/video/list`

```bash
# ใช้ ids
curl -o selection.zip -X POST "{BASE}/api/upload/selection/download" \
  -H "Content-Type: application/json" \
  -d '{"ids": [43, 42, 30]}'

# ใช้ file_paths
curl -o selection.zip -X POST "{BASE}/api/upload/selection/download" \
  -H "Content-Type: application/json" \
  -d '{"file_paths": ["uploads/xxx.mp4", "uploads/yyy.mp3"]}'
```

```javascript
// JavaScript/Fetch
const res = await fetch(`${BASE}/api/upload/selection/download`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ids: [43, 42, 30] }),
});
const blob = await res.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = 'selection.zip';
a.click();
URL.revokeObjectURL(url);
```

```python
# Python
import requests

base = "https://your-pod-8010.proxy.runpod.net"
r = requests.post(
    f"{base}/api/upload/selection/download",
    json={"ids": [43, 42, 30]},
    timeout=300,
)
with open("selection.zip", "wb") as f:
    f.write(r.content)
```

---

## 3. ดึงรายการไฟล์ก่อน (GET /api/video/list)

```bash
curl -s "{BASE}/api/video/list" | jq '.videos[0], .audios[0]'
```

Response จะมี `id`, `file_path`, `filename` สำหรับใช้กับ download endpoints

---

## 4. สคริปต์ Python (ใช้ env)

```bash
# ตั้งค่า URL ก่อน
export MAIN_API_URL=https://your-pod-8010.proxy.runpod.net

# แสดงรายการ
python scripts/download_from_video_list.py --list-only

# ดาวน์โหลดตาม ID
python scripts/download_from_video_list.py --ids 43,42,30 --output-dir ./downloads

# ใช้ --base-url แทน env
python scripts/download_from_video_list.py --base-url https://xxx.proxy.runpod.net --ids 43,42
```
