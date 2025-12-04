# โฟลเดอร์ SSH
mkdir -p /root/.ssh
chown root:root /root/.ssh
chmod 700 /root/.ssh

# ไฟล์ authorized_keys
chown root:root /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys

# ใส่คีย์ใหม่แทนของเดิม (แทนบรรทัดด้านล่างด้วยเนื้อหา id_ed25519.pub จาก Mac)
cat > /root/.ssh/authorized_keys <<'EOF'
ssh-ed25519 AAAA...YOUR_PUBLIC_KEY... athip-ch
EOF

# จัดการ Authen Permission
chown root:root /root
chmod 700 /root

# ลบทุกบรรทัดเดิมที่เกี่ยวข้องก่อน (กันค่าซ้ำ)
sed -i '/^PasswordAuthentication /d' /etc/ssh/sshd_config
sed -i '/^PubkeyAuthentication /d'    /etc/ssh/sshd_config
sed -i '/^AuthorizedKeysFile /d'      /etc/ssh/sshd_config
sed -i '/^PermitRootLogin /d'         /etc/ssh/sshd_config
sed -i '/^Port /d'                    /etc/ssh/sshd_config
sed -i '/^ListenAddress /d'           /etc/ssh/sshd_config

# ใส่ค่าที่ต้องการ (key-based + root ด้วยกุญแจเท่านั้น)
cat >> /etc/ssh/sshd_config <<'EOF'
Port 22
ListenAddress 0.0.0.0
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
PermitRootLogin prohibit-password
PasswordAuthentication no
EOF

# ตรวจสอบไวยากรณ์ + รีสตาร์ท
/usr/sbin/sshd -t && service ssh restart

--------

# เช็กค่าจริงที่มีผล
sshd -T | egrep 'port|listenaddress|pubkeyauthentication|authorizedkeysfile|permitrootlogin|passwordauthentication'

# ควรได้
```
port 22
listenaddress 0.0.0.0
pubkeyauthentication yes
authorizedkeysfile .ssh/authorized_keys
permitrootlogin prohibit-password
passwordauthentication no
```
