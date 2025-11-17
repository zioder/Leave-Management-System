"""
High-level orchestration that connects the LLM with S3 storage queries.
This module is designed to be imported by an AWS Lambda handler.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict
from datetime import datetime as dt
import uuid

from src.storage.s3_storage import S3Storage

# Gemini client (replaces SageMaker / AgentRouter usage)
from .gemini_client import GeminiLLM


def query_balance(storage: S3Storage, employee_id: str) -> Dict[str, Any]:
    """Query leave balance for an employee."""
    item = storage.get_item("LeaveQuota", {"employee_id": employee_id})
    if not item:
        return {"status": "NOT_FOUND", "message": f"Employee {employee_id} not found"}
    return {
        "status": "OK",
        "available_days": float(item.get("available_days", 0)),
        "taken_ytd": float(item.get("taken_ytd", 0)),
    }


def request_leave_direct(storage: S3Storage, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process leave request directly in S3 (simplified version for AWS Academy).
    """
    employee_id = payload.get("employee_id")
    if not employee_id:
        return {"status": "ERROR", "error": "Employee ID is required"}
    
    parameters = payload.get("parameters", {})
    start_date = parameters.get("start_date")
    end_date = parameters.get("end_date")
    leave_type = parameters.get("leave_type", "Vacation")
    
    # Calculate days
    if start_date and end_date:
        start = dt.strptime(start_date, "%Y-%m-%d")
        end = dt.strptime(end_date, "%Y-%m-%d")
        days = (end - start).days + 1
    else:
        days = parameters.get("days", 1)
    
    # Generate request ID
    request_id = str(uuid.uuid4())
    
    # Check quota
    quota_item = storage.get_item("LeaveQuota", {"employee_id": employee_id})
    if not quota_item:
        return {"status": "ERROR", "error": f"Employee {employee_id} not found"}
    
    available_days = float(quota_item.get("available_days", 0))
    if days > available_days:
        # Create request with DENIED status
        storage.put_item("LeaveRequests", {
            "request_id": request_id,
            "employee_id": employee_id,
            "status": "DENIED_BALANCE",
            "start_date": start_date,
            "end_date": end_date,
            "leave_type": leave_type,
            "days": days,
            "reason": f"Insufficient balance. Available: {available_days}, Requested: {days}",
        })
        return {
            "status": "DENIED",
            "reason": f"Insufficient leave balance. You have {available_days} days available, but requested {days} days.",
            "request_id": request_id,
        }
    
    # Check availability (simplified - at least 20 engineers available)
    engineers = storage.scan("EngineerAvailability")
    
    # Check if this employee is currently available
    engineer_item = storage.get_item("EngineerAvailability", {"employee_id": employee_id})
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
        storage.put_item("LeaveRequests", {
            "request_id": request_id,
            "employee_id": employee_id,
            "status": "DENIED_CAPACITY",
            "start_date": start_date,
            "end_date": end_date,
            "leave_type": leave_type,
            "days": days,
            "reason": "Not enough engineers available. At least 20 must remain available.",
        })
        return {
            "status": "DENIED",
            "reason": "Not enough engineers available. At least 20 must remain available.",
            "request_id": request_id,
        }
    
    # Approve request
    # Update engineer status
    if engineer_item:
        engineer_item.update({
            "current_status": "ON_LEAVE",
            "on_leave_from": start_date,
            "on_leave_to": end_date,
        })
        storage.put_item("EngineerAvailability", engineer_item)
    
    # Update quota
    if quota_item:
        quota_item["taken_ytd"] = float(quota_item.get("taken_ytd", 0)) + days
        quota_item["available_days"] = float(quota_item.get("available_days", 0)) - days
        storage.put_item("LeaveQuota", quota_item)
    
    # Create request record
    storage.put_item("LeaveRequests", {
        "request_id": request_id,
        "employee_id": employee_id,
        "status": "APPROVED",
        "start_date": start_date,
        "end_date": end_date,
        "leave_type": leave_type,
        "days": days,
    })
    
    return {
        "status": "APPROVED",
        "request_id": request_id,
        "message": f"Leave request approved for {days} days from {start_date} to {end_date}",
    }


def get_all_employees(storage: S3Storage, limit: int = 30) -> Dict[str, Any]:
    """Get all employees with their availability and quota info (admin only)."""
    engineers = storage.scan("EngineerAvailability")
    result = []
    for eng in engineers[:limit]:  # Limit to prevent context overflow
        employee_id = eng.get("employee_id")
        quota = storage.get_item("LeaveQuota", {"employee_id": employee_id}) or {}
        result.append({
            "employee_id": employee_id,
            "status": eng.get("current_status", "AVAILABLE"),
            "on_leave_from": eng.get("on_leave_from"),
            "on_leave_to": eng.get("on_leave_to"),
            "available_days": float(quota.get("available_days", 0)),
            "taken_ytd": float(quota.get("taken_ytd", 0)),
            "annual_allowance": float(quota.get("annual_allowance", 0)),
        })
    
    total_count = len(engineers)
    return {
        "status": "OK", 
        "employees": result,
        "total": total_count,
        "showing": len(result)
    }


def get_availability_stats(storage: S3Storage) -> Dict[str, Any]:
    """Get availability statistics (admin only)."""
    engineers = storage.scan("EngineerAvailability")
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


def list_requests(storage: S3Storage, employee_id: str = None, is_admin: bool = False) -> Dict[str, Any]:
    """List leave requests."""
    all_requests = storage.scan("LeaveRequests")
    
    # Filter by employee if not admin
    if not is_admin and employee_id:
        all_requests = [r for r in all_requests if r.get("employee_id") == employee_id]
    
    # Sort by most recent
    all_requests.sort(key=lambda x: x.get("start_date", ""), reverse=True)
    
    # Limit results
    limit = 50 if is_admin else 20
    return {"status": "OK", "requests": all_requests[:limit]}


def handle_user_message(message: str, employee_id: str | None = None, is_admin: bool = False) -> Dict[str, Any]:
    """
    Handle user message with optional employee_id and admin mode.
    
    Args:
        message: User's natural language message
        employee_id: Selected employee ID (required for user mode, optional for admin)
        is_admin: Whether the user is an admin
    """
    # Initialize S3 storage
    bucket = os.environ.get("LEAVE_MGMT_S3_BUCKET", "")
    if not bucket:
        return {"error": "S3 bucket not configured", "command": {}, "data": {}}
    
    storage = S3Storage(bucket)

    # Always use Gemini as the LLM backend
    llm = GeminiLLM()
    
    # Add employee_id to message if provided
    if employee_id:
        message = f"{message} employee_id: {employee_id}"
    if is_admin:
        message = f"{message} [ADMIN_MODE]"
    
    command = llm.command(message)

    action = command.get("action")
    cmd_employee_id = command.get("employee_id") or employee_id
    
    # Admin-specific actions
    if is_admin and action == "get_all_employees":
        data = get_all_employees(storage)
    elif is_admin and action == "get_availability_stats":
        data = get_availability_stats(storage)
    elif action == "query_balance":
        if not cmd_employee_id:
            return {"error": "Employee ID is required", "command": command, "data": {}}
        data = query_balance(storage, cmd_employee_id)
    elif action == "request_leave":
        if not cmd_employee_id:
            return {"error": "Employee ID is required", "command": command, "data": {}}
        data = request_leave_direct(storage, command)
    elif action == "list_requests":
        data = list_requests(storage, cmd_employee_id, is_admin)
    else:
        data = {"status": "UNSUPPORTED", "details": command}

    # Create a simplified version for narrative (avoid context overflow)
    narrative_data = data.copy()
    if action == "get_all_employees" and "employees" in narrative_data:
        # Only send summary stats for narrative, not full employee list
        narrative_data = {
            "status": narrative_data.get("status"),
            "total": narrative_data.get("total"),
            "showing": narrative_data.get("showing"),
            "sample_count": min(5, len(narrative_data.get("employees", [])))
        }
    
    narrative = llm.narrative(command, narrative_data)
    return {"command": command, "data": data, "message": narrative}
