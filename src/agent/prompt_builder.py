"""
Prompt templates for the lightweight SageMaker-hosted LLM. The model is used
bidirectionally:

1. User natural language -> structured JSON command for backend Lambdas.
2. Structured data -> conversational explanation.
"""
from __future__ import annotations

from textwrap import dedent
from typing import Dict


def command_prompt(user_message: str) -> str:
    """Return a prompt instructing the model to emit JSON only."""
    is_admin = "[ADMIN_MODE]" in user_message.upper()
    
    if is_admin:
        actions = '"query_balance" | "request_leave" | "list_requests" | "get_all_employees" | "get_availability_stats"'
        admin_note = "\n        - Admin mode: You can query all employees, view availability stats, and manage any employee's leave."
    else:
        actions = '"query_balance" | "request_leave" | "list_requests"'
        admin_note = ""
    
    template = dedent(
        f"""
        You are a leave-management assistant. Translate the user request into a JSON command.
        Schema:
        {{{{
          "action": {actions},
          "employee_id": "string (required for user actions, optional for admin)",
          "parameters": {{{{
             "start_date": "YYYY-MM-DD (optional, for leave requests)",
             "end_date": "YYYY-MM-DD (optional, for leave requests)",
             "leave_type": "string (optional, e.g., 'Sick Leave', 'Vacation')",
             "days": "integer (optional, calculated from dates if not provided)"
          }}}}
        }}}}

        Available actions:
        - query_balance: Get employee's remaining leave days
        - request_leave: Request leave for an employee
        - list_requests: List leave requests for an employee
        - get_all_employees: Get all employees with their status (admin only)
        - get_availability_stats: Get availability statistics (admin only)

        Constraints:
        - There are 30 engineers total; at least 20 must remain available.
        - Reject impossible requests by setting "action": "error" with explanation.
        - Dates must be ISO 8601 format (YYYY-MM-DD).
        - Omit optional parameters when not provided.{admin_note}
        - Extract employee_id from the message if present, otherwise use the one from context.

        Output ONLY minified JSON, nothing else.

        User: {{message}}
        """
    )
    return template.format(message=user_message.strip())


def narrative_prompt(command: Dict, data_payload: Dict) -> str:
    """Build the instruction for turning raw data into a user-facing explanation."""
    template = dedent(
        """
        You are summarizing the result of a leave-management operation.
        User command:
        {command}

        Data:
        {data}

        Compose a short friendly paragraph describing the outcome for the engineer.
        Mention remaining balance or denial reasons. Keep it under 100 words.
        """
    )
    return template.format(command=command, data=data_payload)


