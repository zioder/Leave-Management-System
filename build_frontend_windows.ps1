# Build Frontend on Windows (no AWS CLI needed)
# Run this in PowerShell on your Windows machine

Write-Host "🚀 Building Frontend" -ForegroundColor Cyan
Write-Host ""

# Set the Lambda URL
$LAMBDA_URL = "https://bczn2rrklvrvubxnr45kc7atau0gvpjp.lambda-url.us-east-1.on.aws/"

# Step 1: Update .env file
Write-Host "1️⃣ Updating frontend .env..." -ForegroundColor Yellow
Set-Content -Path "frontend\.env" -Value "REACT_APP_API_URL=$LAMBDA_URL"
Write-Host "✅ .env updated with Lambda URL" -ForegroundColor Green
Get-Content "frontend\.env"
Write-Host ""

# Step 2: Install dependencies
Write-Host "2️⃣ Installing dependencies (this may take a few minutes)..." -ForegroundColor Yellow
Set-Location frontend
npm install --legacy-peer-deps
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ npm install failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Dependencies installed" -ForegroundColor Green
Write-Host ""

# Step 3: Build the frontend
Write-Host "3️⃣ Building React app..." -ForegroundColor Yellow
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Build complete!" -ForegroundColor Green
Write-Host ""

# Step 4: Create zip file
Write-Host "4️⃣ Creating zip file..." -ForegroundColor Yellow
Set-Location build
Compress-Archive -Path * -DestinationPath "..\..\frontend-build.zip" -Force
Set-Location ..\..
Write-Host "✅ Created frontend-build.zip" -ForegroundColor Green
Write-Host ""

Write-Host "╔═══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          ✅ BUILD COMPLETE! ✅                    ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "📦 File created: frontend-build.zip" -ForegroundColor Green
Write-Host ""
Write-Host "🎯 NEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. Go to AWS CloudShell in your browser" -ForegroundColor White
Write-Host "2. Click Actions -> Upload file" -ForegroundColor White
Write-Host "3. Upload frontend-build.zip" -ForegroundColor White
Write-Host "4. Run the deploy script (see instructions)" -ForegroundColor White

