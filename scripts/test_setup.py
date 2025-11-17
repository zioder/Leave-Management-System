"""
Test script to verify the setup is working correctly.

This script checks:
1. Environment variables are set
2. DynamoDB tables exist
3. Kafka connection works
4. Gemini integration works
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import boto3
from kafka import KafkaProducer

from src.config import load as load_config


def test_config() -> bool:
    """Test that all required environment variables are set."""
    print("Testing configuration...")  # noqa: T201
    try:
        cfg = load_config()
        print(f"✓ Configuration loaded successfully")  # noqa: T201
        print(f"  Region: {cfg.region}")  # noqa: T201
        print(f"  DynamoDB Tables: {cfg.dynamodb_engineer_table}, {cfg.dynamodb_quota_table}, {cfg.dynamodb_request_table}")  # noqa: T201
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")  # noqa: T201
        return False


def test_dynamodb(cfg) -> bool:
    """Test DynamoDB table access."""
    print("\nTesting DynamoDB tables...")  # noqa: T201
    try:
        dynamodb = boto3.resource("dynamodb", region_name=cfg.region)
        tables = [
            cfg.dynamodb_engineer_table,
            cfg.dynamodb_quota_table,
            cfg.dynamodb_request_table,
        ]
        for table_name in tables:
            table = dynamodb.Table(table_name)
            table.load()
            print(f"✓ Table {table_name} exists")  # noqa: T201
        return True
    except Exception as e:
        print(f"✗ DynamoDB error: {e}")  # noqa: T201
        print("  Run scripts/init_dynamodb_tables.py to create tables")  # noqa: T201
        return False


def test_kafka(cfg) -> bool:
    """Test Kafka connection."""
    print("\nTesting Kafka connection...")  # noqa: T201
    try:
        producer = KafkaProducer(
            bootstrap_servers=cfg.kafka_bootstrap.split(","),
            value_serializer=lambda v: v.encode("utf-8"),
        )
        producer.close()
        print(f"✓ Kafka connection successful ({cfg.kafka_bootstrap})")  # noqa: T201
        return True
    except Exception as e:
        print(f"✗ Kafka connection error: {e}")  # noqa: T201
        print("  Ensure Kafka is running and bootstrap servers are correct")  # noqa: T201
        return False


def test_gemini() -> bool:
    """Test Gemini integration."""
    print("\nTesting Gemini integration...")  # noqa: T201
    try:
        from src.agent.gemini_client import GeminiLLM
        llm = GeminiLLM()
        response = llm.invoke("Say 'OK' if you can hear me.")
        if "OK" in response.upper() or len(response) > 0:
            print(f"✓ Gemini integration is working")  # noqa: T201
            return True
        else:
            print(f"⚠ Gemini integration test failed")  # noqa: T201
            return False
    except Exception as e:
        print(f"✗ Gemini error: {e}")  # noqa: T201
        print("  Ensure GOOGLE_API_KEY or GEMINI_API_KEY is set in your environment")  # noqa: T201
        return False


def main() -> None:
    """Run all tests."""
    print("=" * 50)  # noqa: T201
    print("Leave Management System - Setup Test")  # noqa: T201
    print("=" * 50)  # noqa: T201

    if not test_config():
        sys.exit(1)

    cfg = load_config()

    results = []
    results.append(("DynamoDB", test_dynamodb(cfg)))
    results.append(("Kafka", test_kafka(cfg)))
    results.append(("Gemini", test_gemini()))

    print("\n" + "=" * 50)  # noqa: T201
    print("Test Summary:")  # noqa: T201
    print("=" * 50)  # noqa: T201
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name}: {status}")  # noqa: T201

    if all(result for _, result in results):
        print("\n✓ All tests passed! System is ready to use.")  # noqa: T201
        sys.exit(0)
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()


