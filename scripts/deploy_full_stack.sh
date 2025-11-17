#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Leave Management System - Full Stack Deploy    ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# Load environment variables
if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please create .env file with your configuration"
    exit 1
fi

export $(grep -v '^#' .env | xargs)

# Check required environment variables
if [ -z "$LEAVE_MGMT_S3_BUCKET" ]; then
    echo -e "${RED}❌ Error: LEAVE_MGMT_S3_BUCKET not set in .env${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment loaded${NC}"
echo "   S3 Bucket: $LEAVE_MGMT_S3_BUCKET"
echo ""

# =============================================================================
# STEP 1: Redeploy Lambda
# =============================================================================
echo -e "${BLUE}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Step 1/3: Deploying Lambda Function             ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}📦 Creating Lambda deployment package...${NC}"
zip -r lambda-agent.zip src/agent src/storage src/config.py -x "*__pycache__*" "*.pyc" > /dev/null

echo -e "${BLUE}☁️  Uploading to S3...${NC}"
aws s3 cp lambda-agent.zip s3://$LEAVE_MGMT_S3_BUCKET/lambda/lambda-agent.zip

echo -e "${BLUE}🔄 Updating Lambda function...${NC}"
aws lambda update-function-code \
  --function-name leave-mgmt-agent \
  --s3-bucket $LEAVE_MGMT_S3_BUCKET \
  --s3-key lambda/lambda-agent.zip > /dev/null

# Wait for Lambda to be updated
echo -e "${YELLOW}⏳ Waiting for Lambda to be ready...${NC}"
aws lambda wait function-updated --function-name leave-mgmt-agent

echo -e "${GREEN}✅ Lambda function deployed!${NC}"
echo ""

# =============================================================================
# STEP 2: Setup Lambda Function URL
# =============================================================================
echo -e "${BLUE}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Step 2/3: Setting up Lambda Function URL        ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# Try to create function URL
FUNCTION_URL=$(aws lambda create-function-url-config \
    --function-name leave-mgmt-agent \
    --auth-type NONE \
    --cors "AllowOrigins=*,AllowMethods=GET,POST,PUT,DELETE,OPTIONS,AllowHeaders=Content-Type,Authorization,X-Requested-With,MaxAge=86400" \
    --query 'FunctionUrl' \
    --output text 2>&1)

# If URL already exists, get it
if echo "$FUNCTION_URL" | grep -q "ResourceConflictException"; then
    echo -e "${YELLOW}⚠️  Function URL already exists, retrieving...${NC}"
    FUNCTION_URL=$(aws lambda get-function-url-config \
        --function-name leave-mgmt-agent \
        --query 'FunctionUrl' \
        --output text)
fi

# Add permission
aws lambda add-permission \
    --function-name leave-mgmt-agent \
    --statement-id FunctionURLAllowPublicAccess \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE \
    &> /dev/null || true

echo -e "${GREEN}✅ Function URL configured!${NC}"
echo "   URL: $FUNCTION_URL"
echo ""

# Test the endpoint
echo -e "${BLUE}🧪 Testing Lambda endpoint...${NC}"
TEST_RESPONSE=$(curl -s -X POST "${FUNCTION_URL}" \
    -H "Content-Type: application/json" \
    -d '{"message":"test","is_admin":true}' || echo '{"error":"failed"}')

if echo "$TEST_RESPONSE" | grep -q "error"; then
    echo -e "${YELLOW}⚠️  Warning: Lambda test returned an error${NC}"
    echo "   This might be expected if data is not seeded yet"
else
    echo -e "${GREEN}✅ Lambda is responding correctly!${NC}"
fi
echo ""

# Update .env with function URL
echo -e "${BLUE}💾 Saving configuration...${NC}"
sed -i.bak '/^REACT_APP_API_URL=/d' .env
sed -i.bak '/^LAMBDA_FUNCTION_URL=/d' .env
echo "REACT_APP_API_URL=$FUNCTION_URL" >> .env
echo "LAMBDA_FUNCTION_URL=$FUNCTION_URL" >> .env
echo -e "${GREEN}✅ Configuration saved to .env${NC}"
echo ""

# =============================================================================
# STEP 3: Deploy Frontend
# =============================================================================
echo -e "${BLUE}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Step 3/3: Deploying Frontend                     ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# Set frontend bucket name
FRONTEND_BUCKET=${FRONTEND_BUCKET_NAME:-"leave-mgmt-frontend"}

cd frontend

# Create .env with API URL
echo "REACT_APP_API_URL=$FUNCTION_URL" > .env
echo -e "${GREEN}✅ Frontend environment configured${NC}"

# Install dependencies
echo -e "${BLUE}📦 Installing npm dependencies...${NC}"
npm install --quiet

# Build
echo -e "${BLUE}🔨 Building React application...${NC}"
npm run build > /dev/null

# Check if bucket exists
echo -e "${BLUE}☁️  Checking S3 bucket...${NC}"
if aws s3 ls "s3://${FRONTEND_BUCKET}" 2>&1 | grep -q 'NoSuchBucket'; then
    echo "   Creating bucket: ${FRONTEND_BUCKET}"
    aws s3 mb s3://${FRONTEND_BUCKET}
    
    # Configure for static website hosting
    aws s3 website s3://${FRONTEND_BUCKET} \
      --index-document index.html \
      --error-document index.html
    
    # Set bucket policy
    cat > /tmp/bucket-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::${FRONTEND_BUCKET}/*"
  }]
}
EOF
    
    aws s3api put-bucket-policy --bucket ${FRONTEND_BUCKET} --policy file:///tmp/bucket-policy.json
    
    # Disable block public access
    aws s3api put-public-access-block --bucket ${FRONTEND_BUCKET} --public-access-block-configuration \
      "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
    
    echo -e "${GREEN}   ✅ Bucket created and configured${NC}"
else
    echo -e "${GREEN}   ✅ Bucket exists${NC}"
fi

# Deploy to S3
echo -e "${BLUE}📤 Uploading frontend to S3...${NC}"
aws s3 sync build/ s3://${FRONTEND_BUCKET}/ --delete --quiet

cd ..

# Get website URL
REGION=$(aws configure get region)
WEBSITE_URL="http://${FRONTEND_BUCKET}.s3-website-${REGION}.amazonaws.com"

echo -e "${GREEN}✅ Frontend deployed!${NC}"
echo ""

# =============================================================================
# DEPLOYMENT COMPLETE
# =============================================================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          🎉 DEPLOYMENT COMPLETE! 🎉               ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📋 Deployment Summary:${NC}"
echo "   ✅ Lambda function deployed and updated"
echo "   ✅ Lambda Function URL configured"
echo "   ✅ Frontend built and deployed to S3"
echo ""
echo -e "${GREEN}🌐 Your Application URLs:${NC}"
echo "   Frontend: ${WEBSITE_URL}"
echo "   API:      ${FUNCTION_URL}"
echo ""
echo -e "${BLUE}📋 Quick Links:${NC}"
echo "   S3 Console:     https://s3.console.aws.amazon.com/s3/buckets/${FRONTEND_BUCKET}"
echo "   Lambda Console: https://console.aws.amazon.com/lambda/home#/functions/leave-mgmt-agent"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "   1. Visit: ${WEBSITE_URL}"
echo "   2. Test the chatbot interface"
echo "   3. Verify employee dropdown loads"
echo "   4. Try sending messages in admin mode"
echo ""
echo -e "${BLUE}💡 Useful Commands:${NC}"
echo "   View Lambda logs:"
echo "     aws logs tail /aws/lambda/leave-mgmt-agent --follow"
echo ""
echo "   Test API directly:"
echo "     curl -X POST '${FUNCTION_URL}' -H 'Content-Type: application/json' -d '{\"message\":\"test\",\"is_admin\":true}'"
echo ""
echo "   Redeploy frontend after changes:"
echo "     cd frontend && npm run build && aws s3 sync build/ s3://${FRONTEND_BUCKET}/ --delete"
echo ""

