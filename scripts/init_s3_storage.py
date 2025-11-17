"""
Initialize S3 storage for the leave management system.
Creates the S3 bucket and folder structure.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


def create_bucket(bucket_name: str, region: str) -> bool:
    """Create S3 bucket if it doesn't exist."""
    s3_client = boto3.client('s3', region_name=region)
    
    try:
        # Check if bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Bucket '{bucket_name}' already exists")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            # Bucket doesn't exist, create it
            try:
                if region == 'us-east-1':
                    s3_client.create_bucket(Bucket=bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': region}
                    )
                print(f"✅ Created bucket: {bucket_name}")
                return True
            except ClientError as create_error:
                print(f"❌ Error creating bucket: {create_error}")
                return False
        else:
            print(f"❌ Error checking bucket: {e}")
            return False


def create_folder_structure(bucket_name: str, region: str) -> None:
    """Create folder structure in S3."""
    s3_client = boto3.client('s3', region_name=region)
    
    folders = [
        "EngineerAvailability/",
        "LeaveQuota/",
        "LeaveRequests/",
        "analytics/",
        "raw-data/"
    ]
    
    for folder in folders:
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=folder,
                Body=b''
            )
            print(f"✅ Created folder: {folder}")
        except ClientError as e:
            print(f"⚠️  Error creating folder {folder}: {e}")


def main() -> None:
    """Main function."""
    region = os.getenv("AWS_REGION", "us-east-1")
    bucket_name = os.getenv("LEAVE_MGMT_S3_BUCKET")
    
    if not bucket_name:
        print("❌ LEAVE_MGMT_S3_BUCKET not set in .env file")
        print("   Set it to your S3 bucket name")
        sys.exit(1)
    
    print("=" * 60)
    print("🚀 Initializing S3 Storage")
    print("=" * 60)
    print(f"Region: {region}")
    print(f"Bucket: {bucket_name}")
    print()
    
    # Create bucket
    if not create_bucket(bucket_name, region):
        print("\n❌ Failed to create/verify bucket")
        sys.exit(1)
    
    # Create folder structure
    print("\n📁 Creating folder structure...")
    create_folder_structure(bucket_name, region)
    
    print("\n" + "=" * 60)
    print("✅ S3 storage initialized successfully!")
    print("=" * 60)
    print("\n💡 Next steps:")
    print("   1. Seed data: python3 scripts/seed_s3.py")
    print("   2. Test setup: python3 initiate.py")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

