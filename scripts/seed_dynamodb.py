"""
Seed DynamoDB tables with initial employee data from the generated CSV files.

This script reads the seed_engineers.csv file and populates:
- EngineerAvailability table with current status
- LeaveQuota table with leave balances

Run this after init_dynamodb_tables.py and prepare_seed_data.py
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
from decimal import Decimal
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import boto3
import pandas as pd

from src.config import load as load_config


def seed_engineer_availability(dynamodb, table_name: str, df: pd.DataFrame) -> None:
    """Populate EngineerAvailability table."""
    table = dynamodb.Table(table_name)
    count = 0
    for _, row in df.iterrows():
        table.put_item(
            Item={
                "employee_id": str(row["employee_id"]),
                "current_status": "AVAILABLE",
                "on_leave_from": None,
                "on_leave_to": None,
                "updated_at": row.get("updated_at", ""),
            }
        )
        count += 1
    print(f"Seeded {count} employees into {table_name}")  # noqa: T201


def seed_leave_quota(dynamodb, table_name: str, df: pd.DataFrame) -> None:
    """Populate LeaveQuota table."""
    table = dynamodb.Table(table_name)
    count = 0
    for _, row in df.iterrows():
        table.put_item(
            Item={
                "employee_id": str(row["employee_id"]),
                "annual_allowance": Decimal(str(row["annual_allowance"])),
                "carried_over": Decimal(str(row.get("carried_over", 0))),
                "taken_ytd": Decimal(str(row.get("taken_to_date", 0))),
                "available_days": Decimal(str(row.get("remaining_leaves", 0))),
                "updated_at": row.get("updated_at", ""),
            }
        )
        count += 1
    print(f"Seeded {count} quotas into {table_name}")  # noqa: T201


def main(csv_path: pathlib.Path) -> None:
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    cfg = load_config()
    dynamodb = boto3.resource("dynamodb", region_name=cfg.region)

    print(f"Reading employee data from {csv_path}...")  # noqa: T201
    df = pd.read_csv(csv_path)

    print("Seeding DynamoDB tables...")  # noqa: T201
    seed_engineer_availability(dynamodb, cfg.dynamodb_engineer_table, df)
    seed_leave_quota(dynamodb, cfg.dynamodb_quota_table, df)
    print("Seeding complete!")  # noqa: T201


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed DynamoDB with employee data.")
    parser.add_argument(
        "--csv",
        type=pathlib.Path,
        default=pathlib.Path("data/seed_engineers.csv"),
        help="Path to seed_engineers.csv file",
    )
    args = parser.parse_args()
    try:
        main(args.csv)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        sys.exit(1)


