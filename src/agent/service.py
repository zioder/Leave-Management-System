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


def cancel_leave_request(storage: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cancel an existing leave request.
    """
    employee_id = payload.get("employee_id")
    if not employee_id:
        return {"status": "ERROR", "error": "Employee ID is required"}
    
    parameters = payload.get("parameters", {})
    start_date = parameters.get("start_date")
    
    if not start_date:
         return {"status": "ERROR", "error": "Please specify the start date of the leave you want to cancel."}

    # Find the request
    # In a real DB we would query by employee_id and start_date, or use request_id directly.
    # Here we scan and filter (inefficient but functional for this demo).
    all_requests = storage.scan("LeaveRequests")
    target_request = None
    
    for req in all_requests:
        if (req.get("employee_id") == employee_id and 
            req.get("start_date") == start_date and 
            req.get("status") == "APPROVED"):
            target_request = req
            break
    
    if not target_request:
        return {"status": "NOT_FOUND", "error": f"No active approved leave found starting on {start_date}."}
    
    # Refund days
    days = float(target_request.get("days", 0))
    quota_item = storage.get_item("LeaveQuota", {"employee_id": employee_id})
    if quota_item:
        quota_item["taken_ytd"] = float(quota_item.get("taken_ytd", 0)) - days
        quota_item["available_days"] = float(quota_item.get("available_days", 0)) + days
        storage.put_item("LeaveQuota", quota_item)
    
    # Update Engineer Availability if they are currently ON_LEAVE for this request
    # (Simplified check: if they are ON_LEAVE and the dates match)
    engineer_item = storage.get_item("EngineerAvailability", {"employee_id": employee_id})
    if engineer_item and engineer_item.get("current_status") == "ON_LEAVE":
        # Only reset if the leave dates match (approximate check)
        if engineer_item.get("on_leave_from") == start_date:
            engineer_item.update({
                "current_status": "AVAILABLE",
                "on_leave_from": None,
                "on_leave_to": None,
            })
            storage.put_item("EngineerAvailability", engineer_item)
            
    # Update request status
    target_request["status"] = "CANCELLED"
    storage.put_item("LeaveRequests", target_request)
    
    return {
        "status": "CANCELLED", 
        "message": f"Leave request for {start_date} has been cancelled. {days} days have been refunded to your balance."
    }


def check_availability_for_date(storage: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check who is on leave for a specific date or range.
    """
    parameters = payload.get("parameters", {})
    start_date = parameters.get("start_date")
    end_date = parameters.get("end_date") or start_date
    
    if not start_date:
        return {"status": "ERROR", "error": "Please specify a date to check availability for."}
        
    # Convert strings to date objects for comparison
    try:
        check_start = dt.strptime(start_date, "%Y-%m-%d")
        check_end = dt.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return {"status": "ERROR", "error": "Invalid date format. Use YYYY-MM-DD."}

    all_requests = storage.scan("LeaveRequests")
    on_leave = []
    
    for req in all_requests:
        if req.get("status") != "APPROVED":
            continue
            
        req_start_str = req.get("start_date")
        req_end_str = req.get("end_date")
        
        if not req_start_str or not req_end_str:
            continue
            
        try:
            req_start = dt.strptime(req_start_str, "%Y-%m-%d")
            req_end = dt.strptime(req_end_str, "%Y-%m-%d")
            
            # Check for overlap
            # Overlap occurs if (StartA <= EndB) and (EndA >= StartB)
            if req_start <= check_end and req_end >= check_start:
                on_leave.append({
                    "employee_id": req.get("employee_id"),
                    "leave_type": req.get("leave_type"),
                    "start_date": req_start_str,
                    "end_date": req_end_str
                })
        except ValueError:
            continue
            
    total_engineers = 30  # Hardcoded for this demo, or query from DB
    available_count = total_engineers - len(on_leave)
    
    return {
        "status": "OK",
        "check_date": start_date,
        "check_end_date": end_date,
        "on_leave_count": len(on_leave),
        "available_count": available_count,
        "on_leave_employees": on_leave
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
    
    # Handle error action from LLM parsing failure
    if action == "error":
        error_msg = command.get("parameters", {}).get("error", "An error occurred")
        return {
            "command": command,
            "data": {"status": "ERROR", "error": error_msg},
            "message": error_msg
        }
    
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
    elif action == "cancel_leave":
        if not cmd_employee_id:
            return {"error": "Employee ID is required", "command": command, "data": {}}
        data = cancel_leave_request(storage, command)
    elif action == "check_availability_for_date":
        data = check_availability_for_date(storage, command)
    elif action == "list_requests":
        data = list_requests(storage, cmd_employee_id, is_admin)
    else:
        data = {"status": "UNSUPPORTED", "details": command}

    # Create a simplified version for narrative (avoid context overflow)
    narrative_data = data.copy()
    if action == "get_all_employees" and "employees" in narrative_data:
        # Prepare a summary for the narrative, highlighting those on leave
        all_emps = narrative_data.get("employees", [])
        on_leave_emps = [e.get("employee_id") for e in all_emps if e.get("status") == "ON_LEAVE"]
        
        narrative_data = {
            "status": narrative_data.get("status"),
            "total": narrative_data.get("total"),
            "on_leave_count": len(on_leave_emps),
            "on_leave_employees": on_leave_emps,
            "sample_available": [e.get("employee_id") for e in all_emps[:5] if e.get("status") == "AVAILABLE"]
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
    if action == "error":
        error_msg = data.get("error", "An error occurred processing your request.")
        return f"I'm sorry, I couldn't understand your request. {error_msg}\n\nPlease try:\n- Using clear date formats like '2025-11-20' or 'November 20, 2025'\n- Being specific about the action (e.g., 'request leave', 'check balance', 'who is on leave')\n- Breaking complex requests into smaller parts"
    
    elif action == "query_balance":
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
            
    elif action == "cancel_leave":
        if data.get("status") == "CANCELLED":
            return f"✅ {data.get('message')}"
        else:
            return f"❌ Could not cancel leave: {data.get('error', 'Unknown error')}"

    elif action == "check_availability_for_date":
        count = data.get("on_leave_count", 0)
        avail = data.get("available_count", 0)
        date = data.get("check_date")
        if count == 0:
            return f"Good news! The entire team ({avail} engineers) is available on {date}."
        else:
            emps = [e['employee_id'] for e in data.get('on_leave_employees', [])]
            return f"On {date}, {count} engineer(s) are on leave: {', '.join(emps)}. {avail} engineers are available."
    
    elif action == "get_all_employees":
        total = data.get("total", 0)
        showing = data.get("showing", 0)
        return f"Showing {showing} out of {total} total employees."
    
    elif action == "list_requests":
        requests = data.get("requests", [])
        if not requests:
            return "No leave requests found."
        
        details = []
        for r in requests[:3]:  # Show first 3
            details.append(f"{r.get('leave_type', 'Leave')} ({r.get('status', 'PENDING')}) from {r.get('start_date')} to {r.get('end_date')}")
        
        msg = f"Found {len(requests)} leave requests: " + "; ".join(details)
        if len(requests) > 3:
            msg += f", and {len(requests) - 3} more."
        return msg
    
    else:
        return "Request processed successfully."
