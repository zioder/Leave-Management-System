#!/bin/bash

# Check EC2 deployment status
REGION="us-east-1"

echo "🔍 Checking for Leave Management EC2 instances..."
echo ""

# Find the instance
INSTANCE_INFO=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=leave-mgmt-server" "Name=instance-state-name,Values=running,pending,stopping,stopped" \
    --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress,LaunchTime]' \
    --output table \
    --region $REGION)

if [ -z "$INSTANCE_INFO" ]; then
    echo "❌ No Leave Management instances found."
    echo ""
    echo "The deployment might have failed. Check if there's an error in the script."
    exit 1
fi

echo "$INSTANCE_INFO"
echo ""

# Get the most recent instance
INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=leave-mgmt-server" "Name=instance-state-name,Values=running,pending,stopping,stopped" \
    --query 'Reservations[*].Instances[*].[InstanceId,LaunchTime] | sort_by(@, &[1])[-1][0]' \
    --output text \
    --region $REGION)

echo "Most recent instance: $INSTANCE_ID"
echo ""

# Get instance state
STATE=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].State.Name' \
    --output text \
    --region $REGION)

echo "State: $STATE"
echo ""

if [ "$STATE" != "running" ]; then
    echo "⏳ Instance is not running yet. Waiting for it to start..."
    aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $REGION
    echo "✅ Instance is now running!"
fi

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text \
    --region $REGION)

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║          🎉 INSTANCE INFORMATION 🎉               ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo "State: $STATE"
echo ""
echo "🌐 Website URL: http://${PUBLIC_IP}"
echo "🏥 Health Check: http://${PUBLIC_IP}/health.html"
echo ""
echo "⏳ The setup is still running in the background."
echo "   Wait 3-5 minutes for the build to complete."
echo ""
echo "📝 To check setup progress:"
echo "   ssh -i ~/.ssh/labsuser.pem ec2-user@${PUBLIC_IP} 'sudo tail -f /var/log/user-data.log'"
echo ""
echo "🔍 To check if setup is complete:"
echo "   ssh -i ~/.ssh/labsuser.pem ec2-user@${PUBLIC_IP} 'ls -la /var/log/user-data-complete.txt'"
echo ""

