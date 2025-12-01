# 🔌 RunPod SSH Configuration

## SSH Config

เพิ่มใน `~/.ssh/config`:

```ssh-config
# RunPod Pod: calm_pink_turtle
Host calm-pink-turtle
     HostName 80.15.7.37
     Port 41317
     User root
     IdentityFile ~/.ssh/id_ed25519
     StrictHostKeyChecking no
     UserKnownHostsFile /dev/null
```

## การใช้งาน

### SSH เข้า Pod
```bash
ssh calm-pink-turtle
```

### ใช้ Script
```bash
# SSH interactive
bash scripts/pod/ssh-runpod.sh

# Execute command
bash scripts/pod/ssh-runpod.sh "hostname && pwd"
```

### Deploy และ Setup
```bash
# Deploy และ setup
bash scripts/pod/deploy-to-runpod.sh

# หรือระบุ host
RUNPOD_HOST=calm-pink-turtle bash scripts/pod/deploy-to-runpod.sh
```

### ทดสอบ Transcription
```bash
# ทดสอบ transcription
bash scripts/pod/test-runpod.sh uploads/v10-1.mp4 medium

# หรือระบุ host
RUNPOD_HOST=calm-pink-turtle bash scripts/pod/test-runpod.sh uploads/v10-1.mp4 medium
```

## หมายเหตุ

- **IP/Port อาจเปลี่ยน**: ถ้า Pod ถูก restart IP และ Port อาจเปลี่ยน
- **ตรวจสอบ RunPod Dashboard**: ดู SSH command ที่ถูกต้องจาก RunPod dashboard
- **Update SSH Config**: ถ้า IP/Port เปลี่ยน ให้อัปเดต `~/.ssh/config`

## Troubleshooting

### Connection Refused
```bash
# ตรวจสอบว่า Pod ทำงานอยู่หรือไม่
# ดูจาก RunPod Dashboard

# ทดสอบ connection
ssh -v calm-pink-turtle "echo 'test'"
```

### Permission Denied
```bash
# ตรวจสอบ SSH key
ls -la ~/.ssh/id_ed25519

# ตรวจสอบ permissions
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/config
```

