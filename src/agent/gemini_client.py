"""
Gemini LLM client (Google AI Studio) for Leave Management System.

This client replaces SageMaker / AgentRouter usage and talks directly to
Gemini 2.5 Flash using the official `google-genai` SDK:

    from google import genai
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Explain how AI works in a few words",
    )
    print(response.text)
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from google import genai

# Try relative imports first (for local dev), then absolute imports (for Lambda)
try:
    from .prompt_builder import command_prompt, narrative_prompt
except ImportError:
    # Absolute imports for Lambda deployment
    from prompt_builder import command_prompt, narrative_prompt


class GeminiLLM:
    """
    High-level wrapper around Gemini chat completion for this project.

    Environment variables:
    - GOOGLE_API_KEY or GEMINI_API_KEY: API key from Google AI Studio
    - GEMINI_MODEL (optional): defaults to "gemini-2.5-flash"
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Gemini API key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY "
                "in your environment / .env (from Google AI Studio)."
            )

        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        # The Client will pick up GOOGLE_API_KEY automatically, but we pass it
        # explicitly so it also works with GEMINI_API_KEY.
        self._client = genai.Client(api_key=api_key)

    def invoke(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
        system_prompt: str | None = None,
    ) -> str:
        """
        Call Gemini with a simple text prompt and optional system message.

        Returns:
            Generated text response.
        """
        # The google-genai SDK expects contents to be a string.
        # If we have a system prompt, prepend it to the user prompt.
        contents: str
        if system_prompt:
            contents = f"{system_prompt}\n\n{prompt}"
        else:
            contents = prompt

        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )

        # Try to extract text from response
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        
        # Try to get text from candidates (even if MAX_TOKENS was hit)
        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    parts = getattr(candidate.content, "parts", [])
                    if parts and len(parts) > 0:
                        # Try different ways to get text
                        part_text = getattr(parts[0], "text", None)
                        if not part_text and hasattr(parts[0], "__dict__"):
                            # Try to get text from the part's dict
                            part_dict = parts[0].__dict__ if hasattr(parts[0], "__dict__") else {}
                            part_text = part_dict.get("text") or part_dict.get("_text")
                        
                        if part_text and isinstance(part_text, str):
                            return part_text.strip()
        except Exception as e:
            # Log the exception but don't crash
            import sys
            print(f"Warning: Failed to extract text from Gemini response: {e}", file=sys.stderr)
        
        # Check if response has any useful attributes we can extract
        try:
            if hasattr(response, "__dict__"):
                print(f"Warning: Gemini response has no text. Response type: {type(response)}", file=sys.stderr)
        except Exception:
            pass

        # Fallback: return a generic error message instead of dumping SDK response
        return "I apologize, but I'm having trouble generating a response right now. Please try again."

    # The following helpers mirror the old SageMaker / AgentRouter interface

    def command(self, user_message: str) -> Dict[str, Any]:
        """
        Parse user message into a command structure using the LLM.

        Always attempts to return a JSON object with:
        - action
        - employee_id
        - parameters
        """
        prompt = command_prompt(user_message)

        system_prompt = """You are a helpful assistant that parses user requests into structured JSON commands.
Always respond with valid JSON only, no additional text.
The JSON must contain: action, employee_id, and parameters."""

        try:
            raw = self.invoke(
                prompt,
                temperature=0.1,
                max_tokens=256,
                system_prompt=system_prompt,
            )

            # Robustly extract JSON from the response
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
            
            # Fallback: try to parse the whole string if no braces found (unlikely)
            return json.loads(raw.strip())
        except Exception as exc:
            # Fall back to a simple error command; the service layer will still
            # return something sensible to the user.
            return {
                "action": "error",
                "employee_id": None,
                "parameters": {
                    "error": f"Failed to parse command with Gemini: {exc}",
                },
            }

    def narrative(self, command: Dict[str, Any], data_payload: Dict[str, Any], is_admin: bool = False) -> str:
        """
        Generate a human-readable narrative for the user.
        """
        prompt = narrative_prompt(command, data_payload)

        if is_admin:
            system_prompt = """You are a professional assistant for a leave management system admin interface.
Generate clear, objective, and impersonal responses about employee leave data and team statistics.
Use third-person language (e.g., "The employee has..." not "You have...").
Keep responses brief, factual, and professional. Do not use personal greetings or names."""
        else:
            system_prompt = """You are a helpful assistant for a leave management system.
Generate clear, concise, and friendly responses to users about their leave requests and balances.
Keep responses professional but conversational. Be brief and to the point."""

        try:
            return self.invoke(
                prompt,
                temperature=0.4,
                max_tokens=800,  # Increased from 300 to avoid MAX_TOKENS
                system_prompt=system_prompt,
            )
        except Exception as exc:
            # Fallback: dump JSON so the user still sees something
            return json.dumps(
                {
                    "command": command,
                    "data": data_payload,
                    "error": f"Failed to generate narrative with Gemini: {exc}",
                },
                indent=2,
            )



