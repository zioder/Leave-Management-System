#!/bin/bash

# Complete the deployment if it was interrupted
REGION="us-east-1"

echo "🔍 Finding your EC2 instance..."

# Get the most recent instance
INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=leave-mgmt-server" "Name=instance-state-name,Values=running,pending" \
    --query 'Reservations[*].Instances[*].[InstanceId,LaunchTime] | sort_by(@, &[1])[-1][0]' \
    --output text \
    --region $REGION)

if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" == "None" ]; then
    echo "❌ No running Leave Management instance found."
    echo "   You may need to re-run the deployment script."
    exit 1
fi

echo "✅ Found instance: $INSTANCE_ID"
echo ""

# Check if already running
STATE=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].State.Name' \
    --output text \
    --region $REGION)

if [ "$STATE" == "pending" ]; then
    echo "⏳ Instance is starting... Waiting for it to be running..."
    aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $REGION
    echo "✅ Instance is now running!"
fi

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text \
    --region $REGION)

# Get security group
SG_ID=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
    --output text \
    --region $REGION)

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║          🎉 DEPLOYMENT COMPLETE! 🎉               ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
echo "📋 Your Application:"
echo ""
echo "   🌐 Website URL: http://${PUBLIC_IP}"
echo "   ⏳ Wait 3-5 minutes for setup and build to complete"
echo ""
echo "📝 Next Steps:"
echo "1. Wait for instance initialization and frontend build (3-5 minutes)"
echo "2. Check health: curl http://${PUBLIC_IP}/health.html"
echo "3. Access your website: http://${PUBLIC_IP}"
echo ""
echo "⚠️  Note:"
echo "   The frontend source will be downloaded and built on EC2."
echo "   This may take 3-5 minutes (npm install + build)."
echo "   If the site doesn't load, wait a few more minutes and refresh."
echo ""
echo "🔧 Troubleshooting:"
echo "   Check logs: ssh -i ~/.ssh/labsuser.pem ec2-user@${PUBLIC_IP} 'sudo tail -100 /var/log/user-data.log'"
echo "   Check if complete: ssh -i ~/.ssh/labsuser.pem ec2-user@${PUBLIC_IP} 'ls -la /var/log/user-data-complete.txt'"
echo ""

# Create deployment info file
cat > deployment-info.txt << EOF
Leave Management System - Deployment Info
==========================================

EC2 Instance ID: $INSTANCE_ID
Public IP: $PUBLIC_IP
Security Group: $SG_ID

Access URLs:
- Website: http://${PUBLIC_IP}
- Health Check: http://${PUBLIC_IP}/health.html

SSH Access:
ssh -i ~/.ssh/labsuser.pem ec2-user@${PUBLIC_IP}

Logs:
- User Data: sudo cat /var/log/user-data.log
- Proxy: sudo cat /var/log/proxy.log
- Nginx: sudo cat /var/log/nginx/error.log

Management:
- Stop: aws ec2 stop-instances --instance-ids ${INSTANCE_ID}
- Start: aws ec2 start-instances --instance-ids ${INSTANCE_ID}
- Terminate: aws ec2 terminate-instances --instance-ids ${INSTANCE_ID}
EOF

echo "✅ Deployment info saved to: deployment-info.txt"
echo ""

