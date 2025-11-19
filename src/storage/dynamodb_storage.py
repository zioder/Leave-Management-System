"""
DynamoDB storage implementation for leave management system.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

class DynamoDBStorage:
    """DynamoDB storage adapter."""
    
    def __init__(self, region: str = "us-east-1"):
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.tables = {}
        
    def _get_table(self, table_name: str):
        """Get or create table resource cache."""
        if table_name not in self.tables:
            self.tables[table_name] = self.dynamodb.Table(table_name)
        return self.tables[table_name]
    
    def put_item(self, table: str, item: Dict[str, Any]) -> None:
        """Store an item in DynamoDB."""
        # DynamoDB handles Decimal conversion automatically if using boto3 resource
        # But we might need to handle float -> Decimal conversion if coming from JSON
        self._get_table(table).put_item(Item=self._float_to_decimal(item))
    
    def get_item(self, table: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Retrieve an item from DynamoDB."""
        try:
            response = self._get_table(table).get_item(Key=key)
            return self._decimal_to_float(response.get('Item'))
        except ClientError as e:
            print(f"Error getting item: {e}")
            return None
            
    def query(self, table: str, index_name: Optional[str] = None,
              key_condition: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Query items."""
        # This is a simplified query wrapper. 
        # In a real app, you'd construct KeyConditionExpression properly.
        # For now, assuming simple key matching or scan if no key provided (which is bad but matches S3 implementation behavior for compatibility)
        
        # If no key condition, we must scan (or query all partition key if known, but here generic)
        if not key_condition:
            return self.scan(table)

        # Construct KeyConditionExpression
        # This is tricky without knowing the schema structure generic wrapper
        # But for our specific tables:
        # EngineerAvailability: employee_id (PK)
        # LeaveQuota: employee_id (PK)
        # LeaveRequests: request_id (PK), employee_id (GSI)
        
        kwargs = {}
        if index_name:
            kwargs['IndexName'] = index_name
            
        # Simple equality conditions for now
        conditions = []
        for k, v in key_condition.items():
            conditions.append(Key(k).eq(v))
            
        if conditions:
            # Combine conditions (though usually only one for PK/GSI PK)
            condition = conditions[0]
            for c in conditions[1:]:
                condition = condition & c
            kwargs['KeyConditionExpression'] = condition
            
        response = self._get_table(table).query(**kwargs)
        return self._decimal_to_float(response.get('Items', []))
    
    def scan(self, table: str) -> List[Dict[str, Any]]:
        """Scan all items in a table."""
        response = self._get_table(table).scan()
        items = response.get('Items', [])
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = self._get_table(table).scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))
            
        return self._decimal_to_float(items)
    
    def update_item(self, table: str, key: Dict[str, str],
                   update_expression: str,
                   expression_values: Dict[str, Any],
                   expression_names: Optional[Dict[str, str]] = None) -> None:
        """Update an item."""
        kwargs = {
            'Key': key,
            'UpdateExpression': update_expression,
            'ExpressionAttributeValues': self._float_to_decimal(expression_values)
        }
        if expression_names:
            kwargs['ExpressionAttributeNames'] = expression_names
            
        self._get_table(table).update_item(**kwargs)
        
    def delete_item(self, table: str, key: Dict[str, str]) -> None:
        """Delete an item."""
        self._get_table(table).delete_item(Key=key)
        
    def batch_write_item(self, request_items: Dict[str, List[Dict[str, Any]]]) -> None:
        """Batch write items."""
        # Boto3 resource batch_writer context manager is easier, but we need to match input format
        # Input format: {'TableName': [{'PutRequest': {'Item': ...}}]}
        
        for table_name, items in request_items.items():
            with self._get_table(table_name).batch_writer() as batch:
                for item_dict in items:
                    if 'PutRequest' in item_dict:
                        batch.put_item(Item=self._float_to_decimal(item_dict['PutRequest']['Item']))
                    elif 'DeleteRequest' in item_dict:
                        batch.delete_item(Key=item_dict['DeleteRequest']['Key'])

    def _float_to_decimal(self, obj: Any) -> Any:
        """Recursively convert float to Decimal for DynamoDB."""
        if isinstance(obj, list):
            return [self._float_to_decimal(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: self._float_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, float):
            return Decimal(str(obj))
        return obj

    def _decimal_to_float(self, obj: Any) -> Any:
        """Recursively convert Decimal to float."""
        if isinstance(obj, list):
            return [self._decimal_to_float(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: self._decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, Decimal):
            return float(obj)
        return obj

def create_storage(region: str = "us-east-1") -> DynamoDBStorage:
    """Factory function to create storage instance."""
    return DynamoDBStorage(region=region)

