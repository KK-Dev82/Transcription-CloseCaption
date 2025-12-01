#!/bin/bash
# Script สำหรับ SSH ไปยัง RunPod Pod
# Usage: bash scripts/pod/ssh-runpod.sh [command]

SSH_HOST="${RUNPOD_HOST:-calm-pink-turtle}"

if [ $# -eq 0 ]; then
    # Interactive SSH session
    ssh "$SSH_HOST"
else
    # Execute command remotely
    ssh "$SSH_HOST" "$@"
fi

