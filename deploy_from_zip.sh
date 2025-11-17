#!/bin/bash

# Deploy frontend from uploaded zip to S3
# Run this in CloudShell after uploading frontend-build.zip

set -e

S3_BUCKET="leave-mgmt-1763398367"
ZIP_FILE="fm.zip"

echo "╔═══════════════════════════════════════════════════╗"
echo "║      Deploying Frontend Build to S3              ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# Check if zip file exists
if [ ! -f "$ZIP_FILE" ]; then
    echo "❌ Error: $ZIP_FILE not found!"
    echo ""
    echo "📋 Instructions:"
    echo "1. In CloudShell, click 'Actions' -> 'Upload file'"
    echo "2. Upload the frontend-build.zip file"
    echo "3. Run this script again: ./deploy_from_zip.sh"
    exit 1
fi

echo "✅ Found $ZIP_FILE"
echo ""

# Create temp directory
echo "📦 Extracting build files..."
mkdir -p /tmp/frontend-build
cd /tmp/frontend-build
unzip -q ~/"$ZIP_FILE"
echo "✅ Extracted"
echo ""

# Deploy to S3
echo "🚀 Uploading to S3 bucket: $S3_BUCKET..."
aws s3 sync . s3://$S3_BUCKET/ --delete --region us-east-1

if [ $? -eq 0 ]; then
    echo "✅ Upload successful!"
    echo ""
    
    # Cleanup
    cd ~
    rm -rf /tmp/frontend-build
    
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║          🎉 DEPLOYMENT COMPLETE! 🎉               ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo ""
    echo "🌐 Your app is live at:"
    echo "   http://$S3_BUCKET.s3-website-us-east-1.amazonaws.com/"
    echo ""
    echo "🔗 Lambda API:"
    echo "   https://bczn2rrklvrvubxnr45kc7atau0gvpjp.lambda-url.us-east-1.on.aws/"
    echo ""
    echo "🎯 Open your browser and test it!"
else
    echo "❌ Upload failed!"
    exit 1
fi

