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

# Check if frontend build already exists in S3
echo -e "${BLUE}📦 Checking frontend build in S3...${NC}"
if aws s3 ls s3://${LEAVE_MGMT_S3_BUCKET}/app/frontend/index.html --region $REGION 2>/dev/null; then
    echo -e "${GREEN}✅ Frontend build already exists in S3, skipping build step${NC}"
    echo -e "${YELLOW}💡 To rebuild, delete from S3 first: aws s3 rm s3://${LEAVE_MGMT_S3_BUCKET}/app/frontend/ --recursive${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend build not found in S3${NC}"
    echo ""
    echo -e "${BLUE}📋 You have two options:${NC}"
    echo ""
    echo -e "${YELLOW}Option 1: Build locally (Recommended - saves CloudShell space)${NC}"
    echo "  1. On your local machine, run:"
    echo "     cd frontend"
    echo "     echo 'REACT_APP_API_URL=' > .env"
    echo "     npm install"
    echo "     npm run build"
    echo "  2. Upload to S3:"
    echo "     aws s3 sync frontend/build/ s3://${LEAVE_MGMT_S3_BUCKET}/app/frontend/ --region $REGION"
    echo ""
    echo -e "${YELLOW}Option 2: Build in CloudShell (requires free disk space)${NC}"
    echo "  Press Enter to continue with CloudShell build..."
    echo "  (Or Ctrl+C to exit and build locally)"
    read -p "  Your choice: " choice
    
    # Check if frontend directory exists
    if [ ! -d "frontend" ]; then
        echo -e "${RED}❌ Error: frontend directory not found${NC}"
        exit 1
    fi
    
    # Find a location with available space for building
    # Check /tmp first (usually has more space), then /home
    BUILD_DIR=""
    TMP_SPACE=$(df -BM /tmp 2>/dev/null | tail -1 | awk '{print $4}' | sed 's/M//' || echo "0")
    HOME_SPACE=$(df -BM /home 2>/dev/null | tail -1 | awk '{print $4}' | sed 's/M//' || echo "0")
    
    if [ "$TMP_SPACE" -gt 2048 ]; then
        BUILD_DIR="/tmp/leave-mgmt-build-$$"
        echo -e "${BLUE}💾 Using /tmp for build (${TMP_SPACE}MB available)${NC}"
    elif [ "$HOME_SPACE" -gt 2048 ]; then
        BUILD_DIR="/home/leave-mgmt-build-$$"
        echo -e "${BLUE}💾 Using /home for build (${HOME_SPACE}MB available)${NC}"
    else
        echo -e "${RED}❌ Error: Insufficient disk space in /tmp (${TMP_SPACE}MB) and /home (${HOME_SPACE}MB)${NC}"
        echo -e "${YELLOW}📋 Please build locally instead:${NC}"
        echo ""
        echo "1. On your local machine, run:"
        echo "   cd frontend"
        echo "   echo 'REACT_APP_API_URL=' > .env"
        echo "   npm install"
        echo "   npm run build"
        echo ""
        echo "2. Upload to S3:"
        echo "   aws s3 sync frontend/build/ s3://${LEAVE_MGMT_S3_BUCKET}/app/frontend/ --region $REGION"
        echo ""
        echo "3. Then re-run this script - it will skip the build step"
        exit 1
    fi
    
    # Create build directory and copy frontend source
    echo -e "${BLUE}📁 Setting up build directory at ${BUILD_DIR}...${NC}"
    mkdir -p "$BUILD_DIR"
    cp -r frontend/* "$BUILD_DIR/"
    cd "$BUILD_DIR"
    
    # Configure npm to use the build directory's filesystem for cache and temp
    export npm_config_cache="$BUILD_DIR/.npm-cache"
    export TMPDIR="$BUILD_DIR/.tmp"
    mkdir -p "$npm_config_cache" "$TMPDIR"
    
    # Function to check and clean up disk space
    cleanup_disk_space() {
        echo -e "${YELLOW}🧹 Cleaning up disk space...${NC}"
        npm cache clean --force 2>/dev/null || true
        rm -rf "$BUILD_DIR/.npm-cache" 2>/dev/null || true
        rm -rf "$BUILD_DIR/.tmp" 2>/dev/null || true
        rm -rf "$BUILD_DIR/node_modules" 2>/dev/null || true
        # Clean up any partial node_modules
        if [ -d "node_modules" ] && [ ! -f "node_modules/.bin/react-scripts" ]; then
            echo -e "${YELLOW}Removing incomplete node_modules...${NC}"
            rm -rf node_modules
        fi
    }
    
    # Function to check disk space (returns available space in MB)
    check_disk_space() {
        df -BM . | tail -1 | awk '{print $4}' | sed 's/M//'
    }
    
    # Check available disk space (need at least 2GB for npm install)
    AVAILABLE_SPACE_MB=$(check_disk_space)
    AVAILABLE_SPACE_GB=$((AVAILABLE_SPACE_MB / 1024))
    
    echo -e "${BLUE}💾 Available disk space: ${AVAILABLE_SPACE_GB}GB (${AVAILABLE_SPACE_MB}MB)${NC}"
    
    # Install dependencies (need dev dependencies for build)
    echo -e "${BLUE}📥 Installing npm dependencies...${NC}"
    
    # Check if react-scripts is actually available (not just if node_modules exists)
    NEED_INSTALL=true
    if [ -d "node_modules" ] && [ -f "node_modules/.bin/react-scripts" ]; then
        echo -e "${GREEN}✅ node_modules exists and react-scripts found, checking if install is needed...${NC}"
        # Verify react-scripts works
        if ./node_modules/.bin/react-scripts --version > /dev/null 2>&1; then
            echo -e "${GREEN}✅ react-scripts is working, skipping install${NC}"
            NEED_INSTALL=false
        else
            echo -e "${YELLOW}⚠️  react-scripts found but not working, reinstalling...${NC}"
            rm -rf node_modules package-lock.json
        fi
    fi
    
    if [ "$NEED_INSTALL" = true ]; then
        # Try npm install, if it fails, check for ENOSPC and clean up
        if ! npm install 2>&1 | tee "$BUILD_DIR/npm-install.log"; then
            # Check if error is ENOSPC (no space left)
            if grep -q "ENOSPC\|no space left\|nospc" "$BUILD_DIR/npm-install.log"; then
                echo -e "${RED}❌ Error: No space left on device${NC}"
                echo -e "${YELLOW}🧹 Attempting to free up space...${NC}"
                cleanup_disk_space
                
                # Check space again
                AVAILABLE_SPACE_MB=$(check_disk_space)
                if [ "$AVAILABLE_SPACE_MB" -lt 2048 ]; then
                    echo -e "${RED}❌ Error: Still insufficient disk space after cleanup${NC}"
                    echo ""
                    echo -e "${YELLOW}📋 Please build locally instead:${NC}"
                    echo ""
                    echo "1. On your local machine, run:"
                    echo "   cd frontend"
                    echo "   echo 'REACT_APP_API_URL=' > .env"
                    echo "   npm install"
                    echo "   npm run build"
                    echo ""
                    echo "2. Upload to S3:"
                    echo "   aws s3 sync frontend/build/ s3://${LEAVE_MGMT_S3_BUCKET}/app/frontend/ --region $REGION"
                    echo ""
                    echo "3. Then re-run this script - it will skip the build step"
                    # Cleanup before exit
                    cd "$PROJECT_ROOT"
                    rm -rf "$BUILD_DIR"
                    exit 1
                fi
                
                echo -e "${YELLOW}⚠️  Retrying npm install after cleanup...${NC}"
                rm -rf node_modules package-lock.json
                if ! npm install; then
                    echo -e "${RED}❌ Error: npm install failed after cleanup${NC}"
                    echo "This is likely due to insufficient disk space in CloudShell"
                    echo ""
                    echo -e "${YELLOW}📋 Please build locally and upload to S3 manually${NC}"
                    # Cleanup before exit
                    cd "$PROJECT_ROOT"
                    rm -rf "$BUILD_DIR"
                    exit 1
                fi
            else
                echo -e "${YELLOW}⚠️  npm install failed, clearing cache and retrying...${NC}"
                cleanup_disk_space
                rm -rf node_modules package-lock.json
                if ! npm install; then
                    echo -e "${RED}❌ Error: npm install failed after cache clear${NC}"
                    echo "This is likely due to insufficient disk space in CloudShell"
                    echo ""
                    echo -e "${YELLOW}📋 Please build locally and upload to S3 manually${NC}"
                    # Cleanup before exit
                    cd "$PROJECT_ROOT"
                    rm -rf "$BUILD_DIR"
                    exit 1
                fi
            fi
        fi
        echo -e "${GREEN}✅ Dependencies installed successfully${NC}"
        
        # Verify react-scripts is now available
        if [ ! -f "node_modules/.bin/react-scripts" ]; then
            echo -e "${RED}❌ Error: react-scripts not found after installation${NC}"
            # Check if we have space before trying to install react-scripts
            AVAILABLE_SPACE_MB=$(check_disk_space)
            if [ "$AVAILABLE_SPACE_MB" -lt 500 ]; then
                echo -e "${RED}❌ Insufficient space to install react-scripts${NC}"
                echo -e "${YELLOW}📋 Please build locally and upload to S3 manually${NC}"
                # Cleanup before exit
                cd "$PROJECT_ROOT"
                rm -rf "$BUILD_DIR"
                exit 1
            fi
            echo "Attempting to install react-scripts directly..."
            if ! npm install react-scripts --save; then
                echo -e "${RED}❌ Error: Failed to install react-scripts${NC}"
                echo -e "${YELLOW}📋 Please build locally and upload to S3 manually${NC}"
                # Cleanup before exit
                cd "$PROJECT_ROOT"
                rm -rf "$BUILD_DIR"
                exit 1
            fi
        fi
    fi
    
    # Build with relative API URL (will use same origin as the website)
    # Set to empty string - api.js now handles empty string as relative paths
    echo -e "${BLUE}🔨 Building React application...${NC}"
    echo "REACT_APP_API_URL=" > .env
    
    if ! npm run build 2>&1 | tee "$BUILD_DIR/npm-build.log"; then
        echo -e "${RED}❌ Error: npm run build failed${NC}"
        
        # Check if error is ENOSPC (no space left)
        if grep -q "ENOSPC\|no space left\|nospc" "$BUILD_DIR/npm-build.log"; then
            echo -e "${RED}❌ Error: No space left on device during build${NC}"
            echo ""
            echo -e "${YELLOW}📋 Please build locally instead:${NC}"
            echo ""
            echo "1. On your local machine, run:"
            echo "   cd frontend"
            echo "   echo 'REACT_APP_API_URL=' > .env"
            echo "   npm install"
            echo "   npm run build"
            echo ""
            echo "2. Upload to S3:"
            echo "   aws s3 sync frontend/build/ s3://${LEAVE_MGMT_S3_BUCKET}/app/frontend/ --region $REGION"
            echo ""
            echo "3. Then re-run this script - it will skip the build step"
            # Cleanup before exit
            cd "$PROJECT_ROOT"
            rm -rf "$BUILD_DIR"
            exit 1
        fi
        
        # Check available space before attempting reinstall
        AVAILABLE_SPACE_MB=$(check_disk_space)
        if [ "$AVAILABLE_SPACE_MB" -lt 2048 ]; then
            echo -e "${RED}❌ Insufficient disk space to retry build${NC}"
            echo ""
            echo -e "${YELLOW}📋 Please build locally instead:${NC}"
            echo ""
            echo "1. On your local machine, run:"
            echo "   cd frontend"
            echo "   echo 'REACT_APP_API_URL=' > .env"
            echo "   npm install"
            echo "   npm run build"
            echo ""
            echo "2. Upload to S3:"
            echo "   aws s3 sync frontend/build/ s3://${LEAVE_MGMT_S3_BUCKET}/app/frontend/ --region $REGION"
            echo ""
            echo "3. Then re-run this script - it will skip the build step"
            # Cleanup before exit
            cd "$PROJECT_ROOT"
            rm -rf "$BUILD_DIR"
            exit 1
        fi
        
        echo -e "${YELLOW}Attempting to fix by reinstalling dependencies...${NC}"
        cleanup_disk_space
        rm -rf node_modules package-lock.json
        if ! npm install; then
            echo -e "${RED}❌ Error: npm install failed during retry${NC}"
            echo -e "${YELLOW}📋 Please build locally and upload to S3 manually${NC}"
            # Cleanup before exit
            cd "$PROJECT_ROOT"
            rm -rf "$BUILD_DIR"
            exit 1
        fi
        if ! npm run build; then
            echo -e "${RED}❌ Error: npm run build failed after reinstall${NC}"
            echo -e "${YELLOW}📋 Please build locally and upload to S3 manually${NC}"
            # Cleanup before exit
            cd "$PROJECT_ROOT"
            rm -rf "$BUILD_DIR"
            exit 1
        fi
    fi
    
    # Check if build was successful
    if [ ! -d "build" ] || [ ! -f "build/index.html" ]; then
        echo -e "${RED}❌ Error: Build directory or index.html not found${NC}"
        # Cleanup before exit
        cd "$PROJECT_ROOT"
        rm -rf "$BUILD_DIR"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Build successful!${NC}"
    
    # Upload frontend build to S3
    echo -e "${BLUE}📤 Uploading to S3...${NC}"
    if ! aws s3 sync build/ s3://${LEAVE_MGMT_S3_BUCKET}/app/frontend/ --region $REGION; then
        echo -e "${RED}❌ Error: Failed to upload to S3${NC}"
        # Cleanup before exit
        cd "$PROJECT_ROOT"
        rm -rf "$BUILD_DIR"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Frontend uploaded to S3${NC}"
    
    # Cleanup build directory
    echo -e "${BLUE}🧹 Cleaning up build directory...${NC}"
    cd "$PROJECT_ROOT"
    rm -rf "$BUILD_DIR"
    echo -e "${GREEN}✅ Cleanup complete${NC}"
fi

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

# Download the frontend build from S3 to nginx html directory
echo "Downloading frontend from S3..."
# Retry logic - wait for S3 upload to complete
RETRY_COUNT=0
MAX_RETRIES=10
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    aws s3 sync s3://BUCKET_NAME/app/frontend/ /usr/share/nginx/html/ 2>&1
    if [ -f /usr/share/nginx/html/index.html ]; then
        echo "Frontend downloaded successfully"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for frontend in S3... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 5
done

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
    --output text)

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
echo "   ⏳ Wait 2-3 minutes for setup to complete"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Wait for instance initialization (2-3 minutes)"
echo "2. Check health: curl http://${PUBLIC_IP}/health.html"
echo "3. Access your website: http://${PUBLIC_IP}"
echo ""
echo -e "${YELLOW}⚠️  Note:${NC}"
echo "   The frontend will automatically download from S3."
echo "   If the site doesn't load, wait a few more minutes and refresh."
echo ""
echo "Deployment info saved to: deployment-info.txt"
echo ""

# Cleanup
rm -f user-data.sh

