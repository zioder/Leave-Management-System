#!/bin/bash

# Test the deployment
REGION="us-east-1"

echo "🧪 Testing Leave Management Deployment..."
echo ""

# Get the instance
INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=leave-mgmt-server" "Name=instance-state-name,Values=running" \
    --query 'Reservations[*].Instances[*].[InstanceId,LaunchTime] | sort_by(@, &[1])[-1][0]' \
    --output text \
    --region $REGION)

if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "None" ]; then
    echo "❌ No running Leave Management instance found."
    exit 1
fi

PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text \
    --region $REGION)

echo "Instance: $INSTANCE_ID"
echo "IP: $PUBLIC_IP"
echo ""

echo "1️⃣ Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://${PUBLIC_IP}/health.html --max-time 5)
if [ "$HEALTH_RESPONSE" == "200" ]; then
    echo "   ✅ Health check passed (HTTP $HEALTH_RESPONSE)"
else
    echo "   ⚠️  Health check returned HTTP $HEALTH_RESPONSE (server may still be starting)"
fi
echo ""

echo "2️⃣ Testing main page..."
MAIN_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://${PUBLIC_IP}/ --max-time 5)
if [ "$MAIN_RESPONSE" == "200" ]; then
    echo "   ✅ Main page is accessible (HTTP $MAIN_RESPONSE)"
else
    echo "   ⚠️  Main page returned HTTP $MAIN_RESPONSE (build may still be in progress)"
fi
echo ""

echo "3️⃣ Checking if setup is complete..."
ssh -i ~/.ssh/labsuser.pem -o StrictHostKeyChecking=no -o ConnectTimeout=5 ec2-user@${PUBLIC_IP} 'ls /var/log/user-data-complete.txt 2>/dev/null' > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Setup is complete!"
else
    echo "   ⏳ Setup is still in progress..."
    echo "      Check progress: ssh -i ~/.ssh/labsuser.pem ec2-user@${PUBLIC_IP} 'sudo tail -20 /var/log/user-data.log'"
fi
echo ""

echo "🌐 Access your application at: http://${PUBLIC_IP}"
echo ""


