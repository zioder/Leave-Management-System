"""
Quick initiation script to check setup status and guide you through initialization.
"""
import os
import sys
from pathlib import Path

def check_env_file():
    """Check if .env file exists."""
    env_path = Path(".env")
    if env_path.exists():
        print("✅ .env file exists")
        return True
    else:
        print("❌ .env file not found")
        print("   Run: copy env.example .env")
        return False

def check_env_vars():
    """Check if required environment variables are set."""
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = {
        "GOOGLE_API_KEY": "Gemini API Key",
        "AWS_REGION": "AWS Region",
    }
    
    optional_vars = {
        "LEAVE_MGMT_S3_BUCKET": "S3 Bucket",
        "LEAVE_MGMT_KAFKA_BOOTSTRAP": "Kafka Bootstrap",
    }
    
    all_set = True
    
    print("\n📋 Required Environment Variables:")
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            print(f"   ✅ {var} ({desc}): {masked}")
        else:
            print(f"   ❌ {var} ({desc}): NOT SET")
            all_set = False
    
    print("\n📋 Optional Environment Variables:")
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var} ({desc}): {value}")
        else:
            print(f"   ⚠️  {var} ({desc}): Not set (optional)")
    
    return all_set

def check_aws_config():
    """Check if AWS CLI is configured."""
    try:
        import subprocess
        result = subprocess.run(
            ["aws", "configure", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("\n✅ AWS CLI is configured")
            return True
        else:
            print("\n❌ AWS CLI not configured properly")
            print("   Run: aws configure")
            return False
    except Exception as e:
        print(f"\n⚠️  Could not check AWS CLI: {e}")
        return False

def check_dynamodb_tables():
    """Check if DynamoDB tables exist."""
    try:
        import boto3
        from dotenv import load_dotenv
        load_dotenv()
        
        region = os.getenv("AWS_REGION", "us-east-1")
        dynamodb = boto3.client("dynamodb", region_name=region)
        
        tables = {
            os.getenv("LEAVE_MGMT_ENGINEER_TABLE", "EngineerAvailability"),
            os.getenv("LEAVE_MGMT_QUOTA_TABLE", "LeaveQuota"),
            os.getenv("LEAVE_MGMT_REQUEST_TABLE", "LeaveRequests"),
        }
        
        existing_tables = set(dynamodb.list_tables().get("TableNames", []))
        
        print("\n📊 DynamoDB Tables Status:")
        all_exist = True
        for table in tables:
            if table in existing_tables:
                print(f"   ✅ {table}: EXISTS")
            else:
                print(f"   ❌ {table}: NOT FOUND")
                all_exist = False
        
        if not all_exist:
            print("\n   💡 Run: python scripts/init_dynamodb_tables.py")
        
        return all_exist
    except Exception as e:
        print(f"\n⚠️  Could not check DynamoDB: {e}")
        print("   Make sure AWS credentials are configured")
        return False

def check_gemini():
    """Check if Gemini integration works."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from src.agent.gemini_client import GeminiLLM
        
        llm = GeminiLLM()
        response = llm.invoke("Say 'OK' if you can hear me.")
        
        if "OK" in response.upper() or len(response) > 0:
            print("\n✅ Gemini integration is working")
            return True
        else:
            print("\n❌ Gemini integration test failed")
            return False
    except Exception as e:
        print(f"\n❌ Gemini integration error: {e}")
        return False

def check_data_files():
    """Check if seed data files exist."""
    data_dir = Path("data")
    required_files = ["seed_engineers.csv", "seed_leave_events.csv"]
    
    print("\n📁 Data Files:")
    all_exist = True
    for file in required_files:
        file_path = data_dir / file
        if file_path.exists():
            print(f"   ✅ {file}: EXISTS")
        else:
            print(f"   ❌ {file}: NOT FOUND")
            all_exist = False
    
    if not all_exist:
        print("\n   💡 Run: python -m src.data_prep.prepare_seed_data --input \"employee leave tracking data.xlsx\"")
    
    return all_exist

def main():
    """Run all checks and provide next steps."""
    print("=" * 60)
    print("🚀 Leave Management System - Initiation Check")
    print("=" * 60)
    
    checks = {
        "Environment File": check_env_file(),
        "Environment Variables": check_env_vars(),
        "AWS Configuration": check_aws_config(),
        "DynamoDB Tables": check_dynamodb_tables(),
        "Gemini Integration": check_gemini(),
        "Data Files": check_data_files(),
    }
    
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    
    passed = sum(checks.values())
    total = len(checks)
    
    for name, status in checks.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {name}")
    
    print(f"\n✅ Passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All checks passed! You're ready to use the system.")
        print("\n💡 Next steps:")
        print("   1. Test the agent: python -c \"from src.agent.service import handle_user_message; print(handle_user_message('How many days do I have left?', employee_id='john-doe'))\"")
        print("   2. Start the frontend: cd frontend && npm install && npm start")
        print("   3. Deploy to AWS: See AWS_DEPLOYMENT_GUIDE.md")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("\n💡 Quick fixes:")
        if not checks["Environment File"]:
            print("   - Create .env: copy env.example .env")
        if not checks["Environment Variables"]:
            print("   - Edit .env and set GOOGLE_API_KEY and AWS_REGION")
        if not checks["AWS Configuration"]:
            print("   - Configure AWS: aws configure")
        if not checks["DynamoDB Tables"]:
            print("   - Create tables: python scripts/init_dynamodb_tables.py")
        if not checks["Data Files"]:
            print("   - Prepare data: python -m src.data_prep.prepare_seed_data --input \"employee leave tracking data.xlsx\"")
    
    print("\n📚 For detailed instructions, see: INITIATION_GUIDE.md")
    print("=" * 60)

if __name__ == "__main__":
    main()


