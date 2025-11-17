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


def seed_engineers(storage, csv_path: Path, limit: int = 30) -> int:
    """Seed engineer availability data."""
    print(f"📊 Loading engineers from {csv_path} (limit: {limit})...")
    df = pd.read_csv(csv_path)
    
    # Limit to reduce context size
    df = df.head(limit)
    
    count = 0
    for _, row in df.iterrows():
        item = {
            "employee_id": str(row["employee_id"]),
            "department": str(row.get("department", "Engineering")),
            "position": str(row.get("position", "Engineer")),
            "status": str(row.get("status", "ACTIVE")),
            "is_available": True if row.get("status") == "ACTIVE" else False,
            "updated_at": str(row.get("updated_at", "")),
        }
        
        storage.put_item("EngineerAvailability", item)
        count += 1
    
    print(f"✅ Seeded {count} engineers")
    return count


def seed_leave_quotas(storage, csv_path: Path, limit: int = 30) -> int:
    """Seed leave quota data."""
    print(f"📊 Loading leave quotas from {csv_path} (limit: {limit})...")
    df = pd.read_csv(csv_path)
    
    # Limit to reduce context size
    df = df.head(limit)
    
    count = 0
    for _, row in df.iterrows():
        annual_allowance = int(row.get("annual_allowance", 20))
        carried_over = int(row.get("carried_over", 0))
        taken_to_date = int(row.get("taken_to_date", 0))
        remaining = int(row.get("remaining_leaves", 0))
        
        item = {
            "employee_id": str(row["employee_id"]),
            "annual_quota": annual_allowance,
            "carried_over": carried_over,
            "used_days": taken_to_date,
            "available_days": remaining,
            "year": 2024,
            "updated_at": str(row.get("updated_at", "")),
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
    processed_requests = set()
    
    for _, row in df.iterrows():
        request_id = str(row.get("request_id", f"req-{count}"))
        
        # Skip duplicate request IDs (multiple events per request)
        if request_id in processed_requests:
            continue
        
        processed_requests.add(request_id)
        
        item = {
            "request_id": request_id,
            "employee_id": str(row["employee_id"]),
            "leave_type": str(row.get("leave_type", "Annual Leave")),
            "start_date": str(row.get("start_date", "")),
            "end_date": str(row.get("end_date", "")),
            "days_requested": int(row.get("days", 1)),
            "event_type": str(row.get("event_type", "request_created")),
            "status": str(row.get("status", "PENDING")),
            "created_at": str(row.get("created_at", "")),
            "approved_at": str(row.get("approved_at", "")),
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
    
    # Seed data (limit to 30 engineers to reduce context size)
    total = 0
    total += seed_engineers(storage, engineers_csv, limit=30)
    total += seed_leave_quotas(storage, engineers_csv, limit=30)
    total += seed_leave_events(storage, events_csv, limit=25)
    
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

