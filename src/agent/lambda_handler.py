"""AWS Lambda entry point wrapping the agent service."""
from __future__ import annotations

import json
from typing import Any, Dict

from .service import handle_user_message


def lambda_handler(event: Dict[str, Any], _context) -> Dict[str, Any]:
    """
    Lambda handler for chatbot API.
    
    Expected payload:
    {
        "message": "User's message",
        "employee_id": "optional-employee-id",
        "is_admin": false
    }
    """
    # Handle CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": "",
        }
    
    if "body" in event:
        try:
            payload = json.loads(event["body"])
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Invalid JSON body"}),
            }
    else:
        payload = event
    
    message = payload.get("message")
    if not message:
        return {
            "statusCode": 400,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Missing 'message'"}),
        }
    
    employee_id = payload.get("employee_id")
    is_admin = payload.get("is_admin", False)
    
    try:
        result = handle_user_message(message, employee_id=employee_id, is_admin=is_admin)
        return {
            "statusCode": 200,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps(result),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }


