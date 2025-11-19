#!/bin/bash
# Quick setup script for AWS CloudShell
# This configures your environment and checks prerequisites

echo "========================================="
echo "AWS CloudShell Setup - Leave Management"
echo "========================================="
echo ""

# Check if we're in CloudShell
if [ ! -z "$AWS_EXECUTION_ENV" ] && [ "$AWS_EXECUTION_ENV" = "CloudShell" ]; then
    echo "✓ Running in AWS CloudShell"
else
    echo "⚠ Warning: Not detected as CloudShell, but continuing..."
fi

# Check AWS credentials
echo ""
echo "Checking AWS credentials..."
aws sts get-caller-identity > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ AWS credentials are valid"
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo "  Account: $ACCOUNT_ID"
    REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
    echo "  Region: $REGION"
else
    echo "✗ AWS credentials not found"
    exit 1
fi

# Check for .env file
echo ""
if [ -f .env ]; then
    echo "✓ .env file exists"
    
    # Check if GOOGLE_API_KEY is set
    source .env
    if [ -z "$GOOGLE_API_KEY" ]; then
        echo "✗ GOOGLE_API_KEY not set in .env"
        echo ""
        echo "Please edit .env and add your Gemini API key:"
        echo "  nano .env"
        exit 1
    else
        echo "✓ GOOGLE_API_KEY is set"
    fi
else
    echo "⚠ .env file not found"
    if [ -f env.example ]; then
        echo "Creating .env from env.example..."
        cp env.example .env
        echo ""
        echo "Please edit .env and add your Gemini API key:"
        echo "  nano .env"
        echo ""
        echo "Then run this script again."
        exit 1
    else
        echo "✗ env.example not found"
        exit 1
    fi
fi

# Check Python version
echo ""
PYTHON_VERSION=$(python3 --version 2>&1)
echo "Python: $PYTHON_VERSION"

# Check if pip is available
pip3 --version > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ pip3 is available"
else
    echo "✗ pip3 not found"
    exit 1
fi

# Check if Node.js is available (for frontend build)
echo ""
node --version > /dev/null 2>&1
if [ $? -eq 0 ]; then
    NODE_VERSION=$(node --version)
    echo "✓ Node.js: $NODE_VERSION"
else
    echo "⚠ Node.js not found - Installing..."
    # Install Node.js in CloudShell
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install --lts
    echo "✓ Node.js installed"
fi

# Check npm
npm --version > /dev/null 2>&1
if [ $? -eq 0 ]; then
    NPM_VERSION=$(npm --version)
    echo "✓ npm: $NPM_VERSION"
else
    echo "✗ npm not found"
    exit 1
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "You're ready to deploy. Run:"
echo "  chmod +x cloud_deploy.sh"
echo "  ./cloud_deploy.sh"
echo ""

