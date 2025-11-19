"""AWS Lambda entry point wrapping the agent service."""
from __future__ import annotations

import json
from typing import Any, Dict
import os

# Try relative imports first (for local dev), then absolute imports (for Lambda)
try:
    from .service import handle_user_message
    from ..storage.dynamodb_storage import create_storage
except ImportError:
    # Absolute imports for Lambda deployment
    from service import handle_user_message
    from storage.dynamodb_storage import create_storage


def get_headers():
    """Return headers for responses (with CORS since Function URL CORS is disabled)."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
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
            "headers": get_headers(),
            "body": json.dumps({"employees": employees_list})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": get_headers(),
            "body": json.dumps({"error": f"Failed to fetch employees: {str(e)}"})
        }


def chat_handler(payload: Dict[str, Any]):
    """Handle POST /chat endpoint."""
    message = payload.get("message")
    if not message:
        return {
            "statusCode": 400,
            "headers": get_headers(),
            "body": json.dumps({"error": "Missing 'message'"}),
        }
    
    employee_id = payload.get("employee_id")
    is_admin = payload.get("is_admin", False)
    
    try:
        result = handle_user_message(message, employee_id=employee_id, is_admin=is_admin)
        return {
            "statusCode": 200,
            "headers": get_headers(),
            "body": json.dumps(result),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": get_headers(),
            "body": json.dumps({"error": str(e)}),
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda function handler."""
    try:
        # Extract HTTP method
        http_method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "POST")
        raw_path = event.get("requestContext", {}).get("http", {}).get("path") or event.get("path", "")

        # Handle OPTIONS for CORS preflight
        if http_method == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": get_headers(),
                "body": "OK"
            }

        # Route: GET /employees
        if http_method == "GET" and ("employee" in raw_path.lower() or raw_path == "/"):
            return get_employees_handler()

        # Parse request body for POST
        body = event.get("body", "{}")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                pass # keep as is or empty dict

        # If body is empty but it's a POST, check if it's in the event root
        if not body and http_method == "POST":
             body = event

        message = body.get("message")
        
        # If we have a message, it's a chat request
        if message:
            return chat_handler(body)
            
        # Default to chat handler if it looks like a payload
        if "is_admin" in body or "employee_id" in body:
            return chat_handler(body)
            
        # Unknown route/method
        return {
            "statusCode": 404,
            "headers": get_headers(),
            "body": json.dumps({"error": "Route not found"})
        }

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "statusCode": 500,
            "headers": get_headers(),
            "body": json.dumps({
                "error": str(e),
                "message": "Internal server error"
            })
        }
