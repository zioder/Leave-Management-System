"""
Seed S3 storage with employee and leave data from CSV files.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from decimal import Decimal

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from dotenv import load_dotenv

from src.storage.s3_storage import create_storage

load_dotenv()


def seed_engineers(storage, csv_path: Path) -> int:
    """Seed engineer availability data."""
    print(f"📊 Loading engineers from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    count = 0
    for _, row in df.iterrows():
        item = {
            "employee_id": str(row["employee_id"]),
            "name": str(row["name"]),
            "email": str(row["email"]),
            "department": str(row.get("department", "Engineering")),
            "is_available": bool(row.get("is_available", True)),
            "current_status": str(row.get("current_status", "available")),
        }
        
        storage.put_item("EngineerAvailability", item)
        count += 1
    
    print(f"✅ Seeded {count} engineers")
    return count


def seed_leave_quotas(storage, csv_path: Path) -> int:
    """Seed leave quota data."""
    print(f"📊 Loading leave quotas from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    count = 0
    for _, row in df.iterrows():
        item = {
            "employee_id": str(row["employee_id"]),
            "annual_quota": int(row.get("annual_quota", 20)),
            "used_days": int(row.get("used_days", 0)),
            "available_days": int(row.get("available_days", 20)),
            "year": int(row.get("year", 2024)),
        }
        
        storage.put_item("LeaveQuota", item)
        count += 1
    
    print(f"✅ Seeded {count} leave quotas")
    return count


def seed_leave_events(storage, csv_path: Path, limit: int = 100) -> int:
    """Seed leave events data."""
    print(f"📊 Loading leave events from {csv_path} (limit: {limit})...")
    df = pd.read_csv(csv_path)
    
    # Limit the number of events for initial seed
    df = df.head(limit)
    
    count = 0
    for _, row in df.iterrows():
        # Generate a simple request_id
        request_id = f"req-{row['employee_id']}-{row.get('start_date', count)}"
        
        item = {
            "request_id": request_id.replace(" ", "-").replace(":", "-"),
            "employee_id": str(row["employee_id"]),
            "start_date": str(row.get("start_date", "")),
            "end_date": str(row.get("end_date", "")),
            "leave_type": str(row.get("leave_type", "annual")),
            "status": str(row.get("status", "pending")),
            "days_requested": int(row.get("days", 1)),
        }
        
        storage.put_item("LeaveRequests", item)
        count += 1
    
    print(f"✅ Seeded {count} leave requests")
    return count


def main() -> None:
    """Main function."""
    region = os.getenv("AWS_REGION", "us-east-1")
    bucket_name = os.getenv("LEAVE_MGMT_S3_BUCKET")
    
    if not bucket_name:
        print("❌ LEAVE_MGMT_S3_BUCKET not set in .env file")
        sys.exit(1)
    
    print("=" * 60)
    print("🌱 Seeding S3 Storage with Data")
    print("=" * 60)
    print(f"Region: {region}")
    print(f"Bucket: {bucket_name}")
    print()
    
    # Create storage client
    storage = create_storage(bucket_name, region)
    
    # Check if data files exist
    data_dir = Path("data")
    engineers_csv = data_dir / "seed_engineers.csv"
    events_csv = data_dir / "seed_leave_events.csv"
    
    if not engineers_csv.exists():
        print(f"❌ {engineers_csv} not found")
        print("   Run: python3 -m src.data_prep.prepare_seed_data")
        sys.exit(1)
    
    if not events_csv.exists():
        print(f"❌ {events_csv} not found")
        print("   Run: python3 -m src.data_prep.prepare_seed_data")
        sys.exit(1)
    
    # Seed data
    total = 0
    total += seed_engineers(storage, engineers_csv)
    total += seed_leave_quotas(storage, engineers_csv)
    total += seed_leave_events(storage, events_csv, limit=50)
    
    print("\n" + "=" * 60)
    print(f"✅ Successfully seeded {total} items to S3!")
    print("=" * 60)
    print("\n💡 Next steps:")
    print("   1. Test the agent: python3 test_gemini.py")
    print("   2. Run full check: python3 initiate.py")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

