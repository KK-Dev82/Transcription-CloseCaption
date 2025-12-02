mkdir -p /root/.ssh && chown root:root /root /root/.ssh && chmod 700 /root /root/.ssh

cat > /root/.ssh/authorized_keys <<'EOF'
ssh-ed25519 AAAA...YOUR_PUBLIC_KEY... athip-ch
EOF
chown root:root /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys


> ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICsF/zoSGze7Ty995PGsVQRK65N4c3ZtW0b1pWz+F+tu goataog@gmail.com


# เคลียร์ค่าซ้ำใน /etc/ssh/sshd_config ให้เหลือค่าที่ชัดเจนเดียว
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