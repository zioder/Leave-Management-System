"""
Initialize DynamoDB tables required for the leave management system.

This script creates:
- EngineerAvailability table (employee_id as PK)
- LeaveQuota table (employee_id as PK)
- LeaveRequests table (request_id as PK, employee_id GSI)

Run this script once before starting the Kafka consumer.
"""
from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import boto3
from botocore.exceptions import ClientError

from src.config import load as load_config


def create_engineer_table(dynamodb, table_name: str, region: str) -> None:
    """Create the EngineerAvailability table."""
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "employee_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "employee_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Created table: {table_name}")  # noqa: T201
        table.wait_until_exists()
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Table {table_name} already exists")  # noqa: T201
        else:
            raise


def create_quota_table(dynamodb, table_name: str, region: str) -> None:
    """Create the LeaveQuota table."""
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "employee_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "employee_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Created table: {table_name}")  # noqa: T201
        table.wait_until_exists()
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Table {table_name} already exists")  # noqa: T201
        else:
            raise


def create_request_table(dynamodb, table_name: str, region: str) -> None:
    """Create the LeaveRequests table with GSI on employee_id."""
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "request_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "request_id", "AttributeType": "S"},
                {"AttributeName": "employee_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "employee_id-index",
                    "KeySchema": [
                        {"AttributeName": "employee_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Created table: {table_name}")  # noqa: T201
        table.wait_until_exists()
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Table {table_name} already exists")  # noqa: T201
        else:
            raise


def main() -> None:
    cfg = load_config()
    dynamodb = boto3.resource("dynamodb", region_name=cfg.region)

    print("Creating DynamoDB tables...")  # noqa: T201
    create_engineer_table(dynamodb, cfg.dynamodb_engineer_table, cfg.region)
    create_quota_table(dynamodb, cfg.dynamodb_quota_table, cfg.region)
    create_request_table(dynamodb, cfg.dynamodb_request_table, cfg.region)
    print("All tables created successfully!")  # noqa: T201


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        sys.exit(1)


