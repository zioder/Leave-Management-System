#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
FRONTEND_BUCKET=${FRONTEND_BUCKET_NAME:-"leave-mgmt-frontend"}
API_URL=${REACT_APP_API_URL:-""}

echo -e "${BLUE}🚀 Leave Management System - Frontend Deployment${NC}"
echo "=================================================="
echo ""

# Determine project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -d "$SCRIPT_DIR/../frontend" ]; then
    PROJECT_ROOT="$SCRIPT_DIR/.."
elif [ -d "$SCRIPT_DIR/frontend" ]; then
    PROJECT_ROOT="$SCRIPT_DIR"
else
    echo -e "${RED}❌ Error: frontend directory not found${NC}"
    echo "Please ensure you're running this from the project root or scripts directory"
    exit 1
fi

# Change to project root
cd "$PROJECT_ROOT"
echo -e "${GREEN}📁 Working directory: $(pwd)${NC}"
echo ""

# Check if we're in the right directory
if [ ! -d "frontend" ]; then
    echo -e "${RED}❌ Error: frontend directory not found${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Check if API URL is provided
if [ -z "$API_URL" ]; then
    echo -e "${YELLOW}⚠️  Warning: REACT_APP_API_URL not set${NC}"
    echo "Please set your API Gateway URL:"
    echo "  export REACT_APP_API_URL=https://your-api.execute-api.region.amazonaws.com/prod"
    echo ""
    read -p "Enter API URL now (or press Enter to skip): " USER_API_URL
    if [ ! -z "$USER_API_URL" ]; then
        API_URL=$USER_API_URL
    fi
fi

# Navigate to frontend directory
cd frontend

# Create or update .env file
if [ ! -z "$API_URL" ]; then
    echo -e "${BLUE}📝 Configuring environment...${NC}"
    echo "REACT_APP_API_URL=${API_URL}" > .env
    echo "✅ API URL configured: ${API_URL}"
else
    echo -e "${YELLOW}⚠️  No API URL configured - app will use default${NC}"
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Error: Node.js is not installed${NC}"
    echo "Please install Node.js 16+ from https://nodejs.org/"
    exit 1
fi

# Install dependencies
echo ""
echo -e "${BLUE}📦 Installing dependencies...${NC}"
npm install

# Build
echo ""
echo -e "${BLUE}🔨 Building React application...${NC}"
npm run build

if [ ! -d "build" ]; then
    echo -e "${RED}❌ Error: Build failed - build directory not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Build successful!${NC}"

# Check if bucket exists, if not create it
echo ""
echo -e "${BLUE}☁️  Checking S3 bucket...${NC}"
if aws s3 ls "s3://${FRONTEND_BUCKET}" 2>&1 | grep -q 'NoSuchBucket'; then
    echo "Creating bucket: ${FRONTEND_BUCKET}"
    aws s3 mb s3://${FRONTEND_BUCKET}
    
    # Configure for static website hosting
    aws s3 website s3://${FRONTEND_BUCKET} \
      --index-document index.html \
      --error-document index.html
    
    # Set bucket policy for public read
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
    
    echo -e "${GREEN}✅ Bucket created and configured${NC}"
else
    echo -e "${GREEN}✅ Bucket exists${NC}"
fi

# Deploy to S3
echo ""
echo -e "${BLUE}📤 Uploading to S3...${NC}"
aws s3 sync build/ s3://${FRONTEND_BUCKET}/ \
  --delete \
  --cache-control "public, max-age=31536000" \
  --exclude "index.html" \
  --exclude "*.json"

# Upload index.html with no-cache (for SPA routing)
aws s3 cp build/index.html s3://${FRONTEND_BUCKET}/index.html \
  --cache-control "no-cache" \
  --content-type "text/html"

# Get website URL
REGION=$(aws configure get region)
WEBSITE_URL="http://${FRONTEND_BUCKET}.s3-website-${REGION}.amazonaws.com"

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo "=================================================="
echo ""
echo -e "${GREEN}🌐 Website URL:${NC}"
echo "   ${WEBSITE_URL}"
echo ""
echo -e "${BLUE}📋 Quick Links:${NC}"
echo "   S3 Console: https://s3.console.aws.amazon.com/s3/buckets/${FRONTEND_BUCKET}"
echo "   Website: ${WEBSITE_URL}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "   1. Visit the website URL above"
echo "   2. Test the chatbot interface"
echo "   3. Verify API connectivity"
if [ -z "$API_URL" ]; then
    echo "   4. Configure API Gateway endpoint if not done"
fi
echo ""

