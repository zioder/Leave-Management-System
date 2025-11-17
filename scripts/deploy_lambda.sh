#!/bin/bash
# Script to package and deploy Lambda function for Leave Management System
# Usage: ./scripts/deploy_lambda.sh [function-name] [region]

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

FUNCTION_NAME=${1:-leave-mgmt-agent}
REGION=${2:-us-east-1}
PACKAGE_DIR="lambda-package"
ZIP_FILE="lambda-agent.zip"

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Lambda Deployment Script${NC}"
echo -e "${BLUE}=========================================${NC}"
echo "Function Name: $FUNCTION_NAME"
echo "Region: $REGION"
echo ""

# Determine project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -d "$SCRIPT_DIR/../src" ]; then
    PROJECT_ROOT="$SCRIPT_DIR/.."
elif [ -d "$SCRIPT_DIR/src" ]; then
    PROJECT_ROOT="$SCRIPT_DIR"
else
    echo -e "${RED}❌ Error: src directory not found${NC}"
    echo "Please run this script from the project root or scripts directory"
    exit 1
fi

# Change to project root
cd "$PROJECT_ROOT"
echo -e "${GREEN}📁 Working directory: $(pwd)${NC}"
echo ""

# Load environment variables if available
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Clean up previous package
echo "Cleaning up previous package..."
rm -rf $PACKAGE_DIR
rm -f $ZIP_FILE

# Create package directory
echo "Creating package directory..."
mkdir -p $PACKAGE_DIR

# Copy agent code
echo "Copying agent code..."
cp -r src/agent $PACKAGE_DIR/
cp -r src/storage $PACKAGE_DIR/
cp src/config.py $PACKAGE_DIR/

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -t $PACKAGE_DIR/ --quiet

# Create zip file
echo "Creating zip file..."
cd $PACKAGE_DIR
zip -r ../$ZIP_FILE . -q
cd ..

# Get account ID for IAM role
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Check if function exists
echo "Checking if Lambda function exists..."
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Function exists. Updating code...${NC}"
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$ZIP_FILE \
        --region $REGION > /dev/null
    
    echo "Waiting for update to complete..."
    aws lambda wait function-updated \
        --function-name $FUNCTION_NAME \
        --region $REGION
    
    echo -e "${GREEN}✅ Function updated successfully!${NC}"
else
    echo -e "${YELLOW}⚠️  Function does not exist. Creating it...${NC}"
    
    # Try to find an existing Lambda role
    LAMBDA_ROLE=$(aws iam list-roles --query "Roles[?contains(RoleName, 'Lambda') || contains(RoleName, 'LabRole')].Arn | [0]" --output text)
    
    if [ -z "$LAMBDA_ROLE" ] || [ "$LAMBDA_ROLE" == "None" ]; then
        echo -e "${RED}❌ Error: No suitable IAM role found${NC}"
        echo "For AWS Academy accounts, you typically need to use 'LabRole'"
        echo ""
        echo "Available roles:"
        aws iam list-roles --query "Roles[*].[RoleName,Arn]" --output table
        echo ""
        echo "Please specify a role ARN manually:"
        echo "aws lambda create-function \\"
        echo "  --function-name $FUNCTION_NAME \\"
        echo "  --runtime python3.11 \\"
        echo "  --role arn:aws:iam::$ACCOUNT_ID:role/LabRole \\"
        echo "  --handler agent.lambda_handler.lambda_handler \\"
        echo "  --zip-file fileb://$ZIP_FILE \\"
        echo "  --timeout 60 \\"
        echo "  --memory-size 512 \\"
        echo "  --environment Variables={LEAVE_MGMT_S3_BUCKET=${LEAVE_MGMT_S3_BUCKET},GEMINI_API_KEY=${GEMINI_API_KEY}} \\"
        echo "  --region $REGION"
        exit 1
    fi
    
    echo "Using IAM role: $LAMBDA_ROLE"
    
    # Create the function
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime python3.11 \
        --role $LAMBDA_ROLE \
        --handler agent.lambda_handler.lambda_handler \
        --zip-file fileb://$ZIP_FILE \
        --timeout 60 \
        --memory-size 512 \
        --environment Variables="{LEAVE_MGMT_S3_BUCKET=${LEAVE_MGMT_S3_BUCKET},GEMINI_API_KEY=${GEMINI_API_KEY}}" \
        --region $REGION > /dev/null
    
    echo "Waiting for function to be active..."
    aws lambda wait function-active \
        --function-name $FUNCTION_NAME \
        --region $REGION
    
    echo -e "${GREEN}✅ Function created successfully!${NC}"
fi

# Clean up
echo "Cleaning up..."
rm -rf $PACKAGE_DIR

echo ""
echo "========================================="
echo "Deployment complete!"
echo "========================================="



