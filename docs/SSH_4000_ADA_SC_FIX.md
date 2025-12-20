# 🔧 แก้ไข SSH Connection ไป 4000-ada-sc

## ❌ ปัญหา

```bash
ssh 4000-ada-sc
# Warning: Permanently added '[213.173.108.12]:15270' (ED25519) to the list of known hosts.
# root@213.173.108.12: Permission denied (publickey).
```

**สาเหตุ**: SSH public key ยังไม่ได้ถูกเพิ่มไปที่ `authorized_keys` บน server `4000-ada-sc`

---

## ✅ วิธีแก้ไข

### วิธีที่ 1: เพิ่ม SSH Key ผ่าน RunPod (ถ้า server อยู่ใน network เดียวกัน)

```bash
# 1. SSH เข้า RunPod ก่อน
ssh feez7cx7a58j13-6441103b@ssh.runpod.io -i ~/.ssh/id_ed25519

# 2. จาก RunPod SSH ต่อเข้า 4000-ada-sc (ถ้า network เชื่อมต่อกัน)
# หรือใช้วิธีอื่นตามที่ server admin กำหนด
```

### วิธีที่ 2: ใช้ Password Authentication ชั่วคราว (ถ้ามี)

```bash
# 1. SSH ด้วย password (ถ้าเปิดไว้)
ssh -p 15270 root@213.173.108.12

# 2. เมื่อเข้าได้แล้ว เพิ่ม public key
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICsF/zoSGze7Ty995PGsVQRK65N4c3ZtW0b1pWz+F+tu goataog@gmail.com" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### วิธีที่ 3: ใช้ Script setup-ssh.sh (ถ้าเข้าได้ด้วยวิธีอื่น)

```bash
# 1. Copy script ไปที่ server (ถ้าเข้าได้)
scp -P 15270 scripts/pod/setup-ssh.sh root@213.173.108.12:/tmp/

# 2. SSH เข้า server
ssh -p 15270 root@213.173.108.12

# 3. รัน script
bash /tmp/setup-ssh.sh
```

### วิธีที่ 4: ให้ Server Admin ช่วยเพิ่ม Key

ส่ง public key นี้ให้ server admin:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICsF/zoSGze7Ty995PGsVQRK65N4c3ZtW0b1pWz+F+tu goataog@gmail.com
```

ให้ admin เพิ่มไปที่ `/root/.ssh/authorized_keys` บน server `213.173.108.12`

---

## 🔍 ตรวจสอบ SSH Config

### SSH Config ที่ถูกต้อง

```ssh-config
Host 4000-ada-sc
     HostName 213.173.108.12
     Port 15270
     User root
     IdentityFile ~/.ssh/id_ed25519
     StrictHostKeyChecking no
     UserKnownHostsFile /dev/null
```

### ตรวจสอบ Public Key

```bash
# ดู public key
cat ~/.ssh/id_ed25519.pub

# ควรได้:
# ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICsF/zoSGze7Ty995PGsVQRK65N4c3ZtW0b1pWz+F+tu goataog@gmail.com
```

---

## 📋 Checklist

- [ ] ตรวจสอบว่า public key ถูกต้อง: `cat ~/.ssh/id_ed25519.pub`
- [ ] เพิ่ม public key ไปที่ `/root/.ssh/authorized_keys` บน server
- [ ] ตรวจสอบ permissions:
  - `/root/.ssh`: `700`
  - `/root/.ssh/authorized_keys`: `600`
- [ ] ทดสอบ SSH: `ssh 4000-ada-sc`

---

## ⚠️ หมายเหตุ

### เกี่ยวกับ 4000-ada-sc

- **IP**: `213.173.108.12`
- **Port**: `15270`
- **User**: `root`
- **ไม่ใช่ RunPod**: Server นี้เป็น server แยก (ไม่ใช่ RunPod managed)

### เกี่ยวกับ RunPod SSH

- RunPod SSH ใช้ได้: `ssh feez7cx7a58j13-6441103b@ssh.runpod.io`
- RunPod จัดการ SSH keys อัตโนมัติ
- 4000-ada-sc ต้อง setup SSH key เอง

---

## 🔧 Troubleshooting

### Error: Permission denied (publickey)

**สาเหตุ**: Public key ไม่ได้ถูกเพิ่มไปที่ server

**วิธีแก้**:
1. ตรวจสอบว่า public key ถูกต้อง
2. เพิ่ม key ไปที่ `/root/.ssh/authorized_keys` บน server
3. ตรวจสอบ permissions

### Error: Connection refused

**สาเหตุ**: Port หรือ IP ไม่ถูกต้อง

**วิธีแก้**:
1. ตรวจสอบ SSH config
2. ตรวจสอบว่า server เปิด port 15270
3. ตรวจสอบ firewall

---

**Last Updated**: 2025-01-XX  
**Issue**: SSH Permission denied (publickey)  
**Server**: 4000-ada-sc (213.173.108.12:15270)

