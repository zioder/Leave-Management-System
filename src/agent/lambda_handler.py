"""AWS Lambda entry point wrapping the agent service."""
from __future__ import annotations

import json
from typing import Any, Dict

import os
from .service import handle_user_message
from ..storage.dynamodb_storage import create_storage


def get_cors_headers():
    """Return CORS headers for all responses."""
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        "Content-Type": "application/json"
    }


def get_employees_handler():
    """Handle GET /employees endpoint."""
    try:
        storage = create_storage()
        employees = storage.scan("EngineerAvailability")
        
        # Limit to 30 engineers to reduce context size
        employees = employees[:30]
        
        # Format for frontend dropdown
        employees_list = []
        for emp in employees:
            emp_id = emp["employee_id"]
            # Convert "adam-solomon" to "Adam Solomon"
            name = emp_id.replace("-", " ").title()
            employees_list.append({
                "id": emp_id,
                "name": name,
                "department": emp.get("department", "Unknown"),
                "status": emp.get("current_status", "AVAILABLE")
            })
        
        # Sort by name
        employees_list.sort(key=lambda x: x["name"])
        
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({"employees": employees_list})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": f"Failed to fetch employees: {str(e)}"})
        }


def chat_handler(payload: Dict[str, Any]):
    """Handle POST /chat endpoint."""
    message = payload.get("message")
    if not message:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": "Missing 'message'"}),
        }
    
    employee_id = payload.get("employee_id")
    is_admin = payload.get("is_admin", False)
    
    try:
        result = handle_user_message(message, employee_id=employee_id, is_admin=is_admin)
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps(result),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }


def lambda_handler(event: Dict[str, Any], _context) -> Dict[str, Any]:
    """
    Lambda handler for chatbot API.
    Supports both API Gateway and Lambda Function URL formats.
    
    Routes:
    - GET /employees - List all employees
    - POST /chat - Send message to chatbot
    
    Expected payload for /chat:
    {
        "message": "User's message",
        "employee_id": "optional-employee-id",
        "is_admin": false
    }
    """
    # Extract HTTP method and path (works for both API Gateway and Function URLs)
    http_method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "POST")
    raw_path = event.get("requestContext", {}).get("http", {}).get("path") or event.get("path", "")
    
    # Handle CORS preflight
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": ""
        }
    
    # Route: GET /employees
    if http_method == "GET" and ("employee" in raw_path.lower() or raw_path == "/"):
        return get_employees_handler()
    
    # Route: POST /chat or POST / (default)
    if http_method == "POST":
        # Parse request body
        if "body" in event:
            try:
                payload = json.loads(event["body"])
            except json.JSONDecodeError:
                return {
                    "statusCode": 400,
                    "headers": get_cors_headers(),
                    "body": json.dumps({"error": "Invalid JSON body"}),
                }
        else:
            payload = event
        
        return chat_handler(payload)
    
    # Unknown route
    return {
        "statusCode": 404,
        "headers": get_cors_headers(),
        "body": json.dumps({"error": f"Route not found: {http_method} {raw_path}"})
    }


