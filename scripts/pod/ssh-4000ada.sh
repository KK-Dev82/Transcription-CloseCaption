#!/bin/bash
# Script สำหรับ SSH เข้า RTX 4000 Ada Server
# Usage: bash scripts/pod/ssh-4000ada.sh [command]

SSH_HOST="${SSH_4000ADA_HOST:-4000-ada}"

if [ $# -eq 0 ]; then
    # Interactive SSH session
    echo "🔌 Connecting to RTX 4000 Ada Server..."
    echo "   Host: $SSH_HOST"
    echo ""
    ssh "$SSH_HOST"
else
    # Execute command remotely
    ssh "$SSH_HOST" "$@"
fi

