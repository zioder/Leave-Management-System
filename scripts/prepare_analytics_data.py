"""
Prepare analytics data for QuickSight by exporting DynamoDB data to S3/Athena.

This script can be run periodically to sync DynamoDB data to S3 for analytics.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import boto3
import pandas as pd

from src.config import load as load_config


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def export_table_to_s3(dynamodb, table_name: str, s3_bucket: str, s3_prefix: str) -> None:
    """Export DynamoDB table to S3 as JSON."""
    table = dynamodb.Table(table_name)
    s3_client = boto3.client("s3")
    
    print(f"Exporting {table_name} to S3...")  # noqa: T201
    
    # Scan table
    items = []
    response = table.scan()
    items.extend(response.get("Items", []))
    
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    
    # Convert to JSON
    json_data = json.dumps(items, cls=DecimalEncoder, default=str)
    
    # Upload to S3
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    s3_key = f"{s3_prefix}/{table_name}/{timestamp}.json"
    
    s3_client.put_object(
        Bucket=s3_bucket,
        Key=s3_key,
        Body=json_data.encode("utf-8"),
        ContentType="application/json",
    )
    
    print(f"✓ Exported {len(items)} items to s3://{s3_bucket}/{s3_key}")  # noqa: T201


def create_athena_view(athena_client, database: str, view_name: str, query: str) -> None:
    """Create an Athena view for analytics."""
    try:
        athena_client.start_query_execution(
            QueryString=f"CREATE OR REPLACE VIEW {database}.{view_name} AS {query}",
            QueryExecutionContext={"Database": database},
            ResultConfiguration={
                "OutputLocation": f"s3://your-query-results-bucket/athena-results/"
            }
        )
        print(f"✓ Created Athena view: {view_name}")  # noqa: T201
    except Exception as e:
        print(f"Error creating view: {e}")  # noqa: T201
        raise


def main() -> None:
    """Main export function."""
    cfg = load_config()
    dynamodb = boto3.resource("dynamodb", region_name=cfg.region)
    s3_bucket = cfg.s3_bucket
    s3_prefix = "analytics/exports"
    
    print("Exporting DynamoDB tables to S3 for analytics...")  # noqa: T201
    print("=" * 60)  # noqa: T201
    
    # Export each table
    export_table_to_s3(
        dynamodb,
        cfg.dynamodb_engineer_table,
        s3_bucket,
        s3_prefix
    )
    
    export_table_to_s3(
        dynamodb,
        cfg.dynamodb_quota_table,
        s3_bucket,
        s3_prefix
    )
    
    export_table_to_s3(
        dynamodb,
        cfg.dynamodb_request_table,
        s3_bucket,
        s3_prefix
    )
    
    print("\n✓ Export complete!")  # noqa: T201
    print("Next steps:")  # noqa: T201
    print("1. Run Glue Crawler to update table schemas")  # noqa: T201
    print("2. Create QuickSight data source pointing to Athena")  # noqa: T201
    print("3. Build visualizations in QuickSight")  # noqa: T201


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        sys.exit(1)


