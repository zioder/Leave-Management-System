"""
Setup script for Amazon QuickSight analytics dashboard.

This script helps prepare data sources and create QuickSight datasets
for the leave management system analytics.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import boto3
from botocore.exceptions import ClientError

from src.config import load as load_config


def create_athena_data_source(quicksight_client, account_id: str, region: str) -> Dict[str, Any]:
    """Create an Athena data source in QuickSight."""
    data_source_id = "leave-mgmt-athena-ds"
    data_source_name = "Leave Management Athena"
    
    try:
        response = quicksight_client.create_data_source(
            AwsAccountId=account_id,
            DataSourceId=data_source_id,
            Name=data_source_name,
            Type="ATHENA",
            DataSourceParameters={
                "AthenaParameters": {
                    "WorkGroup": "primary"  # Use default workgroup or specify your workgroup
                }
            },
            Credentials={
                "CredentialPair": {
                    "Username": "quicksight-user",  # Replace with your credentials
                    "Password": "your-password"  # In production, use Secrets Manager
                }
            },
            Permissions=[
                {
                    "Principal": f"arn:aws:quicksight:{region}:{account_id}:user/default/*",
                    "Actions": [
                        "quicksight:DescribeDataSource",
                        "quicksight:DescribeDataSourcePermissions",
                        "quicksight:PassDataSource",
                    ]
                }
            ]
        )
        print(f"✓ Created Athena data source: {data_source_id}")  # noqa: T201
        return response
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceExistsException":
            print(f"Data source {data_source_id} already exists")  # noqa: T201
        else:
            print(f"Error creating data source: {e}")  # noqa: T201
            raise


def create_dynamodb_data_source(quicksight_client, account_id: str, region: str, table_name: str) -> Dict[str, Any]:
    """Create a DynamoDB data source in QuickSight."""
    data_source_id = f"leave-mgmt-dynamodb-{table_name.lower()}"
    data_source_name = f"Leave Management DynamoDB - {table_name}"
    
    try:
        response = quicksight_client.create_data_source(
            AwsAccountId=account_id,
            DataSourceId=data_source_id,
            Name=data_source_name,
            Type="DYNAMODB",
            DataSourceParameters={
                "DynamoDbParameters": {
                    "TableName": table_name,
                    "S3Bucket": "quicksight-dynamodb-export-bucket"  # S3 bucket for DynamoDB exports
                }
            },
            Permissions=[
                {
                    "Principal": f"arn:aws:quicksight:{region}:{account_id}:user/default/*",
                    "Actions": [
                        "quicksight:DescribeDataSource",
                        "quicksight:DescribeDataSourcePermissions",
                        "quicksight:PassDataSource",
                    ]
                }
            ]
        )
        print(f"✓ Created DynamoDB data source: {data_source_id}")  # noqa: T201
        return response
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceExistsException":
            print(f"Data source {data_source_id} already exists")  # noqa: T201
        else:
            print(f"Error creating data source: {e}")  # noqa: T201
            raise


def create_dataset(quicksight_client, account_id: str, data_source_arn: str, dataset_name: str) -> Dict[str, Any]:
    """Create a QuickSight dataset from a data source."""
    dataset_id = dataset_name.lower().replace(" ", "-")
    
    # Define logical table structure
    logical_table = {
        "Alias": dataset_name,
        "Source": {
            "DataSourceArn": data_source_arn,
            "PhysicalTableId": "leave-mgmt-table",
        },
        "DataTransforms": []
    }
    
    try:
        response = quicksight_client.create_data_set(
            AwsAccountId=account_id,
            DataSetId=dataset_id,
            Name=dataset_name,
            ImportMode="DIRECT_QUERY",  # or "SPICE" for imported data
            PhysicalTableMap={
                "leave-mgmt-table": {
                    "RelationalTable": {
                        "DataSourceArn": data_source_arn,
                        "Name": "leave_management",
                        "InputColumns": [
                            {
                                "Name": "employee_id",
                                "Type": "STRING"
                            },
                            {
                                "Name": "current_status",
                                "Type": "STRING"
                            },
                            {
                                "Name": "available_days",
                                "Type": "DECIMAL"
                            },
                            {
                                "Name": "taken_ytd",
                                "Type": "DECIMAL"
                            }
                        ]
                    }
                }
            },
            LogicalTableMap={
                "leave-mgmt-logical-table": logical_table
            },
            Permissions=[
                {
                    "Principal": f"arn:aws:quicksight:{account_id}:user/default/*",
                    "Actions": [
                        "quicksight:DescribeDataSet",
                        "quicksight:DescribeDataSetPermissions",
                        "quicksight:PassDataSet",
                        "quicksight:DescribeIngestion",
                        "quicksight:ListIngestions",
                    ]
                }
            ]
        )
        print(f"✓ Created dataset: {dataset_name}")  # noqa: T201
        return response
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceExistsException":
            print(f"Dataset {dataset_id} already exists")  # noqa: T201
        else:
            print(f"Error creating dataset: {e}")  # noqa: T201
            raise


def get_account_id() -> str:
    """Get AWS account ID."""
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def main() -> None:
    """Main setup function."""
    print("Setting up QuickSight for Leave Management System...")  # noqa: T201
    print("=" * 60)  # noqa: T201
    
    cfg = load_config()
    account_id = get_account_id()
    quicksight_client = boto3.client("quicksight", region_name=cfg.region)
    
    print(f"AWS Account ID: {account_id}")  # noqa: T201
    print(f"Region: {cfg.region}")  # noqa: T201
    print()  # noqa: T201
    
    # Note: QuickSight setup typically requires manual configuration in the console
    # This script provides a starting point, but you may need to:
    # 1. Create data sources manually in QuickSight Console
    # 2. Connect to Athena or DynamoDB
    # 3. Create datasets
    # 4. Build visualizations
    # 5. Create dashboards
    # 6. Set up embedding for web application
    
    print("QuickSight Setup Instructions:")  # noqa: T201
    print("1. Go to AWS QuickSight Console")  # noqa: T201
    print("2. Create a new data source:")  # noqa: T201
    print("   - For real-time data: Connect to DynamoDB")  # noqa: T201
    print("   - For analytics: Connect to Athena (which queries S3)")  # noqa: T201
    print("3. Create datasets from your data sources")  # noqa: T201
    print("4. Create visualizations:")  # noqa: T201
    print("   - Employee availability chart")  # noqa: T201
    print("   - Leave requests over time")  # noqa: T201
    print("   - Department-wise leave distribution")  # noqa: T201
    print("   - Leave balance statistics")  # noqa: T201
    print("5. Create a dashboard with your visualizations")  # noqa: T201
    print("6. Enable dashboard embedding")  # noqa: T201
    print("7. Update frontend/src/components/QuickSightDashboard.js with dashboard URL")  # noqa: T201
    print()  # noqa: T201
    
    print("For detailed instructions, see QUICKSIGHT_SETUP.md")  # noqa: T201


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        sys.exit(1)


