"""
Kafka consumer that bridges streaming leave events into AWS services.

Responsibilities:
- Forward each Kafka message to Kinesis Data Streams for downstream Lambda.
- Update S3 storage to keep the operational state in sync.
- Enforce the business rule that at least 20 engineers must remain available.

Note: This is for simulation/testing. AWS Academy doesn't have Kafka/Kinesis access.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict

import boto3
from kafka import KafkaConsumer

from src.storage.s3_storage import S3Storage

ENGINEER_TARGET = 20  # At least 20 must remain available
TOTAL_ENGINEERS = 30  # Total engineers in the system


def parse_message(message: bytes) -> Dict[str, Any]:
    decoded = message.decode("utf-8")
    return json.loads(decoded)


def update_request_tables(
    storage: S3Storage,
    record: Dict[str, Any],
) -> str:
    """Apply the business logic to S3 storage and return the resulting status."""
    request_id = record["request_id"]
    employee_id = record["employee_id"]
    days = int(record.get("days", 0))

    # Put/Update the request record
    storage.put_item("LeaveRequests", {
        "request_id": request_id,
        "employee_id": employee_id,
        "status": record.get("status", "PENDING"),
        "start_date": record.get("start_date"),
        "end_date": record.get("end_date"),
        "leave_type": record.get("leave_type"),
        "days": days,
        "event_type": record.get("event_type"),
    })

    if record["event_type"] != "request_approved":
        return "PENDING"

    # Check if employee is already on leave (to avoid double-counting)
    engineer_item = storage.get_item("EngineerAvailability", {"employee_id": employee_id})
    current_status = engineer_item.get("current_status", "AVAILABLE") if engineer_item else "AVAILABLE"

    # Compute remaining availability BEFORE approving this request
    # Count all engineers currently on leave (excluding this employee if they're switching status)
    availability = storage.scan("EngineerAvailability")
    unavailable = sum(
        1 for item in availability 
        if item.get("current_status") == "ON_LEAVE" and item.get("employee_id") != employee_id
    )
    # Add 1 if this employee will be going on leave
    if current_status != "ON_LEAVE":
        unavailable += 1
    
    available = TOTAL_ENGINEERS - unavailable
    if available < ENGINEER_TARGET:  # Maintain at least 20 available
        # Not enough capacity, mark as denied
        request_item = storage.get_item("LeaveRequests", {"request_id": request_id})
        if request_item:
            request_item["status"] = "DENIED_CAPACITY"
            storage.put_item("LeaveRequests", request_item)
        return "DENIED_CAPACITY"

    quota = storage.get_item("LeaveQuota", {"employee_id": employee_id})
    if not quota:
        raise RuntimeError(f"Quota not found for employee {employee_id}")
    remaining = int(quota.get("available_days", 0))
    if days > remaining:
        request_item = storage.get_item("LeaveRequests", {"request_id": request_id})
        if request_item:
            request_item["status"] = "DENIED_BALANCE"
            storage.put_item("LeaveRequests", request_item)
        return "DENIED_BALANCE"

    # Approve: update records
    if engineer_item:
        engineer_item.update({
            "current_status": "ON_LEAVE",
            "on_leave_from": record.get("start_date"),
            "on_leave_to": record.get("end_date"),
        })
        storage.put_item("EngineerAvailability", engineer_item)
    
    if quota:
        quota["taken_ytd"] = float(quota.get("taken_ytd", 0)) + days
        quota["available_days"] = float(quota.get("available_days", 0)) - days
        storage.put_item("LeaveQuota", quota)
    
    request_item = storage.get_item("LeaveRequests", {"request_id": request_id})
    if request_item:
        request_item["status"] = "APPROVED"
        storage.put_item("LeaveRequests", request_item)
    
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
    # Get configuration
    bucket = os.environ.get("LEAVE_MGMT_S3_BUCKET", "")
    region = os.environ.get("AWS_REGION", "us-east-1")
    kafka_bootstrap = os.environ.get("LEAVE_MGMT_KAFKA_BOOTSTRAP", "localhost:9092")
    kafka_topic = os.environ.get("LEAVE_MGMT_KAFKA_TOPIC", "leave-events")
    kinesis_stream = os.environ.get("LEAVE_MGMT_KINESIS_STREAM", "leave-events-stream")
    firehose_stream = os.environ.get("LEAVE_MGMT_FIREHOSE_STREAM", "")
    
    if not bucket:
        raise ValueError("LEAVE_MGMT_S3_BUCKET environment variable is required")
    
    storage = S3Storage(bucket, region)
    
    consumer = KafkaConsumer(
        kafka_topic,
        bootstrap_servers=kafka_bootstrap.split(","),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id=group_id,
        value_deserializer=lambda value: value,
    )
    kinesis = boto3.client("kinesis", region_name=region)
    firehose = boto3.client("firehose", region_name=region)

    for message in consumer:
        record = parse_message(message.value)
        print(f"received {record['event_type']} for {record['employee_id']}")  # noqa: T201
        status = update_request_tables(storage, record)
        record["decision_status"] = status
        forward_to_kinesis(kinesis, kinesis_stream, record)
        maybe_firehose(firehose, firehose_stream, record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consume Kafka events and update AWS services.")
    parser.add_argument("--group-id", default="leave-agent-consumer")
    args = parser.parse_args()
    main(args.group_id)
