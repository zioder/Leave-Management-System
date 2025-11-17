"""
High-level orchestration that connects the LLM with DynamoDB/Athena queries.
This module is designed to be imported by an AWS Lambda handler.
"""
from __future__ import annotations

import json
from typing import Any, Dict

import boto3

from src.config import load as load_config

# Gemini client (replaces SageMaker / AgentRouter usage)
from .gemini_client import GeminiLLM


def query_balance(dynamodb, quota_table: str, employee_id: str) -> Dict[str, Any]:
    table = dynamodb.Table(quota_table)
    item = table.get_item(Key={"employee_id": employee_id}).get("Item")
    if not item:
        return {"status": "NOT_FOUND", "message": f"Employee {employee_id} not found"}
    return {
        "status": "OK",
        "available_days": float(item.get("available_days", 0)),
        "taken_ytd": float(item.get("taken_ytd", 0)),
    }


def request_leave(lambda_client, payload: Dict[str, Any], dynamodb=None, cfg=None) -> Dict[str, Any]:
    """
    Process leave request by either invoking a Lambda function or writing directly to DynamoDB.
    
    For AWS Academy or when ingest Lambda is not available, writes directly to DynamoDB.
    """
    # Try to invoke Lambda function first (if it exists)
    try:
        response = lambda_client.invoke(
            FunctionName="leave-management-ingest-handler",
            Payload=json.dumps(payload).encode("utf-8"),
            InvocationType="RequestResponse",
        )
        result = json.loads(response["Payload"].read())
        if response.get("StatusCode") == 200 and not result.get("errorMessage"):
            return result
    except Exception as e:
        # Lambda doesn't exist or failed, fall back to direct DynamoDB write
        if dynamodb and cfg:
            return request_leave_direct(dynamodb, cfg, payload)
        else:
            return {
                "status": "ERROR",
                "error": f"Could not process leave request: {str(e)}. Ingest Lambda may not be configured."
            }
    
    # Fallback: direct DynamoDB write
    if dynamodb and cfg:
        return request_leave_direct(dynamodb, cfg, payload)
    
    return {"status": "ERROR", "error": "Could not process leave request"}


def request_leave_direct(dynamodb, cfg, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process leave request directly in DynamoDB (simplified version for AWS Academy).
    This implements a simplified version of the business logic from kafka_consumer.py.
    """
    from decimal import Decimal
    import uuid
    
    engineer_table = dynamodb.Table(cfg.dynamodb_engineer_table)
    quota_table = dynamodb.Table(cfg.dynamodb_quota_table)
    request_table = dynamodb.Table(cfg.dynamodb_request_table)
    
    employee_id = payload.get("employee_id")
    if not employee_id:
        return {"status": "ERROR", "error": "Employee ID is required"}
    
    parameters = payload.get("parameters", {})
    start_date = parameters.get("start_date")
    end_date = parameters.get("end_date")
    leave_type = parameters.get("leave_type", "Vacation")
    
    # Calculate days
    if start_date and end_date:
        from datetime import datetime as dt
        start = dt.strptime(start_date, "%Y-%m-%d")
        end = dt.strptime(end_date, "%Y-%m-%d")
        days = (end - start).days + 1
    else:
        days = parameters.get("days", 1)
    
    # Generate request ID
    request_id = str(uuid.uuid4())
    
    # Check quota
    quota_item = quota_table.get_item(Key={"employee_id": employee_id}).get("Item")
    if not quota_item:
        return {"status": "ERROR", "error": f"Employee {employee_id} not found"}
    
    available_days = float(quota_item.get("available_days", 0))
    if days > available_days:
        # Create request with DENIED status
        request_table.put_item(
            Item={
                "request_id": request_id,
                "employee_id": employee_id,
                "status": "DENIED_BALANCE",
                "start_date": start_date,
                "end_date": end_date,
                "leave_type": leave_type,
                "days": Decimal(str(days)),
                "reason": f"Insufficient balance. Available: {available_days}, Requested: {days}",
            }
        )
        return {
            "status": "DENIED",
            "reason": f"Insufficient leave balance. You have {available_days} days available, but requested {days} days.",
            "request_id": request_id,
        }
    
    # Check availability (simplified - at least 20 engineers available)
    engineers = engineer_table.scan(ProjectionExpression="employee_id,current_status").get("Items", [])
    
    # Check if this employee is currently available
    engineer_item = engineer_table.get_item(Key={"employee_id": employee_id}).get("Item")
    current_status = engineer_item.get("current_status", "AVAILABLE") if engineer_item else "AVAILABLE"
    
    # Count unavailable engineers (excluding current employee if they're switching status)
    unavailable = sum(
        1 for e in engineers 
        if e.get("current_status") == "ON_LEAVE" and e.get("employee_id") != employee_id
    )
    
    # If current employee is going on leave, add them to unavailable count
    if current_status == "AVAILABLE":
        unavailable += 1
    
    total_engineers = len(engineers)
    available = total_engineers - unavailable
    
    if available < 20:
        # Not enough capacity
        request_table.put_item(
            Item={
                "request_id": request_id,
                "employee_id": employee_id,
                "status": "DENIED_CAPACITY",
                "start_date": start_date,
                "end_date": end_date,
                "leave_type": leave_type,
                "days": Decimal(str(days)),
                "reason": "Not enough engineers available. At least 20 must remain available.",
            }
        )
        return {
            "status": "DENIED",
            "reason": "Not enough engineers available. At least 20 must remain available.",
            "request_id": request_id,
        }
    
    # Approve request
    # Update engineer status
    engineer_table.update_item(
        Key={"employee_id": employee_id},
        UpdateExpression="SET current_status = :status, on_leave_from = :from, on_leave_to = :to",
        ExpressionAttributeValues={
            ":status": "ON_LEAVE",
            ":from": start_date,
            ":to": end_date,
        },
    )
    
    # Update quota
    quota_table.update_item(
        Key={"employee_id": employee_id},
        UpdateExpression="SET taken_ytd = if_not_exists(taken_ytd, :zero) + :days, available_days = available_days - :days",
        ExpressionAttributeValues={
            ":days": Decimal(str(days)),
            ":zero": Decimal("0"),
        },
    )
    
    # Create request record
    request_table.put_item(
        Item={
            "request_id": request_id,
            "employee_id": employee_id,
            "status": "APPROVED",
            "start_date": start_date,
            "end_date": end_date,
            "leave_type": leave_type,
            "days": Decimal(str(days)),
        }
    )
    
    return {
        "status": "APPROVED",
        "request_id": request_id,
        "message": f"Leave request approved for {days} days from {start_date} to {end_date}",
    }


def get_all_employees(dynamodb, engineer_table: str, quota_table: str) -> Dict[str, Any]:
    """Get all employees with their availability and quota info (admin only)."""
    engineer_tbl = dynamodb.Table(engineer_table)
    quota_tbl = dynamodb.Table(quota_table)
    
    engineers = engineer_tbl.scan().get("Items", [])
    result = []
    for eng in engineers:
        employee_id = eng.get("employee_id")
        quota = quota_tbl.get_item(Key={"employee_id": employee_id}).get("Item", {})
        result.append({
            "employee_id": employee_id,
            "status": eng.get("current_status", "AVAILABLE"),
            "on_leave_from": eng.get("on_leave_from"),
            "on_leave_to": eng.get("on_leave_to"),
            "available_days": float(quota.get("available_days", 0)),
            "taken_ytd": float(quota.get("taken_ytd", 0)),
            "annual_allowance": float(quota.get("annual_allowance", 0)),
        })
    return {"status": "OK", "employees": result}


def get_availability_stats(dynamodb, engineer_table: str) -> Dict[str, Any]:
    """Get availability statistics (admin only)."""
    table = dynamodb.Table(engineer_table)
    engineers = table.scan().get("Items", [])
    total = len(engineers)
    available = sum(1 for e in engineers if e.get("current_status") == "AVAILABLE")
    on_leave = total - available
    return {
        "status": "OK",
        "total_engineers": total,
        "available": available,
        "on_leave": on_leave,
        "availability_percentage": (available / total * 100) if total > 0 else 0,
    }


def handle_user_message(message: str, employee_id: str | None = None, is_admin: bool = False) -> Dict[str, Any]:
    """
    Handle user message with optional employee_id and admin mode.
    
    Args:
        message: User's natural language message
        employee_id: Selected employee ID (required for user mode, optional for admin)
        is_admin: Whether the user is an admin
    """
    cfg = load_config()

    # Always use Gemini as the LLM backend (configured via GOOGLE_API_KEY / GEMINI_API_KEY).
    # This replaces previous SageMaker / AgentRouter usage.
    llm = GeminiLLM()
    
    # Add employee_id to message if provided
    if employee_id:
        message = f"{message} employee_id: {employee_id}"
    if is_admin:
        message = f"{message} [ADMIN_MODE]"
    
    command = llm.command(message)

    dynamodb = boto3.resource("dynamodb", region_name=cfg.region)
    lambda_client = boto3.client("lambda", region_name=cfg.region)

    action = command.get("action")
    cmd_employee_id = command.get("employee_id") or employee_id
    
    # Admin-specific actions
    if is_admin and action == "get_all_employees":
        data = get_all_employees(dynamodb, cfg.dynamodb_engineer_table, cfg.dynamodb_quota_table)
    elif is_admin and action == "get_availability_stats":
        data = get_availability_stats(dynamodb, cfg.dynamodb_engineer_table)
    elif action == "query_balance":
        if not cmd_employee_id:
            return {"error": "Employee ID is required", "command": command}
        data = query_balance(dynamodb, cfg.dynamodb_quota_table, cmd_employee_id)
    elif action == "request_leave":
        if not cmd_employee_id:
            return {"error": "Employee ID is required", "command": command}
        data = request_leave(lambda_client, command, dynamodb=dynamodb, cfg=cfg)
    elif action == "list_requests":
        if not cmd_employee_id:
            return {"error": "Employee ID is required", "command": command}
        from boto3.dynamodb.conditions import Key
        table = dynamodb.Table(cfg.dynamodb_request_table)
        # Admin can query all requests, user only their own
        if is_admin and not cmd_employee_id:
            result = table.scan(Limit=50)
        else:
            result = table.query(
                IndexName="employee_id-index",
                KeyConditionExpression=Key("employee_id").eq(cmd_employee_id),
                Limit=20,
            )
        data = {"status": "OK", "requests": result.get("Items", [])}
    else:
        data = {"status": "UNSUPPORTED", "details": command}

    narrative = llm.narrative(command, data)
    return {"command": command, "data": data, "message": narrative}


