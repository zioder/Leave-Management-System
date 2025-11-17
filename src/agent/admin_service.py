"""
Admin-specific service functions for leave management system.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import boto3

from src.config import load as load_config


def get_employee_list(dynamodb, engineer_table: str) -> List[Dict[str, Any]]:
    """Get list of all employees for dropdown selection."""
    table = dynamodb.Table(engineer_table)
    result = table.scan(ProjectionExpression="employee_id,current_status")
    employees = []
    for item in result.get("Items", []):
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
    
    cfg = load_config()
    dynamodb = boto3.resource("dynamodb", region_name=cfg.region)
    
    path = event.get("path", "")
    if path == "/employees" or event.get("action") == "get_employees":
        employees = get_employee_list(dynamodb, cfg.dynamodb_engineer_table)
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


