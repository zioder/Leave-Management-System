"""
Quick test script to verify Gemini integration is working.
This can be run without AWS resources - only needs Google API key.
"""
import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agent.gemini_client import GeminiLLM


def test_gemini():
    """Test Gemini API connection and basic functionality."""
    print("=" * 60)
    print("Testing Gemini Integration")
    print("=" * 60)
    
    # Check if API key is set (support multiple environment variable names)
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] API key not found in .env file")
        print("   Please add your Gemini API key to .env file:")
        print("   GOOGLE_API_KEY=your-api-key-here")
        print("   Or use: GEMINI_API_KEY=your-api-key-here")
        print("   Get your key at: https://aistudio.google.com/")
        return False
    
    print(f"[OK] API Key found: {api_key[:10]}...")
    
    # Get model from env or use default
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    print(f"[OK] Using model: {model}")
    
    try:
        # Initialize client
        print("\nInitializing Gemini client...")
        llm = GeminiLLM(api_key=api_key, model=model)
        print("[OK] Client initialized successfully")
        print(f"[OK] Model: {llm.model}")
        
        # Test 1: Simple invoke
        print("\nTest 1: Testing basic API call...")
        response = llm.invoke("Say 'Hello, Gemini is working!' in one sentence.")
        print(f"[OK] API Response: {response}")
        
        # Test 2: Command parsing
        print("\nTest 2: Testing command parsing...")
        command = llm.command("How many days do I have left? employee_id: john-doe")
        print(f"[OK] Parsed command: {command}")
        
        # Verify command structure
        if not isinstance(command, dict):
            print("[WARNING] Command is not a dictionary")
        else:
            if "action" in command:
                print(f"   - Action: {command['action']}")
            if "employee_id" in command:
                print(f"   - Employee ID: {command['employee_id']}")
            if "parameters" in command:
                print(f"   - Parameters: {command['parameters']}")
        
        # Test 3: Command parsing with leave request
        print("\nTest 3: Testing leave request parsing...")
        command2 = llm.command("I want to request leave from 2024-12-20 to 2024-12-25. employee_id: jane-smith")
        print(f"[OK] Parsed command: {command2}")
        if isinstance(command2, dict) and command2.get("action") == "request_leave":
            print("   ✓ Correctly identified as leave request")
        
        # Test 4: Narrative generation
        print("\nTest 4: Testing narrative generation...")
        test_data = {
            "status": "OK",
            "available_days": 15.0,
            "taken_ytd": 5.0
        }
        narrative = llm.narrative(
            {"action": "query_balance", "employee_id": "john-doe"},
            test_data
        )
        print(f"[OK] Generated narrative: {narrative}")
        
        # Test 5: Test with system prompt
        print("\nTest 5: Testing with system prompt...")
        response_with_system = llm.invoke(
            "What is 2+2?",
            system_prompt="You are a helpful math tutor. Always explain your reasoning."
        )
        print(f"[OK] Response with system prompt: {response_with_system}")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All Gemini tests passed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("1. Verify your API key is correct")
        print("2. Check your internet connection")
        print("3. Visit https://aistudio.google.com/ to verify your account")
        print("4. Ensure GOOGLE_API_KEY or GEMINI_API_KEY is set in .env")
        print("5. Make sure you've installed: pip install google-genai")
        return False


if __name__ == "__main__":
    success = test_gemini()
    sys.exit(0 if success else 1)


