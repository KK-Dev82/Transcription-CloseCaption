# 🔪 วิธี Kill Uvicorn/Server Process

คู่มือการ kill server process ที่รันอยู่

## วิธีที่ 1: ใช้ Ctrl+C (ถ้ายังอยู่ใน terminal เดิม)

```bash
# กด Ctrl+C ใน terminal ที่รัน server อยู่
```

---

## วิธีที่ 2: หา PID แล้ว Kill (แนะนำ)

### ขั้นตอนที่ 1: หา Process ID
```bash
# หา uvicorn process
ps aux | grep uvicorn | grep -v grep

# หรือหา python process ที่รัน main.py
ps aux | grep "python.*main.py" | grep -v grep

# หรือหา process ที่ใช้ port 8010
lsof -i :8010
```

### ขั้นตอนที่ 2: Kill Process
```bash
# Kill แบบปกติ (graceful shutdown)
kill <PID>

# หรือ kill แบบ force (ถ้า kill ไม่ได้)
kill -9 <PID>
```

### ตัวอย่าง
```bash
# หา PID
ps aux | grep uvicorn | grep -v grep
# Output: root  188607  1.5  0.1 5403152 485428 pts/3  Sl   12:57   0:05 python3 -m uvicorn...

# Kill
kill 188607
```

---

## วิธีที่ 3: ใช้ pkill (ง่ายที่สุด)

```bash
# Kill uvicorn ทั้งหมด
pkill -f uvicorn

# หรือ kill python process ที่รัน main.py
pkill -f "python.*main.py"

# Force kill
pkill -9 -f uvicorn
```

---

## วิธีที่ 4: ใช้ killall

```bash
# Kill process ทั้งหมดที่ชื่อ uvicorn
killall uvicorn

# หรือ kill python process
killall python3

# Force kill
killall -9 uvicorn
```

---

## วิธีที่ 5: หา Process จาก Port แล้ว Kill

```bash
# หา process ที่ใช้ port 8010
lsof -i :8010

# Output จะแสดง PID
# COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
# python3 188607 root   10u  IPv4 123456      0t0  TCP *:8010 (LISTEN)

# Kill จาก PID
kill 188607

# หรือใช้ fuser (ถ้ามี)
fuser -k 8010/tcp
```

---

## วิธีที่ 6: สร้าง Script สำหรับ Kill

สร้างไฟล์ `kill-server.sh`:
```bash
#!/bin/bash
# Kill uvicorn server

echo "🔍 Finding uvicorn processes..."
PROCESSES=$(ps aux | grep -E "uvicorn|python.*main.py" | grep -v grep)

if [ -z "$PROCESSES" ]; then
    echo "✅ No uvicorn processes found"
    exit 0
fi

echo "📋 Found processes:"
echo "$PROCESSES"

# Extract PIDs
PIDS=$(echo "$PROCESSES" | awk '{print $2}')

echo "🔪 Killing processes..."
for PID in $PIDS; do
    echo "   Killing PID: $PID"
    kill $PID 2>/dev/null || kill -9 $PID 2>/dev/null
done

sleep 1

# Verify
REMAINING=$(ps aux | grep -E "uvicorn|python.*main.py" | grep -v grep)
if [ -z "$REMAINING" ]; then
    echo "✅ All processes killed successfully"
else
    echo "⚠️  Some processes still running:"
    echo "$REMAINING"
fi
```

ใช้:
```bash
chmod +x kill-server.sh
./kill-server.sh
```

---

## วิธีที่ 7: ใช้ Python Script

สร้างไฟล์ `kill_server.py`:
```python
#!/usr/bin/env python3
import subprocess
import sys
import signal

def kill_uvicorn():
    """Kill all uvicorn processes"""
    try:
        # Find processes
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        
        lines = result.stdout.split('\n')
        pids = []
        
        for line in lines:
            if 'uvicorn' in line and 'grep' not in line:
                parts = line.split()
                if len(parts) > 1:
                    pids.append(parts[1])
        
        if not pids:
            print("✅ No uvicorn processes found")
            return
        
        print(f"🔍 Found {len(pids)} uvicorn process(es)")
        
        # Kill processes
        for pid in pids:
            try:
                print(f"🔪 Killing PID: {pid}")
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                print(f"   PID {pid} already dead")
            except Exception as e:
                print(f"   Error killing PID {pid}: {e}")
        
        print("✅ Done")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    import os
    kill_uvicorn()
```

ใช้:
```bash
python3 kill_server.py
```

---

## ⚠️ หมายเหตุ

### Signal Types
- `SIGTERM` (kill): Graceful shutdown (แนะนำ)
- `SIGKILL` (kill -9): Force kill (ใช้เมื่อ kill ไม่ได้)

### ถ้า Kill ไม่ได้
```bash
# 1. ตรวจสอบว่า process ยังอยู่หรือไม่
ps aux | grep <PID>

# 2. ตรวจสอบว่าเป็น root process หรือไม่ (ต้องใช้ sudo)
sudo kill <PID>

# 3. Force kill
kill -9 <PID>
# หรือ
sudo kill -9 <PID>
```

---

## 🚀 Quick Commands

```bash
# Kill uvicorn ทั้งหมด (เร็วที่สุด)
pkill -f uvicorn

# Kill process ที่ใช้ port 8010
lsof -ti :8010 | xargs kill

# Kill และ verify
pkill -f uvicorn && sleep 1 && ps aux | grep uvicorn | grep -v grep || echo "✅ All killed"
```

---

## 📝 Tips

1. **ใช้ Ctrl+C ก่อน**: ถ้ายังอยู่ใน terminal เดิม
2. **ใช้ pkill**: ง่ายและเร็วที่สุด
3. **ตรวจสอบหลัง kill**: `ps aux | grep uvicorn` เพื่อยืนยัน
4. **ใช้ kill -9 เฉพาะเมื่อจำเป็น**: เพราะจะ force kill ทันที
