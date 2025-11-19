#!/bin/bash
# Quick script to retrieve your deployed application URLs
# Useful when you start a new Learner Lab session

set -e

REGION=${AWS_REGION:-us-east-1}
LAMBDA_FUNCTION_NAME="leave-mgmt-agent"

echo "========================================="
echo "Retrieving Application URLs"
echo "========================================="
echo ""

# Get Lambda Function URL
echo "Looking up Lambda Function URL..."
FUNCTION_URL=$(aws lambda get-function-url-config \
    --function-name $LAMBDA_FUNCTION_NAME \
    --region $REGION \
    --query 'FunctionUrl' \
    --output text 2>/dev/null || echo "")

if [ ! -z "$FUNCTION_URL" ] && [ "$FUNCTION_URL" != "None" ]; then
    echo "✓ Backend API: ${FUNCTION_URL}"
else
    echo "✗ Lambda function URL not found"
    echo "  Function might not exist. Run: ./cloud_deploy.sh"
fi

# Get S3 Website URLs
echo ""
echo "Looking up S3 Frontend buckets..."
BUCKETS=$(aws s3 ls | grep leave-mgmt-frontend | awk '{print $3}')

if [ ! -z "$BUCKETS" ]; then
    for bucket in $BUCKETS; do
        WEBSITE_URL="http://${bucket}.s3-website-${REGION}.amazonaws.com"
        echo "✓ Frontend: ${WEBSITE_URL}"
    done
else
    echo "✗ No frontend buckets found"
    echo "  Run: ./cloud_deploy.sh"
fi

# Check DynamoDB tables
echo ""
echo "Checking DynamoDB tables..."
TABLES=$(aws dynamodb list-tables --region $REGION --query 'TableNames' --output json)

if echo $TABLES | grep -q "EngineerAvailability"; then
    echo "✓ EngineerAvailability table exists"
else
    echo "✗ EngineerAvailability table not found"
fi

if echo $TABLES | grep -q "LeaveQuota"; then
    echo "✓ LeaveQuota table exists"
else
    echo "✗ LeaveQuota table not found"
fi

if echo $TABLES | grep -q "LeaveRequests"; then
    echo "✓ LeaveRequests table exists"
else
    echo "✗ LeaveRequests table not found"
fi

echo ""
echo "========================================="
echo ""

