"""
Helper script for creating DynamoDB tables when CLI access is restricted.
Provides console links and validates table creation.
"""
import boto3
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def get_region():
    """Get AWS region from environment or default."""
    return os.getenv("AWS_REGION", "us-east-1")

def get_console_url(region):
    """Get DynamoDB console URL for the region."""
    return f"https://{region}.console.aws.amazon.com/dynamodbv2/home?region={region}#tables"

def check_table_exists(table_name, region):
    """Check if a DynamoDB table exists."""
    try:
        dynamodb = boto3.client('dynamodb', region_name=region)
        response = dynamodb.describe_table(TableName=table_name)
        return True, response['Table']
    except dynamodb.exceptions.ResourceNotFoundException:
        return False, None
    except Exception as e:
        return False, str(e)

def print_table_config(name, pk, pk_type, gsi=None):
    """Print table configuration."""
    print(f"\n{'='*60}")
    print(f"📊 Table: {name}")
    print(f"{'='*60}")
    print(f"  Partition Key: {pk} ({pk_type})")
    if gsi:
        print(f"  Global Secondary Index:")
        print(f"    - Index Name: {gsi['name']}")
        print(f"    - Partition Key: {gsi['pk']} ({gsi['pk_type']})")
    print(f"  Table Settings: Default (On-demand or Provisioned)")
    print(f"{'='*60}")

def main():
    """Main function to guide table creation."""
    region = get_region()
    console_url = get_console_url(region)
    
    print("="*70)
    print("🚀 DynamoDB Table Creation Guide (AWS Console)")
    print("="*70)
    print(f"\n📍 Region: {region}")
    print(f"🔗 DynamoDB Console: {console_url}\n")
    
    # Define tables
    tables = {
        "EngineerAvailability": {
            "pk": "employee_id",
            "pk_type": "String",
            "gsi": None
        },
        "LeaveQuota": {
            "pk": "employee_id",
            "pk_type": "String",
            "gsi": None
        },
        "LeaveRequests": {
            "pk": "request_id",
            "pk_type": "String",
            "gsi": {
                "name": "employee_id-index",
                "pk": "employee_id",
                "pk_type": "String"
            }
        }
    }
    
    # Check existing tables
    print("🔍 Checking existing tables...\n")
    
    existing_tables = []
    missing_tables = []
    
    for table_name, config in tables.items():
        exists, info = check_table_exists(table_name, region)
        if exists:
            print(f"✅ {table_name}: ALREADY EXISTS")
            existing_tables.append(table_name)
        else:
            print(f"❌ {table_name}: NOT FOUND")
            missing_tables.append(table_name)
    
    if not missing_tables:
        print("\n" + "="*70)
        print("🎉 All tables already exist! You're good to go!")
        print("="*70)
        return
    
    # Show creation guide for missing tables
    print("\n" + "="*70)
    print("📝 TABLES TO CREATE")
    print("="*70)
    
    print(f"\n🔗 Open this URL: {console_url}\n")
    
    for table_name in missing_tables:
        config = tables[table_name]
        print_table_config(
            table_name,
            config["pk"],
            config["pk_type"],
            config.get("gsi")
        )
    
    print("\n" + "="*70)
    print("📋 STEP-BY-STEP INSTRUCTIONS")
    print("="*70)
    
    for i, table_name in enumerate(missing_tables, 1):
        config = tables[table_name]
        print(f"\n{i}. Create '{table_name}' table:")
        print(f"   a. Click 'Create table' button")
        print(f"   b. Table name: {table_name}")
        print(f"   c. Partition key: {config['pk']} (Type: {config['pk_type']})")
        print(f"   d. Leave Sort key empty")
        
        if config.get("gsi"):
            gsi = config["gsi"]
            print(f"   e. After table is created, add GSI:")
            print(f"      - Go to 'Indexes' tab")
            print(f"      - Click 'Create index'")
            print(f"      - Partition key: {gsi['pk']} (Type: {gsi['pk_type']})")
            print(f"      - Index name: {gsi['name']}")
        
        print(f"   {'e' if not config.get('gsi') else 'f'}. Click 'Create table'")
    
    print("\n" + "="*70)
    print("✅ After creating tables, run this script again to verify!")
    print("="*70)
    print(f"\nCommand: python3 {__file__}")
    
    # Wait for user confirmation
    print("\n" + "="*70)
    input("Press Enter after you've created the tables to verify...")
    
    # Recheck tables
    print("\n🔍 Verifying tables...\n")
    all_exist = True
    for table_name in missing_tables:
        exists, info = check_table_exists(table_name, region)
        if exists:
            print(f"✅ {table_name}: CREATED SUCCESSFULLY")
        else:
            print(f"❌ {table_name}: STILL NOT FOUND")
            all_exist = False
    
    if all_exist:
        print("\n" + "="*70)
        print("🎉 SUCCESS! All tables are now created!")
        print("="*70)
        print("\n💡 Next steps:")
        print("   1. Seed data: python3 scripts/seed_dynamodb.py")
        print("   2. Test setup: python3 scripts/test_setup.py")
        print("   3. Run initiation check: python3 initiate.py")
    else:
        print("\n⚠️  Some tables are still missing. Please create them and try again.")

if __name__ == "__main__":
    main()

