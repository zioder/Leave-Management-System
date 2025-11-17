# PowerShell script to package and deploy Lambda function for Leave Management System
# Usage: .\scripts\deploy_lambda.ps1 [function-name] [region]

param(
    [string]$FunctionName = "leave-management-agent",
    [string]$Region = "us-east-1"
)

$PackageDir = "lambda-package"
$ZipFile = "lambda-agent.zip"

Write-Host "========================================="
Write-Host "Lambda Deployment Script"
Write-Host "========================================="
Write-Host "Function Name: $FunctionName"
Write-Host "Region: $Region"
Write-Host ""

# Clean up previous package
Write-Host "Cleaning up previous package..."
if (Test-Path $PackageDir) {
    Remove-Item -Recurse -Force $PackageDir
}
if (Test-Path $ZipFile) {
    Remove-Item -Force $ZipFile
}

# Create package directory
Write-Host "Creating package directory..."
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null

# Copy agent code
Write-Host "Copying agent code..."
Copy-Item -Path "src\agent\*" -Destination $PackageDir -Recurse -Force
Copy-Item -Path "src\config.py" -Destination $PackageDir -Force

# Install dependencies
Write-Host "Installing dependencies..."
pip install -r requirements.txt -t $PackageDir --quiet

# Create zip file
Write-Host "Creating zip file..."
Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipFile -Force

# Check if function exists
Write-Host "Checking if Lambda function exists..."
try {
    aws lambda get-function --function-name $FunctionName --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Function exists. Updating code..."
        aws lambda update-function-code `
            --function-name $FunctionName `
            --zip-file "fileb://$ZipFile" `
            --region $Region
        
        Write-Host "Waiting for update to complete..."
        aws lambda wait function-updated `
            --function-name $FunctionName `
            --region $Region
        
        Write-Host "Function updated successfully!"
    }
} catch {
    Write-Host "Function does not exist. Please create it first using AWS Console or CLI."
    Write-Host "Use the following command:"
    Write-Host ""
    Write-Host "aws lambda create-function \"
    Write-Host "  --function-name $FunctionName \"
    Write-Host "  --runtime python3.9 \"
    Write-Host "  --role arn:aws:iam::<account-id>:role/LeaveManagementLambdaRole \"
    Write-Host "  --handler agent.lambda_handler.lambda_handler \"
    Write-Host "  --zip-file fileb://$ZipFile \"
    Write-Host "  --timeout 60 \"
    Write-Host "  --memory-size 512 \"
    Write-Host "  --region $Region"
    Write-Host ""
    Write-Host "Package created: $ZipFile"
}

# Clean up
Write-Host "Cleaning up..."
Remove-Item -Recurse -Force $PackageDir

Write-Host ""
Write-Host "========================================="
Write-Host "Deployment complete!"
Write-Host "========================================="



