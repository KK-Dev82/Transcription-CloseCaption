#!/bin/bash
# ตรวจสอบ tasks ค้าง — ใช้ python3 รัน (ไม่ใช่ bash)
cd "$(dirname "$0")/.."
python3 scripts/diagnose_stuck_processing.py "$@"
