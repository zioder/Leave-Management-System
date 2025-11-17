"""
Admin-specific service functions for leave management system.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from src.storage.s3_storage import S3Storage


def get_employee_list(storage: S3Storage) -> List[Dict[str, Any]]:
    """Get list of all employees for dropdown selection."""
    engineers = storage.scan("EngineerAvailability")
    employees = []
    for item in engineers:
        employees.append({
            "id": item.get("employee_id"),
            "name": item.get("employee_id").replace("-", " ").title(),
            "status": item.get("current_status", "AVAILABLE"),
        })
    return sorted(employees, key=lambda x: x["name"])


def lambda_handler(event: Dict[str, Any], _context) -> Dict[str, Any]:
    """
    Lambda handler for admin endpoints (e.g., get employee list).
    """
    # Handle CORS
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": "",
        }
    
    bucket = os.environ.get("LEAVE_MGMT_S3_BUCKET", "")
    if not bucket:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "S3 bucket not configured"}),
        }
    
    storage = S3Storage(bucket)
    
    path = event.get("path", "")
    if path == "/employees" or event.get("action") == "get_employees":
        employees = get_employee_list(storage)
        return {
            "statusCode": 200,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"employees": employees}),
        }
    
    return {
        "statusCode": 404,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"error": "Not found"}),
    }
