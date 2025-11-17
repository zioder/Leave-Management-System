"""
Kafka consumer that bridges streaming leave events into AWS services.

Responsibilities:
- Forward each Kafka message to Kinesis Data Streams for downstream Lambda.
- Update DynamoDB tables to keep the operational state in sync.
- Enforce the business rule that at least 20 engineers must remain available.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from typing import Any, Dict

import boto3
from kafka import KafkaConsumer

from src.config import load as load_config

ENGINEER_TARGET = 20
TOTAL_ENGINEERS = 30


def parse_message(message: bytes) -> Dict[str, Any]:
    decoded = message.decode("utf-8")
    return json.loads(decoded)


def to_decimal(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively convert floats to Decimal for DynamoDB compatibility."""
    result = {}
    for key, value in payload.items():
        if isinstance(value, float):
            result[key] = Decimal(str(value))
        elif isinstance(value, dict):
            result[key] = to_decimal(value)
        else:
            result[key] = value
    return result


def update_request_tables(
    dynamodb,
    engineer_table_name: str,
    quota_table_name: str,
    request_table_name: str,
    record: Dict[str, Any],
) -> str:
    """Apply the business logic to DynamoDB and return the resulting status."""
    engineer_table = dynamodb.Table(engineer_table_name)
    quota_table = dynamodb.Table(quota_table_name)
    request_table = dynamodb.Table(request_table_name)

    request_id = record["request_id"]
    employee_id = record["employee_id"]
    days = int(record.get("days", 0))

    # Put/Update the request record
    request_table.put_item(
        Item=to_decimal(
            {
                "request_id": request_id,
                "employee_id": employee_id,
                "status": record.get("status", "PENDING"),
                "start_date": record.get("start_date"),
                "end_date": record.get("end_date"),
                "leave_type": record.get("leave_type"),
                "days": days,
                "event_type": record.get("event_type"),
            }
        )
    )

    if record["event_type"] != "request_approved":
        return "PENDING"

    # Check if employee is already on leave (to avoid double-counting)
    engineer_item = engineer_table.get_item(Key={"employee_id": employee_id}).get("Item")
    current_status = engineer_item.get("current_status", "AVAILABLE") if engineer_item else "AVAILABLE"
    if current_status == "ON_LEAVE":
        # Employee is already on leave, this might be a duplicate or update
        # For simplicity, we'll allow it, but in production you'd check date overlaps
        pass

    # Compute remaining availability BEFORE approving this request
    # Count all engineers currently on leave (excluding this employee if they're switching status)
    availability = engineer_table.scan(ProjectionExpression="employee_id,current_status").get("Items", [])
    unavailable = sum(
        1 for item in availability 
        if item.get("current_status") == "ON_LEAVE" and item.get("employee_id") != employee_id
    )
    # Add 1 if this employee will be going on leave
    if current_status != "ON_LEAVE":
        unavailable += 1
    
    available = TOTAL_ENGINEERS - unavailable
    if available < ENGINEER_TARGET:  # Changed <= to < to maintain at least 20 available
        # Not enough capacity, mark as denied
        request_table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "DENIED_CAPACITY"},
        )
        return "DENIED_CAPACITY"

    quota = quota_table.get_item(Key={"employee_id": employee_id}).get("Item")
    if not quota:
        raise RuntimeError(f"Quota not found for employee {employee_id}")
    remaining = int(quota.get("available_days", 0))
    if days > remaining:
        request_table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "DENIED_BALANCE"},
        )
        return "DENIED_BALANCE"

    # Approve: update records
    engineer_table.update_item(
        Key={"employee_id": employee_id},
        UpdateExpression="SET current_status = :status, on_leave_from = :from, on_leave_to = :to",
        ExpressionAttributeValues={
            ":status": "ON_LEAVE",
            ":from": record.get("start_date"),
            ":to": record.get("end_date"),
        },
    )
    quota_table.update_item(
        Key={"employee_id": employee_id},
        UpdateExpression="SET taken_ytd = if_not_exists(taken_ytd, :zero) + :days, "
        "available_days = available_days - :days",
        ExpressionAttributeValues={
            ":days": Decimal(str(days)),
            ":zero": Decimal("0"),
        },
    )
    request_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "APPROVED"},
    )
    return "APPROVED"


def forward_to_kinesis(kinesis_client, stream_name: str, record: Dict[str, Any]) -> None:
    kinesis_client.put_record(
        StreamName=stream_name,
        PartitionKey=record["employee_id"],
        Data=json.dumps(record).encode("utf-8"),
    )


def maybe_firehose(firehose_client, delivery_stream: str, record: Dict[str, Any]) -> None:
    if not delivery_stream:
        return
    firehose_client.put_record(
        DeliveryStreamName=delivery_stream,
        Record={"Data": json.dumps(record).encode("utf-8")},
    )


def main(group_id: str) -> None:
    cfg = load_config()
    consumer = KafkaConsumer(
        cfg.kafka_topic,
        bootstrap_servers=cfg.kafka_bootstrap.split(","),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id=group_id,
        value_deserializer=lambda value: value,
    )
    dynamodb = boto3.resource("dynamodb", region_name=cfg.region)
    kinesis = boto3.client("kinesis", region_name=cfg.region)
    firehose = boto3.client("firehose", region_name=cfg.region)

    for message in consumer:
        record = parse_message(message.value)
        print(f"received {record['event_type']} for {record['employee_id']}")  # noqa: T201
        status = update_request_tables(
            dynamodb,
            cfg.dynamodb_engineer_table,
            cfg.dynamodb_quota_table,
            cfg.dynamodb_request_table,
            record,
        )
        record["decision_status"] = status
        forward_to_kinesis(kinesis, cfg.kinesis_stream, record)
        maybe_firehose(firehose, cfg.firehose_stream, record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consume Kafka events and update AWS services.")
    parser.add_argument("--group-id", default="leave-agent-consumer")
    args = parser.parse_args()
    main(args.group_id)


