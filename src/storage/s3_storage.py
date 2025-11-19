"""
S3-based storage implementation for leave management system.
Uses S3 as a key-value store with JSON objects.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class S3Storage:
    """S3-based storage adapter that mimics DynamoDB interface."""
    
    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name=region)
        self.s3_resource = boto3.resource('s3', region_name=region)
        self.bucket = self.s3_resource.Bucket(bucket_name)
        
    def _get_key(self, table: str, item_id: str) -> str:
        """Generate S3 key for an item."""
        return f"{table}/{item_id}.json"
    
    def _list_keys_prefix(self, prefix: str) -> List[str]:
        """List all keys with given prefix."""
        try:
            objects = self.bucket.objects.filter(Prefix=prefix)
            return [obj.key for obj in objects]
        except ClientError:
            return []
    
    def put_item(self, table: str, item: Dict[str, Any]) -> None:
        """Store an item in S3."""
        # Determine the key based on table type
        if table == "EngineerAvailability" or table == "LeaveQuota":
            item_id = item.get("employee_id")
        elif table == "LeaveRequests":
            item_id = item.get("request_id")
        else:
            raise ValueError(f"Unknown table: {table}")
        
        if not item_id:
            raise ValueError(f"Missing key field for table {table}")
        
        key = self._get_key(table, item_id)
        
        # Convert to JSON
        json_data = json.dumps(item, cls=DecimalEncoder, default=str)
        
        # Upload to S3
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json_data,
            ContentType='application/json'
        )
    
    def get_item(self, table: str, key: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Retrieve an item from S3."""
        # Extract the key value
        if "employee_id" in key:
            item_id = key["employee_id"]
        elif "request_id" in key:
            item_id = key["request_id"]
        else:
            raise ValueError(f"Invalid key: {key}")
        
        s3_key = self._get_key(table, item_id)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            data = json.loads(response['Body'].read().decode('utf-8'))
            return data
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            raise
    
    def query(self, table: str, index_name: Optional[str] = None,
              key_condition: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Query items (simulated by listing and filtering)."""
        prefix = f"{table}/"
        
        # List all objects with this prefix
        results = []
        try:
            for obj in self.bucket.objects.filter(Prefix=prefix):
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=obj.key
                )
                item = json.loads(response['Body'].read().decode('utf-8'))
                
                # Apply filter if provided
                if key_condition:
                    match = True
                    for key, value in key_condition.items():
                        if item.get(key) != value:
                            match = False
                            break
                    if match:
                        results.append(item)
                else:
                    results.append(item)
        except ClientError:
            pass
        
        return results
    
    def scan(self, table: str) -> List[Dict[str, Any]]:
        """Scan all items in a table."""
        return self.query(table)
    
    def update_item(self, table: str, key: Dict[str, str],
                   update_expression: str,
                   expression_values: Dict[str, Any],
                   expression_names: Optional[Dict[str, str]] = None) -> None:
        """Update an item (get, modify, put)."""
        # Get existing item
        item = self.get_item(table, key)
        if not item:
            # Create new item with key
            item = key.copy()
        
        # Parse simple update expressions (ADD, SET)
        # This is a simplified parser for common cases
        if "ADD" in update_expression:
            # Example: "ADD available :val"
            parts = update_expression.split("ADD")[1].strip().split()
            field = parts[0].strip()
            value_ref = parts[1].strip()
            
            # Apply expression names if provided
            if expression_names and field in expression_names:
                field = expression_names[field]
            
            # Get the value
            value = expression_values.get(value_ref, 0)
            
            # Add to existing value
            current = item.get(field, 0)
            item[field] = current + value
            
        elif "SET" in update_expression:
            # Example: "SET #status = :status, updated_at = :updated"
            set_part = update_expression.split("SET")[1].strip()
            assignments = [a.strip() for a in set_part.split(",")]
            
            for assignment in assignments:
                if "=" in assignment:
                    field, value_ref = [x.strip() for x in assignment.split("=", 1)]
                    
                    # Apply expression names
                    if expression_names and field in expression_names:
                        field = expression_names[field]
                    
                    # Get value
                    value = expression_values.get(value_ref)
                    if value is not None:
                        item[field] = value
        
        # Put updated item back
        self.put_item(table, item)
    
    def delete_item(self, table: str, key: Dict[str, str]) -> None:
        """Delete an item from S3."""
        if "employee_id" in key:
            item_id = key["employee_id"]
        elif "request_id" in key:
            item_id = key["request_id"]
        else:
            raise ValueError(f"Invalid key: {key}")
        
        s3_key = self._get_key(table, item_id)
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
        except ClientError:
            pass  # Object doesn't exist, that's fine
    
    def batch_write_item(self, request_items: Dict[str, List[Dict[str, Any]]]) -> None:
        """Batch write items (simplified)."""
        for table, items in request_items.items():
            for item_dict in items:
                if 'PutRequest' in item_dict:
                    self.put_item(table, item_dict['PutRequest']['Item'])


def create_storage(bucket_name: str, region: str = "us-east-1") -> S3Storage:
    """Factory function to create storage instance."""
    return S3Storage(bucket_name=bucket_name, region=region)


