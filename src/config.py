"""
Configuration helpers for the leave management reference implementation.

Values are read from environment variables so that credentials are injected
by your IaC or CI/CD tooling rather than hard-coded. Local `.env` files can
be supported by loading them before importing this module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # python-dotenv is optional


def _get(name: str, default: str | None = None) -> str:
    """Return an environment variable or raise if it is required."""
    try:
        value = os.environ[name]
    except KeyError as exc:  # pragma: no cover - defensive guard
        if default is not None:
            return default
        raise RuntimeError(f"Missing required environment variable: {name}") from exc
    return value


@dataclass(frozen=True)
class AwsResources:
    region: str
    s3_bucket: str
    dynamodb_engineer_table: str
    dynamodb_quota_table: str
    dynamodb_request_table: str
    kinesis_stream: str
    firehose_stream: str
    kafka_bootstrap: str
    kafka_topic: str


def load() -> AwsResources:
    """Hydrate all AWS resource identifiers from environment variables."""
    return AwsResources(
        region=_get("AWS_REGION", "us-east-1"),
        s3_bucket=_get("LEAVE_MGMT_S3_BUCKET", ""),  # Optional
        dynamodb_engineer_table=_get("LEAVE_MGMT_ENGINEER_TABLE", "EngineerAvailability"),
        dynamodb_quota_table=_get("LEAVE_MGMT_QUOTA_TABLE", "LeaveQuota"),
        dynamodb_request_table=_get("LEAVE_MGMT_REQUEST_TABLE", "LeaveRequests"),
        kinesis_stream=_get("LEAVE_MGMT_KINESIS_STREAM", ""),  # Optional
        firehose_stream=_get("LEAVE_MGMT_FIREHOSE_STREAM", ""),  # Optional
        kafka_bootstrap=_get("LEAVE_MGMT_KAFKA_BOOTSTRAP", ""),  # Optional
        kafka_topic=_get("LEAVE_MGMT_KAFKA_TOPIC", "leave-events"),
    )


