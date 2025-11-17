#!/bin/bash
# Script to package and deploy Lambda function for Leave Management System
# Usage: ./scripts/deploy_lambda.sh [function-name] [region]

set -e

FUNCTION_NAME=${1:-leave-management-agent}
REGION=${2:-us-east-1}
PACKAGE_DIR="lambda-package"
ZIP_FILE="lambda-agent.zip"

echo "========================================="
echo "Lambda Deployment Script"
echo "========================================="
echo "Function Name: $FUNCTION_NAME"
echo "Region: $REGION"
echo ""

# Clean up previous package
echo "Cleaning up previous package..."
rm -rf $PACKAGE_DIR
rm -f $ZIP_FILE

# Create package directory
echo "Creating package directory..."
mkdir -p $PACKAGE_DIR

# Copy agent code
echo "Copying agent code..."
cp -r src/agent/* $PACKAGE_DIR/
cp src/config.py $PACKAGE_DIR/

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -t $PACKAGE_DIR/ --quiet

# Create zip file
echo "Creating zip file..."
cd $PACKAGE_DIR
zip -r ../$ZIP_FILE . -q
cd ..

# Check if function exists
echo "Checking if Lambda function exists..."
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION > /dev/null 2>&1; then
    echo "Function exists. Updating code..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$ZIP_FILE \
        --region $REGION
    
    echo "Waiting for update to complete..."
    aws lambda wait function-updated \
        --function-name $FUNCTION_NAME \
        --region $REGION
    
    echo "Function updated successfully!"
else
    echo "Function does not exist. Please create it first using AWS Console or CLI."
    echo "Use the following command:"
    echo ""
    echo "aws lambda create-function \\"
    echo "  --function-name $FUNCTION_NAME \\"
    echo "  --runtime python3.9 \\"
    echo "  --role arn:aws:iam::<account-id>:role/LeaveManagementLambdaRole \\"
    echo "  --handler agent.lambda_handler.lambda_handler \\"
    echo "  --zip-file fileb://$ZIP_FILE \\"
    echo "  --timeout 60 \\"
    echo "  --memory-size 512 \\"
    echo "  --region $REGION"
    echo ""
    echo "Package created: $ZIP_FILE"
fi

# Clean up
echo "Cleaning up..."
rm -rf $PACKAGE_DIR

echo ""
echo "========================================="
echo "Deployment complete!"
echo "========================================="



