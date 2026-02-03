# Shell Command

```
KEY_CONTENT='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAx3EeF3VBJ7ZIio1r3j7dD0Xe06DDv5Z7ekcG66YDpB goataog@gmail.com'
SSHD_CONFIG="/etc/ssh/sshd_config"

install -d -m 700 -o root -g root /root/.ssh
touch /root/.ssh/authorized_keys
chown root:root /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
sed -i 's/\r$//' /root/.ssh/authorized_keys
grep -Fxq "$KEY_CONTENT" /root/.ssh/authorized_keys || echo "$KEY_CONTENT" >> /root/.ssh/authorized_keys

[ -f "$SSHD_CONFIG" ] && cp -a "$SSHD_CONFIG" "${SSHD_CONFIG}.bak.$(date +%Y%m%d-%H%M%S)"
sed -i '/^PasswordAuthentication /d; /^PubkeyAuthentication /d; /^AuthorizedKeysFile /d; /^PermitRootLogin /d; /^Port /d; /^ListenAddress /d' "$SSHD_CONFIG"
cat >> "$SSHD_CONFIG" << 'EOF'
Port 22
ListenAddress 0.0.0.0
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
PermitRootLogin prohibit-password
PasswordAuthentication no
EOF
sshd -t && (systemctl reload sshd 2>/dev/null || systemctl reload ssh 2>/dev/null || service sshd reload 2>/dev/null || service ssh reload 2>/dev/null)
echo "[*] เสร็จ - ล็อกอินด้วยคีย์ได้โดยไม่ต้องใส่รหัสผ่าน"
```