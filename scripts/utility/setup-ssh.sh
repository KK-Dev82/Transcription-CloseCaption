#!/usr/bin/env bash
set -euo pipefail

# ===== ตั้งค่าเบื้องต้น =====
SSH_USER="root"
SSH_HOME="/root"
AUTHORIZED_KEYS="${SSH_HOME}/.ssh/authorized_keys"
SSHD_CONFIG="/etc/ssh/sshd_config"
KEY_CONTENT='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAx3EeF3VBJ7ZIio1r3j7dD0Xe06DDv5Z7ekcG66YDpB goataog@gmail.com'

# ===== ฟังก์ชันช่วยเหลือ =====
err() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[*] $*"; }

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    err "กรุณารันด้วยสิทธิ์ root"
  fi
}

check_openssh() {
  if ! command -v sshd >/dev/null 2>&1; then
    err "ไม่พบ OpenSSH server (sshd). ติดตั้งแพ็กเกจก่อนแล้วลองใหม่"
  fi
}

backup_config() {
  if [[ -f "${SSHD_CONFIG}" ]]; then
    local ts
    ts="$(date +%Y%m%d-%H%M%S)"
    cp -a "${SSHD_CONFIG}" "${SSHD_CONFIG}.bak.${ts}"
    info "สำรองไฟล์คอนฟิกไว้ที่ ${SSHD_CONFIG}.bak.${ts}"
  else
    err "ไม่พบไฟล์ ${SSHD_CONFIG}"
  fi
}

write_authorized_keys(){
  info "ตรวจและเพิ่มคีย์เข้า ${AUTHORIZED_KEYS}"

  # จัดการ permissions ของ /root (ตาม doc)
  chown root:root "${SSH_HOME}"
  chmod 700 "${SSH_HOME}"

  install -d -m 700 -o root -g root "${SSH_HOME}/.ssh"

  # ถ้าไฟล์ยังไม่มีให้สร้างว่าง
  touch "${AUTHORIZED_KEYS}"
  chown root:root "${AUTHORIZED_KEYS}"
  chmod 600 "${AUTHORIZED_KEYS}"

  # ลบ \r เผื่อ key มี CRLF
  sed -i 's/\r$//' "${AUTHORIZED_KEYS}"

  # ตรวจว่ามี key นี้อยู่หรือยัง
  if grep -Fxq "${KEY_CONTENT}" "${AUTHORIZED_KEYS}"; then
      info "คีย์นี้มีอยู่แล้ว → ข้าม"
  else
      echo "${KEY_CONTENT}" >> "${AUTHORIZED_KEYS}"
      info "เพิ่มคีย์ใหม่เรียบร้อย"
  fi
}


update_sshd_config() {
  info "ทำความสะอาด directive ที่ซ้ำซ้อนใน ${SSHD_CONFIG}"
  # ลบบรรทัดเดิมที่เกี่ยวข้อง (แบบตรงตัว เพื่อความชัดเจน)
  sed -i '/^PasswordAuthentication /d' "${SSHD_CONFIG}"
  sed -i '/^PubkeyAuthentication /d'    "${SSHD_CONFIG}"
  sed -i '/^AuthorizedKeysFile /d'      "${SSHD_CONFIG}"
  sed -i '/^PermitRootLogin /d'         "${SSHD_CONFIG}"
  sed -i '/^Port /d'                    "${SSHD_CONFIG}"
  sed -i '/^ListenAddress /d'           "${SSHD_CONFIG}"

  info "เขียนค่าที่ต้องการ (key-based + root ด้วยกุญแจเท่านั้น)"
  cat >> "${SSHD_CONFIG}" <<'EOF'
Port 22
ListenAddress 0.0.0.0
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
PermitRootLogin prohibit-password
PasswordAuthentication no
EOF
}

test_and_reload() {
  local SSHD_BIN
  SSHD_BIN="$(command -v sshd)"

  info "ตรวจสอบไวยากรณ์ด้วย: ${SSHD_BIN} -t"
  if ! "${SSHD_BIN}" -t; then
    err "คอนฟิก SSH ไม่ผ่านการตรวจสอบไวยากรณ์ - คืนค่าไฟล์สำรองแล้วลองใหม่"
  fi

  info "รีโหลด/รีสตาร์ทบริการ SSH"
  # พยายามเรียงลำดับที่ปลอดภัยที่สุด
  if command -v systemctl >/dev/null 2>&1; then
    systemctl reload sshd 2>/dev/null || systemctl reload ssh 2>/dev/null || \
    systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null || \
    err "ไม่สามารถรีโหลด/รีสตาร์ทผ่าน systemctl ได้"
  else
    service sshd reload 2>/dev/null || service ssh reload 2>/dev/null || \
    service sshd restart 2>/dev/null || service ssh restart 2>/dev/null || \
    err "ไม่สามารถรีโหลด/รีสตาร์ทผ่าน service ได้"
  fi
}

# ===== main =====
need_root
check_openssh
backup_config
write_authorized_keys
update_sshd_config
test_and_reload

info "เสร็จสิ้น ✅  ทดสอบล็อกอินด้วยคีย์ของคุณได้เลย (รอบนี้ปิดรหัสผ่านไว้แล้ว)"
