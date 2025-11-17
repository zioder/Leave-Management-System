#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up Lambda Function URL${NC}"
echo "======================================"
echo ""

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Configuration
LAMBDA_FUNCTION_NAME=${LAMBDA_FUNCTION_NAME:-"leave-mgmt-agent"}

echo -e "${BLUE}📋 Configuration:${NC}"
echo "   Lambda Function: $LAMBDA_FUNCTION_NAME"
echo ""

# Check if Lambda function exists
echo -e "${BLUE}🔍 Checking Lambda function...${NC}"
if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME &> /dev/null; then
    echo -e "${GREEN}✅ Lambda function found${NC}"
else
    echo -e "${RED}❌ Error: Lambda function '$LAMBDA_FUNCTION_NAME' not found${NC}"
    echo "Please deploy your Lambda function first"
    exit 1
fi

# Create or update Lambda Function URL
echo ""
echo -e "${BLUE}🌐 Creating Lambda Function URL...${NC}"

# Try to create function URL configuration
FUNCTION_URL=$(aws lambda create-function-url-config \
    --function-name $LAMBDA_FUNCTION_NAME \
    --auth-type NONE \
    --cors "AllowOrigins=*,AllowMethods=GET,POST,PUT,DELETE,OPTIONS,AllowHeaders=Content-Type,Authorization,X-Requested-With,MaxAge=86400" \
    --query 'FunctionUrl' \
    --output text 2>&1)

# If URL already exists, get the existing one
if echo "$FUNCTION_URL" | grep -q "ResourceConflictException"; then
    echo -e "${YELLOW}⚠️  Function URL already exists, retrieving...${NC}"
    FUNCTION_URL=$(aws lambda get-function-url-config \
        --function-name $LAMBDA_FUNCTION_NAME \
        --query 'FunctionUrl' \
        --output text)
fi

# Add public permission for function URL
echo ""
echo -e "${BLUE}🔐 Adding public access permission...${NC}"
aws lambda add-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --statement-id FunctionURLAllowPublicAccess \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE \
    &> /dev/null || echo -e "${YELLOW}Permission already exists${NC}"

echo -e "${GREEN}✅ Lambda Function URL configured!${NC}"
echo ""
echo -e "${GREEN}📋 Function URL Details:${NC}"
echo "   URL: $FUNCTION_URL"
echo ""
echo -e "${BLUE}🔗 Available Endpoints:${NC}"
echo "   POST ${FUNCTION_URL}chat"
echo "   GET  ${FUNCTION_URL}employees"
echo ""
echo -e "${YELLOW}📝 Testing the endpoint:${NC}"
echo '   curl -X POST "'${FUNCTION_URL}'" \'
echo '     -H "Content-Type: application/json" \'
echo '     -d '\''{"message":"Hello","is_admin":true}'\'
echo ""

# Test the endpoint
echo -e "${BLUE}🧪 Testing endpoint...${NC}"
RESPONSE=$(curl -s -X POST "${FUNCTION_URL}" \
    -H "Content-Type: application/json" \
    -d '{"message":"Hello","is_admin":true}' || echo "Error")

if echo "$RESPONSE" | grep -q "error\|Error"; then
    echo -e "${RED}⚠️  Test returned an error (this might be expected if data is not seeded):${NC}"
    echo "$RESPONSE"
else
    echo -e "${GREEN}✅ Endpoint is responding!${NC}"
fi

echo ""
echo -e "${GREEN}💾 Saving to .env file...${NC}"

# Update .env file
if [ -f .env ]; then
    # Remove old API_URL if exists
    sed -i.bak '/^REACT_APP_API_URL=/d' .env
    sed -i.bak '/^LAMBDA_FUNCTION_URL=/d' .env
fi

echo "REACT_APP_API_URL=$FUNCTION_URL" >> .env
echo "LAMBDA_FUNCTION_URL=$FUNCTION_URL" >> .env

echo -e "${GREEN}✅ Configuration saved to .env${NC}"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "   1. Deploy frontend with this URL:"
echo "      export REACT_APP_API_URL=$FUNCTION_URL"
echo "      ./scripts/deploy_frontend.sh"
echo ""
echo "   2. Or use PowerShell:"
echo "      \$env:REACT_APP_API_URL='$FUNCTION_URL'"
echo "      .\scripts\deploy_frontend.ps1"
echo ""

