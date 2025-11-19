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

# Try relative imports first (for local dev), then absolute imports (for Lambda)
try:
    from ..storage.dynamodb_storage import DynamoDBStorage, create_storage
    from .gemini_client import GeminiLLM
except ImportError:
    # Absolute imports for Lambda deployment
    from storage.dynamodb_storage import DynamoDBStorage, create_storage
    from gemini_client import GeminiLLM


def resolve_employee_name(storage: Any, name_query: str) -> str | None:
    """
    Resolve a name query (e.g., 'Adam', 'adam solomon') to an employee_id.
    Returns the employee_id if found, None otherwise.
    """
    name_query = name_query.lower().strip()
    employees = storage.scan("EngineerAvailability")
    
    # Try exact match first (e.g., "adam-solomon")
    for emp in employees:
        emp_id = emp.get("employee_id", "").lower()
        if emp_id == name_query:
            return emp["employee_id"]
    
    # Try partial match (e.g., "adam" matches "adam-solomon")
    matches = []
    for emp in employees:
        emp_id = emp.get("employee_id", "")
        # Check if query matches first name or full name
        if name_query in emp_id.lower():
            matches.append(emp_id)
    
    # If exactly one match, return it
    if len(matches) == 1:
        return matches[0]
    
    # If multiple matches, try to find the best one
    # Prefer match at the start (first name match)
    for emp_id in matches:
        if emp_id.lower().startswith(name_query + "-"):
            return emp_id
    
    # Return first match if available
    return matches[0] if matches else None


def query_balance(storage: Any, employee_id: str) -> Dict[str, Any]:
    """Query leave balance for an employee."""
    item = storage.get_item("LeaveQuota", {"employee_id": employee_id})
    if not item:
        return {"status": "NOT_FOUND", "message": f"Employee {employee_id} not found"}
    return {
        "status": "OK",
        "available_days": float(item.get("available_days", 0)),
        "taken_ytd": float(item.get("taken_ytd", 0)),
    }


def request_leave_direct(storage: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
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


def get_all_employees(storage: Any, limit: int = 30) -> Dict[str, Any]:
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


def get_availability_stats(storage: Any) -> Dict[str, Any]:
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


def list_requests(storage: Any, employee_id: str = None, is_admin: bool = False) -> Dict[str, Any]:
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
    # Initialize Storage (DynamoDB)
    storage = create_storage()

    # Always use Gemini as the LLM backend
    llm = GeminiLLM()
    
    # For admin queries, add context of available employees
    enhanced_message = message
    if is_admin:
        # Get list of employees to help LLM resolve names
        employees = storage.scan("EngineerAvailability")[:30]  # Limit to avoid context overflow
        employee_list = ", ".join([emp.get("employee_id", "") for emp in employees])
        enhanced_message = f"{message}\n\nAvailable employees: {employee_list}"
        enhanced_message = f"{enhanced_message} [ADMIN_MODE]"
    elif employee_id:
        enhanced_message = f"{message} employee_id: {employee_id}"
    
    command = llm.command(enhanced_message)

    action = command.get("action")
    cmd_employee_id = command.get("employee_id") or employee_id
    
    # If admin query and employee_id in command looks like a name (e.g., "adam" instead of "adam-solomon"),
    # try to resolve it to an actual employee_id
    if is_admin and cmd_employee_id and "-" not in cmd_employee_id:
        resolved_id = resolve_employee_name(storage, cmd_employee_id)
        if resolved_id:
            cmd_employee_id = resolved_id
            # Update the command with resolved ID
            command["employee_id"] = resolved_id
    
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
    
    # Generate narrative with fallback
    try:
        # Pass is_admin flag to narrative for proper tone
        narrative = llm.narrative(command, narrative_data, is_admin=is_admin)
        
        # If narrative is the generic error message, create a simple fallback
        if "trouble generating a response" in narrative:
            narrative = generate_simple_narrative(action, data, is_admin=is_admin)
    except Exception:
        narrative = generate_simple_narrative(action, data, is_admin=is_admin)
    
    return {"command": command, "data": data, "message": narrative}


def generate_simple_narrative(action: str, data: Dict[str, Any], is_admin: bool = False) -> str:
    """Generate a simple text narrative when Gemini fails."""
    if action == "query_balance":
        avail = data.get("available_days", 0)
        taken = data.get("taken_ytd", 0)
        if is_admin:
            return f"Employee has {avail} leave days available. {taken} days taken year-to-date."
        return f"You have {avail} leave days available. You've taken {taken} days so far this year."
    
    elif action == "get_availability_stats":
        total = data.get("total_engineers", 0)
        available = data.get("available", 0)
        on_leave = data.get("on_leave", 0)
        pct = data.get("availability_percentage", 0)
        return f"Team Status: {available} out of {total} engineers are available ({pct:.1f}%). {on_leave} engineers are currently on leave."
    
    elif action == "request_leave":
        status = data.get("status", "UNKNOWN")
        if status == "APPROVED":
            return f"✅ Your leave request has been approved! {data.get('message', '')}"
        elif status == "DENIED":
            return f"❌ Your leave request was denied. {data.get('reason', '')}"
        else:
            return f"Leave request status: {status}"
    
    elif action == "get_all_employees":
        total = data.get("total", 0)
        showing = data.get("showing", 0)
        return f"Showing {showing} out of {total} total employees."
    
    elif action == "list_requests":
        requests = data.get("requests", [])
        return f"Found {len(requests)} leave requests."
    
    else:
        return "Request processed successfully."
