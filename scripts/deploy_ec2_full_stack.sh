#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Leave Management - EC2 Full Stack Deployment   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════╝${NC}"
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

# Load environment variables from project root
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
    echo -e "${GREEN}✅ Loaded environment variables${NC}"
elif [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo -e "${GREEN}✅ Loaded environment variables${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: .env file not found${NC}"
fi
echo ""

INSTANCE_TYPE="t2.micro"
REGION="us-east-1"
KEY_NAME="vockey"

echo -e "${YELLOW}📋 This script will:${NC}"
echo "1. Launch a t2.micro EC2 instance"
echo "2. Install Node.js and Python"
echo "3. Deploy your frontend"
echo "4. Create a proxy server to Lambda"
echo "5. Give you a public URL to access everything"
echo ""
read -p "Press Enter to continue..."
echo ""

# Get the latest Amazon Linux 2 AMI
echo -e "${BLUE}🔍 Finding Amazon Linux 2 AMI...${NC}"
AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text \
    --region $REGION)

echo "AMI ID: $AMI_ID"

# Create security group
echo -e "${BLUE}🔒 Creating security group...${NC}"
SG_ID=$(aws ec2 create-security-group \
    --group-name leave-mgmt-sg \
    --description "Leave Management System Web Server" \
    --region $REGION \
    --query 'GroupId' \
    --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
    --group-names leave-mgmt-sg \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region $REGION)

echo "Security Group: $SG_ID"

# Allow HTTP traffic
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 \
    --region $REGION 2>/dev/null || echo "HTTP rule already exists"

# Allow port 3000 (React dev server)
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 3000 \
    --cidr 0.0.0.0/0 \
    --region $REGION 2>/dev/null || echo "Port 3000 rule already exists"

# Allow SSH (for debugging)
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0 \
    --region $REGION 2>/dev/null || echo "SSH rule already exists"

# Upload frontend source code to S3 for EC2 to build
echo -e "${BLUE}📦 Preparing frontend source for EC2 build...${NC}"

# Check if frontend directory exists
if [ ! -d "frontend" ]; then
    echo -e "${RED}❌ Error: frontend directory not found${NC}"
    exit 1
fi

# Create a temporary directory for packaging
TEMP_DIR=$(mktemp -d)
echo -e "${BLUE}📁 Packaging frontend source...${NC}"

# Copy frontend source (excluding node_modules and build directories)
cd frontend
tar --exclude='node_modules' \
    --exclude='build' \
    --exclude='.git' \
    --exclude='.env.local' \
    -czf "$TEMP_DIR/frontend-source.tar.gz" .

cd "$PROJECT_ROOT"

# Upload frontend source to S3
echo -e "${BLUE}📤 Uploading frontend source to S3...${NC}"
if ! aws s3 cp "$TEMP_DIR/frontend-source.tar.gz" s3://${LEAVE_MGMT_S3_BUCKET}/app/frontend-source.tar.gz --region $REGION; then
    echo -e "${RED}❌ Error: Failed to upload frontend source to S3${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Cleanup temp directory
rm -rf "$TEMP_DIR"
echo -e "${GREEN}✅ Frontend source uploaded to S3 (will be built on EC2)${NC}"

# Create user data script
cat > user-data.sh << 'USERDATA'
#!/bin/bash
set -x
exec > /var/log/user-data.log 2>&1

# Update system
yum update -y

# Install Node.js 18
curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
yum install -y nodejs

# Install Python 3 and pip
yum install -y python3 python3-pip

# Install AWS CLI (should already be installed but ensure latest)
pip3 install --upgrade awscli boto3

# Install nginx
amazon-linux-extras install nginx1 -y

# Create app directory
mkdir -p /opt/leave-mgmt
cd /opt/leave-mgmt

# Download and build frontend on EC2
echo "Downloading frontend source from S3..."
# Retry logic - wait for S3 upload to complete
RETRY_COUNT=0
MAX_RETRIES=10
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if aws s3 cp s3://BUCKET_NAME/app/frontend-source.tar.gz /opt/leave-mgmt/frontend-source.tar.gz 2>&1; then
        echo "Frontend source downloaded successfully"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for frontend source in S3... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 5
done

if [ ! -f /opt/leave-mgmt/frontend-source.tar.gz ]; then
    echo "ERROR: Failed to download frontend source from S3"
    exit 1
fi

# Extract frontend source
echo "Extracting frontend source..."
cd /opt/leave-mgmt
mkdir -p frontend-build
cd frontend-build
tar -xzf /opt/leave-mgmt/frontend-source.tar.gz
rm /opt/leave-mgmt/frontend-source.tar.gz

# Set environment variable for API URL (empty = relative paths)
echo "REACT_APP_API_URL=" > .env

# Install npm dependencies
echo "Installing npm dependencies..."
npm install --production=false

# Build React application
echo "Building React application..."
npm run build

# Check if build was successful
if [ ! -d "build" ] || [ ! -f "build/index.html" ]; then
    echo "ERROR: Build failed - build directory or index.html not found"
    exit 1
fi

# Copy build to nginx html directory
echo "Copying build to nginx directory..."
cp -r build/* /usr/share/nginx/html/

# Clean up build files to save space
echo "Cleaning up build files..."
cd /opt/leave-mgmt
rm -rf frontend-build

echo "Frontend build completed successfully"

# Create a simple proxy server
cat > /opt/leave-mgmt/proxy-server.js << 'EOF'
const http = require('http');
const { exec } = require('child_process');
const url = require('url');

const PORT = 3001;
const LAMBDA_FUNCTION = 'leave-mgmt-agent';

const server = http.createServer((req, res) => {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  let body = '';
  req.on('data', chunk => { body += chunk.toString(); });
  req.on('end', () => {
    const pathname = url.parse(req.url).pathname;
    
    // Build Lambda payload
    let payload = {
      requestContext: { http: { method: req.method, path: pathname } },
      body: body
    };
    
    const payloadStr = JSON.stringify(JSON.stringify(payload));
    const cmd = `aws lambda invoke --function-name ${LAMBDA_FUNCTION} --payload ${payloadStr} /tmp/response.json && cat /tmp/response.json`;
    
    exec(cmd, (error, stdout, stderr) => {
      if (error) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: error.message }));
        return;
      }
      
      try {
        const lambdaResponse = JSON.parse(stdout);
        const statusCode = lambdaResponse.statusCode || 200;
        const headers = lambdaResponse.headers || {};
        const responseBody = lambdaResponse.body || stdout;
        
        res.writeHead(statusCode, { ...headers, 'Content-Type': 'application/json' });
        res.end(responseBody);
      } catch (e) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(stdout);
      }
    });
  });
});

server.listen(PORT, () => {
  console.log(`Proxy server running on port ${PORT}`);
});
EOF

# Start proxy server
node /opt/leave-mgmt/proxy-server.js > /var/log/proxy.log 2>&1 &

# Wait a moment for proxy server to start
sleep 2

# Configure nginx to serve React app and proxy API requests
cat > /etc/nginx/conf.d/leave-mgmt.conf << 'NGINXCONF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json application/javascript;

    # Serve static files
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Proxy API requests to Lambda proxy server
    location ~ ^/(chat|employees|api) {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Handle React Router (SPA) - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
        expires -1;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # Error pages
    error_page 404 /index.html;
}
NGINXCONF

# Remove default nginx config to avoid conflicts
rm -f /etc/nginx/conf.d/default.conf

# Test nginx configuration
nginx -t || echo "Nginx config test failed, but continuing..."

# Enable and start nginx
systemctl enable nginx
systemctl restart nginx

# Create health check page (backup)
echo "<h1>Leave Management System</h1><p>Server is running!</p><p>If you see this, frontend may still be downloading from S3. Wait a moment and refresh.</p>" > /usr/share/nginx/html/health.html

echo "Setup complete!" > /var/log/user-data-complete.txt
USERDATA

# Replace BUCKET_NAME in user data
sed -i "s/BUCKET_NAME/${LEAVE_MGMT_S3_BUCKET}/g" user-data.sh

# Launch EC2 instance
echo -e "${BLUE}🚀 Launching EC2 instance...${NC}"

# Try to launch with IAM instance profile first, fallback without it if permission denied
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $SG_ID \
    --iam-instance-profile Name=LabInstanceProfile \
    --user-data file://user-data.sh \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=leave-mgmt-server}]" \
    --region $REGION \
    --query 'Instances[0].InstanceId' \
    --output text 2>&1)

# Check if we got an error about IAM permissions
if echo "$INSTANCE_ID" | grep -q "UnauthorizedOperation\|iam:PassRole"; then
    echo -e "${YELLOW}⚠️  Cannot attach IAM instance profile (permission denied), launching without it...${NC}"
    echo -e "${YELLOW}   Note: EC2 will use default credentials. Ensure S3 and Lambda access is configured.${NC}"
    INSTANCE_ID=$(aws ec2 run-instances \
        --image-id $AMI_ID \
        --instance-type $INSTANCE_TYPE \
        --key-name $KEY_NAME \
        --security-group-ids $SG_ID \
        --user-data file://user-data.sh \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=leave-mgmt-server}]" \
        --region $REGION \
        --query 'Instances[0].InstanceId' \
        --output text)
fi

echo "Instance ID: $INSTANCE_ID"

# Wait for instance to be running
echo -e "${YELLOW}⏳ Waiting for instance to start...${NC}"
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $REGION

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text \
    --region $REGION)

echo -e "${GREEN}✅ EC2 instance launched!${NC}"
echo "Public IP: $PUBLIC_IP"
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

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          🎉 DEPLOYMENT COMPLETE! 🎉               ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📋 Your Application:${NC}"
echo ""
echo "   🌐 Website URL: http://${PUBLIC_IP}"
echo "   ⏳ Wait 3-5 minutes for setup and build to complete"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Wait for instance initialization and frontend build (3-5 minutes)"
echo "2. Check health: curl http://${PUBLIC_IP}/health.html"
echo "3. Access your website: http://${PUBLIC_IP}"
echo ""
echo -e "${YELLOW}⚠️  Note:${NC}"
echo "   The frontend source will be downloaded and built on EC2."
echo "   This may take 3-5 minutes (npm install + build)."
echo "   If the site doesn't load, wait a few more minutes and refresh."
echo "   Check build progress: ssh -i ~/.ssh/labsuser.pem ec2-user@${PUBLIC_IP} 'sudo tail -f /var/log/user-data.log'"
echo ""
echo "Deployment info saved to: deployment-info.txt"
echo ""

# Cleanup
rm -f user-data.sh

