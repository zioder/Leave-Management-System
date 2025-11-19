#!/bin/bash

PUBLIC_IP="3.87.86.24"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔍 Troubleshooting EC2 Deployment"
echo "=================================="
echo ""

# 1. Check if we can reach the instance
echo "1️⃣ Testing connectivity to $PUBLIC_IP..."
if ping -c 2 $PUBLIC_IP >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Instance is reachable${NC}"
else
    echo -e "${YELLOW}⚠️  Ping failed (this is normal if ICMP is blocked)${NC}"
fi
echo ""

# 2. Check if port 80 is open
echo "2️⃣ Checking if port 80 is accessible..."
timeout 5 bash -c "echo > /dev/tcp/$PUBLIC_IP/80" 2>/dev/null && echo -e "${GREEN}✅ Port 80 is open${NC}" || echo -e "${RED}❌ Port 80 is not accessible${NC}"
echo ""

# 3. Try to SSH and check status
echo "3️⃣ Connecting via SSH to check logs..."
if ssh -i ~/.ssh/labsuser.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 ec2-user@${PUBLIC_IP} 'echo "SSH connected"' >/dev/null 2>&1; then
    echo -e "${GREEN}✅ SSH connection successful${NC}"
    echo ""
    
    # Check if setup is complete
    echo "4️⃣ Checking setup status..."
    if ssh -i ~/.ssh/labsuser.pem -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP} 'test -f /var/log/user-data-complete.txt' 2>/dev/null; then
        echo -e "${GREEN}✅ Setup script completed${NC}"
    else
        echo -e "${YELLOW}⏳ Setup script still running...${NC}"
    fi
    echo ""
    
    # Check nginx status
    echo "5️⃣ Checking nginx status..."
    ssh -i ~/.ssh/labsuser.pem -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP} 'sudo systemctl status nginx' 2>/dev/null | grep -q "active (running)" && echo -e "${GREEN}✅ Nginx is running${NC}" || echo -e "${RED}❌ Nginx is not running${NC}"
    echo ""
    
    # Check if frontend build exists
    echo "6️⃣ Checking if frontend build exists..."
    ssh -i ~/.ssh/labsuser.pem -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP} 'ls -la /usr/share/nginx/html/index.html' 2>/dev/null && echo -e "${GREEN}✅ Frontend files exist${NC}" || echo -e "${YELLOW}⚠️  Frontend files not found${NC}"
    echo ""
    
    # Show last 30 lines of user-data log
    echo "7️⃣ Last 30 lines of setup log:"
    echo "=================================="
    ssh -i ~/.ssh/labsuser.pem -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP} 'sudo tail -30 /var/log/user-data.log'
    echo ""
    
    # Check for errors
    echo "8️⃣ Checking for errors in setup log..."
    ERROR_COUNT=$(ssh -i ~/.ssh/labsuser.pem -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP} 'sudo grep -i "error\|fail" /var/log/user-data.log | tail -10' | wc -l)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "${RED}⚠️  Found errors:${NC}"
        ssh -i ~/.ssh/labsuser.pem -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP} 'sudo grep -i "error\|fail" /var/log/user-data.log | tail -10'
    else
        echo -e "${GREEN}✅ No obvious errors found${NC}"
    fi
    echo ""
    
    # Check current processes
    echo "9️⃣ Checking if npm/node processes are running..."
    ssh -i ~/.ssh/labsuser.pem -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP} 'ps aux | grep -E "npm|node" | grep -v grep' || echo "No npm/node processes found"
    echo ""
    
else
    echo -e "${RED}❌ Cannot connect via SSH${NC}"
    echo "This might be a key pair or security group issue."
fi

echo ""
echo "=================================="
echo "📋 Summary & Next Steps:"
echo "=================================="
echo ""
echo "If setup is still running, wait a few more minutes."
echo "If nginx is not running, there may be a build error."
echo "Check the full log with:"
echo "  ssh -i ~/.ssh/labsuser.pem ec2-user@${PUBLIC_IP} 'sudo cat /var/log/user-data.log'"


