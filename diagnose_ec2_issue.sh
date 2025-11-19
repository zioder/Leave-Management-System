#!/bin/bash

echo "🔍 Diagnosing EC2 deployment issue..."
echo ""

REGION="us-east-1"

echo "1️⃣ Checking all EC2 instances in region..."
aws ec2 describe-instances \
    --query 'Reservations[*].Instances[*].[InstanceId,State.Name,Tags[?Key==`Name`].Value|[0],LaunchTime]' \
    --output table \
    --region $REGION

echo ""
echo "2️⃣ Checking security groups..."
aws ec2 describe-security-groups \
    --group-names leave-mgmt-sg \
    --region $REGION \
    --query 'SecurityGroups[0].[GroupId,GroupName,Description]' \
    --output table 2>/dev/null || echo "Security group leave-mgmt-sg exists"

echo ""
echo "3️⃣ Checking key pair 'vockey'..."
aws ec2 describe-key-pairs \
    --key-names vockey \
    --region $REGION \
    --query 'KeyPairs[0].[KeyName,KeyFingerprint]' \
    --output table 2>/dev/null || echo "❌ Key pair 'vockey' not found!"

echo ""
echo "4️⃣ Testing EC2 run-instances with dry-run..."
AMI_ID="ami-06124b567f8becfbd"
SG_ID=$(aws ec2 describe-security-groups \
    --group-names leave-mgmt-sg \
    --region $REGION \
    --query 'SecurityGroups[0].GroupId' \
    --output text)

echo "Testing without IAM instance profile..."
aws ec2 run-instances \
    --dry-run \
    --image-id $AMI_ID \
    --instance-type t2.micro \
    --key-name vockey \
    --security-group-ids $SG_ID \
    --region $REGION 2>&1 | grep -i "error\|unauthorized\|would succeed" || echo "Command completed"

echo ""
echo "5️⃣ Checking IAM permissions..."
aws sts get-caller-identity

echo ""
echo "6️⃣ Looking for recently created instances (last hour)..."
CUTOFF_TIME=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S 2>/dev/null || echo "2025-11-17T14:00:00")
aws ec2 describe-instances \
    --filters "Name=launch-time,Values=${CUTOFF_TIME}Z..*" \
    --query 'Reservations[*].Instances[*].[InstanceId,State.Name,LaunchTime,PublicIpAddress]' \
    --output table \
    --region $REGION

echo ""
echo "✅ Diagnosis complete!"


