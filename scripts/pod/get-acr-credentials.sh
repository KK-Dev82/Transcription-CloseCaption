#!/bin/bash
# Script สำหรับดึง ACR Credentials สำหรับ RunPod Registry Auth
#
# วิธีใช้งาน:
# bash scripts/pod/get-acr-credentials.sh

set -e

ACR_NAME="kksenateacr"

echo "🔐 Getting ACR Credentials for RunPod Registry Auth..."
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in
if ! az account show &> /dev/null; then
    echo "🔑 Logging in to Azure..."
    az login
fi

echo "📋 ACR Name: $ACR_NAME"
echo ""

# Option 1: Admin Credentials
echo "═══════════════════════════════════════════════════════════════"
echo "Option 1: Admin Credentials (ง่ายที่สุด)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Enable Admin User (ถ้ายังไม่เปิด)
echo "🔧 Enabling Admin User..."
az acr update --name $ACR_NAME --admin-enabled true

# Get Username
USERNAME=$(az acr credential show --name $ACR_NAME --query "username" -o tsv)
echo "✅ Username: $USERNAME"

# Get Password
PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
echo "✅ Password: $PASSWORD"
echo ""

echo "📝 ใช้ใน RunPod Template:"
echo "   Registry URL: ${ACR_NAME}.azurecr.io"
echo "   Username: $USERNAME"
echo "   Password: $PASSWORD"
echo ""

# Option 2: Service Principal
echo "═══════════════════════════════════════════════════════════════"
echo "Option 2: Service Principal (Production - แนะนำ)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

read -p "สร้าง Service Principal? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Get Subscription ID
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
    echo "📋 Subscription ID: $SUBSCRIPTION_ID"
    
    # Get Resource Group
    RESOURCE_GROUP=$(az acr show --name $ACR_NAME --query resourceGroup -o tsv)
    echo "📋 Resource Group: $RESOURCE_GROUP"
    
    # Get ACR Resource ID
    ACR_ID=$(az acr show --name $ACR_NAME --query id -o tsv)
    echo "📋 ACR Resource ID: $ACR_ID"
    echo ""
    
    # Create Service Principal
    echo "🔧 Creating Service Principal..."
    SP_OUTPUT=$(az ad sp create-for-rbac \
      --name "runpod-transcription-deployer" \
      --role AcrPull \
      --scopes $ACR_ID \
      --output json)
    
    APP_ID=$(echo $SP_OUTPUT | jq -r '.appId')
    SP_PASSWORD=$(echo $SP_OUTPUT | jq -r '.password')
    TENANT_ID=$(echo $SP_OUTPUT | jq -r '.tenant')
    
    echo ""
    echo "✅ Service Principal Created!"
    echo ""
    echo "📝 ใช้ใน RunPod Template:"
    echo "   Registry URL: ${ACR_NAME}.azurecr.io"
    echo "   Username: $APP_ID"
    echo "   Password: $SP_PASSWORD"
    echo ""
    echo "📋 Service Principal Details:"
    echo "   App ID: $APP_ID"
    echo "   Tenant ID: $TENANT_ID"
    echo ""
    echo "⚠️  เก็บ Password ไว้ให้ดี - จะแสดงแค่ครั้งเดียว!"
fi

echo ""
echo "✅ Done!"
echo ""
echo "💡 Next Steps:"
echo "   1. Copy credentials ด้านบน"
echo "   2. ไปที่ RunPod Template → Registry Auth"
echo "   3. ใส่ Registry URL, Username, Password"
echo ""

