#!/bin/bash

# Build and Push to ACR for Staging Environment
# DEPRECATED: Use build-and-push-acr.sh instead (has better error handling and auto-login)
# This script is kept for backward compatibility

echo "⚠️  WARNING: This script is deprecated. Please use build-and-push-acr.sh instead."
echo "   build-and-push-acr.sh has better features:"
echo "   - Auto Azure/ACR login"
echo "   - Better error handling"
echo "   - Docker Buildx setup"
echo ""
read -p "Continue with build-staging.sh? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled. Please use: ./scripts/build-and-push-acr.sh"
    exit 1
fi

# Redirect to build-and-push-acr.sh
exec ./scripts/build-and-push-acr.sh
