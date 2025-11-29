""
Data validation and schema enforcement.
"""
from typing import Dict, List, Optional, Any, Union, Callable, Type, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel, ValidationError, validator, Field
from typing_extensions import Literal
import json
import re

from ...monitoring.metrics import metrics
from ...monitoring.alerts import Alert, AlertSeverity, AlertType, AlertManager

logger = logging.getLogger(__name__)

class DataType(str, Enum):
    """Supported data types for validation."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    PRICE = "price"
    QUANTITY = "quantity"
    PERCENTAGE = "percentage"
    DURATION = "duration"

class ConstraintType(str, Enum):
    """Types of constraints that can be applied to fields."""
    REQUIRED = "required"
    MIN = "min"
    MAX = "max"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    PATTERN = "pattern"
    ENUM = "enum"
    CUSTOM = "custom"

@dataclass
class FieldConstraint:
    """A constraint that can be applied to a field."""
    type: ConstraintType
    value: Any
    message: str = ""
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        """Validate a value against this constraint."""
        try:
            if self.type == ConstraintType.REQUIRED:
                if value is None or (isinstance(value, (str, list, dict)) and not value):
                    return False, self.message or "Field is required"
            
            elif self.type == ConstraintType.MIN and value is not None:
                if isinstance(value, (int, float)) and value < self.value:
                    return False, self.message or f"Value must be at least {self.value}"
                
            elif self.type == ConstraintType.MAX and value is not None:
                if isinstance(value, (int, float)) and value > self.value:
                    return False, self.message or f"Value must be at most {self.value}"
            
            elif self.type == ConstraintType.MIN_LENGTH and value is not None:
                if hasattr(value, '__len__') and len(value) < self.value:
                    return False, self.message or f"Length must be at least {self.value}"
            
            elif self.type == ConstraintType.MAX_LENGTH and value is not None:
                if hasattr(value, '__len__') and len(value) > self.value:
                    return False, self.message or f"Length must be at most {self.value}"
            
            elif self.type == ConstraintType.PATTERN and value is not None:
                if not re.match(self.value, str(value)):
                    return False, self.message or f"Value does not match pattern {self.value}"
            
            elif self.type == ConstraintType.ENUM and value is not None:
                if value not in self.value:
                    return False, self.message or f"Value must be one of {self.value}"
            
            elif self.type == ConstraintType.CUSTOM and value is not None:
                if not self.value(value):
                    return False, self.message or "Custom validation failed"
            
            return True, ""
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

@dataclass
class FieldDefinition:
    """Definition of a field in a data schema."""
    name: str
    data_type: DataType
    description: str = ""
    default: Any = None
    constraints: List[FieldConstraint] = field(default_factory=list)
    is_nullable: bool = False
    
    def validate(self, value: Any) -> Tuple[bool, str]:
        """Validate a value against this field definition."""
        # Handle null values
        if value is None or (isinstance(value, (str, list, dict)) and not value):
            if not self.is_nullable:
                required = any(c.type == ConstraintType.REQUIRED for c in self.constraints)
                if required or not self.is_nullable:
                    return False, "Field is required"
            return True, ""
        
        # Type conversion and validation
        try:
            if self.data_type == DataType.INTEGER:
                value = int(value)
            elif self.data_type == DataType.FLOAT:
                value = float(value)
            elif self.data_type == DataType.BOOLEAN:
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 't', 'y', 'yes')
                else:
                    value = bool(value)
            elif self.data_type == DataType.DATETIME:
                if isinstance(value, (int, float)):
                    # Assume timestamp in milliseconds
                    value = datetime.fromtimestamp(value / 1000.0)
                elif isinstance(value, str):
                    # Try to parse ISO format
                    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif self.data_type == DataType.TIMESTAMP:
                if isinstance(value, (str, datetime)):
                    # Convert to timestamp in milliseconds
                    if isinstance(value, str):
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    else:
                        dt = value
                    value = int(dt.timestamp() * 1000)
                else:
                    # Ensure it's an integer
                    value = int(value)
            elif self.data_type == DataType.PRICE:
                value = float(value)
                if value <= 0:
                    return False, "Price must be positive"
            elif self.data_type == DataType.QUANTITY:
                value = float(value)
                if value < 0:
                    return False, "Quantity cannot be negative"
            elif self.data_type == DataType.PERCENTAGE:
                value = float(value)
                if not (0 <= value <= 100):
                    return False, "Percentage must be between 0 and 100"
            elif self.data_type == DataType.DURATION:
                value = int(value)
                if value < 0:
                    return False, "Duration cannot be negative"
        except (ValueError, TypeError) as e:
            return False, f"Invalid {self.data_type.value} value: {value}"
        
        # Apply constraints
        for constraint in self.constraints:
            is_valid, message = constraint.validate(value)
            if not is_valid:
                return False, message
        
        return True, ""

class DataSchema:
    """Schema for validating data structures."""
    
    def __init__(self, name: str, fields: List[FieldDefinition]):
        """Initialize the schema with field definitions."""
        self.name = name
        self.fields = {f.name: f for f in fields}
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Validate a data dictionary against the schema.
        
        Args:
            data: Dictionary of data to validate
            
        Returns:
            Dictionary mapping field names to lists of error messages
        """
        errors = {}
        
        # Check for missing required fields
        for field_name, field_def in self.fields.items():
            if field_name not in data and any(c.type == ConstraintType.REQUIRED for c in field_def.constraints):
                if field_name not in errors:
                    errors[field_name] = []
                errors[field_name].append("Field is required")
        
        # Validate provided fields
        for field_name, value in data.items():
            if field_name in self.fields:
                field_def = self.fields[field_name]
                is_valid, message = field_def.validate(value)
                if not is_valid:
                    if field_name not in errors:
                        errors[field_name] = []
                    errors[field_name].append(message)
            else:
                # Unknown field
                if "__unknown__" not in errors:
                    errors["__unknown__"] = []
                errors["__unknown__"].append(f"Unknown field: {field_name}")
        
        return errors
    
    def validate_dataframe(self, df: pd.DataFrame) -> Dict[str, List[Tuple[int, str]]]:
        """
        Validate a pandas DataFrame against the schema.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            Dictionary mapping field names to lists of (row_index, error) tuples
        """
        errors = {}
        
        # Check for missing required columns
        required_columns = [
            name for name, field in self.fields.items()
            if any(c.type == ConstraintType.REQUIRED for c in field.constraints)
        ]
        
        missing_columns = set(required_columns) - set(df.columns)
        for col in missing_columns:
            errors[col] = [(-1, "Column is missing")]
        
        # Validate each row
        for idx, row in df.iterrows():
            row_errors = self.validate(row.to_dict())
            for field, field_errors in row_errors.items():
                if field == "__unknown__":
                    # Skip unknown fields at the row level
                    continue
                for error in field_errors:
                    if field not in errors:
                        errors[field] = []
                    errors[field].append((idx, error))
        
        return errors
    
    def to_json_schema(self) -> Dict[str, Any]:
        """Convert the schema to a JSON Schema dictionary."""
        properties = {}
        required = []
        
        for field_name, field_def in self.fields.items():
            # Map data types to JSON Schema types
            type_mapping = {
                DataType.STRING: "string",
                DataType.INTEGER: "integer",
                DataType.FLOAT: "number",
                DataType.BOOLEAN: "boolean",
                DataType.DATETIME: "string",
                DataType.TIMESTAMP: "integer",
                DataType.PRICE: "number",
                DataType.QUANTITY: "number",
                DataType.PERCENTAGE: "number",
                DataType.DURATION: "integer"
            }
            
            field_schema = {
                "type": type_mapping.get(field_def.data_type, "string"),
                "description": field_def.description or "",
                "default": field_def.default
            }
            
            # Add format for certain types
            if field_def.data_type == DataType.DATETIME:
                field_schema["format"] = "date-time"
            elif field_def.data_type == DataType.PRICE:
                field_schema["minimum"] = 0
                field_schema["exclusiveMinimum"] = True
            elif field_def.data_type == DataType.QUANTITY:
                field_schema["minimum"] = 0
            elif field_def.data_type == DataType.PERCENTAGE:
                field_schema["minimum"] = 0
                field_schema["maximum"] = 100
            
            # Add constraints
            for constraint in field_def.constraints:
                if constraint.type == ConstraintType.MIN:
                    field_schema["minimum"] = constraint.value
                elif constraint.type == ConstraintType.MAX:
                    field_schema["maximum"] = constraint.value
                elif constraint.type == ConstraintType.MIN_LENGTH:
                    field_schema["minLength"] = constraint.value
                elif constraint.type == ConstraintType.MAX_LENGTH:
                    field_schema["maxLength"] = constraint.value
                elif constraint.type == ConstraintType.PATTERN:
                    field_schema["pattern"] = constraint.value
                elif constraint.type == ConstraintType.ENUM:
                    field_schema["enum"] = constraint.value
            
            # Handle nullability
            if field_def.is_nullable:
                if isinstance(field_schema["type"], str):
                    field_schema["type"] = [field_schema["type"], "null"]
                elif isinstance(field_schema["type"], list):
                    field_schema["type"].append("null")
            
            properties[field_name] = field_schema
            
            # Check if field is required
            if any(c.type == ConstraintType.REQUIRED for c in field_def.constraints):
                required.append(field_name)
        
        schema = {
            "$schema": "http://json-schema.org/draft/2020-12/schema#",
            "title": self.name,
            "type": "object",
            "properties": properties
        }
        
        if required:
            schema["required"] = required
        
        return schema

class DataValidator:
    """Validate data against schemas and business rules."""
    
    def __init__(self, alert_manager: Optional[AlertManager] = None):
        """Initialize the validator with an optional alert manager."""
        self.schemas: Dict[str, DataSchema] = {}
        self.alert_manager = alert_manager
        self._setup_default_schemas()
    
    def _setup_default_schemas(self) -> None:
        """Set up default schemas for common data types."""
        # Trade schema
        trade_schema = DataSchema("trade", [
            FieldDefinition(
                name="trade_id",
                data_type=DataType.STRING,
                description="Unique trade identifier",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Trade ID is required")
                ]
            ),
            FieldDefinition(
                name="symbol",
                data_type=DataType.STRING,
                description="Trading pair symbol (e.g., 'BTC/USDT')",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Symbol is required")
                ]
            ),
            FieldDefinition(
                name="price",
                data_type=DataType.PRICE,
                description="Trade price",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Price is required"),
                    FieldConstraint(ConstraintType.MIN, 0, "Price must be positive")
                ]
            ),
            FieldDefinition(
                name="quantity",
                data_type=DataType.QUANTITY,
                description="Trade quantity",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Quantity is required"),
                    FieldConstraint(ConstraintType.MIN, 0, "Quantity must be non-negative")
                ]
            ),
            FieldDefinition(
                name="timestamp",
                data_type=DataType.TIMESTAMP,
                description="Trade timestamp in milliseconds",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Timestamp is required")
                ]
            ),
            FieldDefinition(
                name="side",
                data_type=DataType.STRING,
                description="Trade side (buy/sell)",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Side is required"),
                    FieldConstraint(
                        ConstraintType.ENUM, 
                        ["buy", "sell"], 
                        "Side must be either 'buy' or 'sell'"
                    )
                ]
            )
        ])
        
        self.add_schema("trade", trade_schema)
        
        # OHLCV candle schema
        ohlcv_schema = DataSchema("ohlcv", [
            FieldDefinition(
                name="timestamp",
                data_type=DataType.TIMESTAMP,
                description="Candle open time in milliseconds",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Timestamp is required")
                ]
            ),
            FieldDefinition(
                name="open",
                data_type=DataType.PRICE,
                description="Opening price",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Open price is required")
                ]
            ),
            FieldDefinition(
                name="high",
                data_type=DataType.PRICE,
                description="Highest price",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "High price is required")
                ]
            ),
            FieldDefinition(
                name="low",
                data_type=DataType.PRICE,
                description="Lowest price",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Low price is required")
                ]
            ),
            FieldDefinition(
                name="close",
                data_type=DataType.PRICE,
                description="Closing price",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Close price is required")
                ]
            ),
            FieldDefinition(
                name="volume",
                data_type=DataType.QUANTITY,
                description="Trading volume",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Volume is required")
                ]
            ),
            FieldDefinition(
                name="symbol",
                data_type=DataType.STRING,
                description="Trading pair symbol",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Symbol is required")
                ]
            )
        ])
        
        self.add_schema("ohlcv", ohlcv_schema)
        
        # Order book schema
        order_book_schema = DataSchema("orderbook", [
            FieldDefinition(
                name="timestamp",
                data_type=DataType.TIMESTAMP,
                description="Snapshot timestamp in milliseconds",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Timestamp is required")
                ]
            ),
            FieldDefinition(
                name="bids",
                data_type=DataType.STRING,  # Will be validated as list of [price, quantity] pairs
                description="List of bid [price, quantity] pairs",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Bids are required")
                ]
            ),
            FieldDefinition(
                name="asks",
                data_type=DataType.STRING,  # Will be validated as list of [price, quantity] pairs
                description="List of ask [price, quantity] pairs",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Asks are required")
                ]
            ),
            FieldDefinition(
                name="symbol",
                data_type=DataType.STRING,
                description="Trading pair symbol",
                constraints=[
                    FieldConstraint(ConstraintType.REQUIRED, True, "Symbol is required")
                ]
            )
        ])
        
        self.add_schema("orderbook", order_book_schema)
    
    def add_schema(self, name: str, schema: DataSchema) -> None:
        """Add a schema to the validator."""
        self.schemas[name] = schema
    
    def get_schema(self, name: str) -> Optional[DataSchema]:
        """Get a schema by name."""
        return self.schemas.get(name)
    
    async def validate(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        schema_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate data against a schema.
        
        Args:
            data: Data to validate (single record or list of records)
            schema_name: Name of the schema to validate against
            context: Additional context for validation
            
        Returns:
            Tuple of (is_valid, errors) where errors is a dictionary mapping 
            field names to lists of error messages
        """
        schema = self.get_schema(schema_name)
        if not schema:
            raise ValueError(f"Unknown schema: {schema_name}")
        
        if not data:
            return False, {"__root__": ["No data provided"]}
        
        # Handle single record or list of records
        is_list = isinstance(data, list)
        records = data if is_list else [data]
        
        all_errors = {}
        
        for i, record in enumerate(records):
            # Validate against schema
            errors = schema.validate(record)
            
            # Run additional validations
            if schema_name == "orderbook":
                book_errors = self._validate_order_book(record)
                if book_errors:
                    if "__book__" not in errors:
                        errors["__book__"] = []
                    errors["__book__"].extend(book_errors)
            
            # Add errors to the result
            if errors:
                # For lists, prefix with the index
                prefix = f"[{i}]." if is_list else ""
                for field, field_errors in errors.items():
                    full_field = f"{prefix}{field}"
                    if full_field not in all_errors:
                        all_errors[full_field] = []
                    all_errors[full_field].extend(field_errors)
        
        # Send alerts for validation errors
        if all_errors and self.alert_manager:
            await self._send_validation_alert(schema_name, all_errors, context)
        
        return len(all_errors) == 0, all_errors
    
    def _validate_order_book(self, book: Dict[str, Any]) -> List[str]:
        """Validate order book specific rules."""
        errors = []
        
        # Check bids and asks are lists
        for side in ["bids", "asks"]:
            if side in book and not isinstance(book[side], list):
                try:
                    book[side] = json.loads(book[side])
                except (json.JSONDecodeError, TypeError):
                    errors.append(f"{side} must be a list of [price, quantity] pairs")
                    continue
            
            # Check each price/quantity pair
            if isinstance(book.get(side), list):
                for i, level in enumerate(book[side]):
                    if not isinstance(level, (list, tuple)) or len(level) < 2:
                        errors.append(f"{side}[{i}] must be a [price, quantity] pair")
                        continue
                    
                    price, quantity = level[0], level[1]
                    if not isinstance(price, (int, float)) or price <= 0:
                        errors.append(f"{side}[{i}][0] (price) must be a positive number")
                    if not isinstance(quantity, (int, float)) or quantity < 0:
                        errors.append(f"{side}[{i}][1] (quantity) must be a non-negative number")
        
        # Check bid-ask spread
        if isinstance(book.get("bids"), list) and book["bids"] and \
           isinstance(book.get("asks"), list) and book["asks"]:
            try:
                best_bid = float(book["bids"][0][0])
                best_ask = float(book["asks"][0][0])
                
                if best_bid >= best_ask:
                    errors.append("Best bid must be less than best ask")
                
                spread = (best_ask - best_bid) / ((best_ask + best_bid) / 2) * 10000
                if spread > 100:  # More than 1% spread
                    errors.append(f"Unusually wide spread: {spread:.2f} bps")
                    
            except (TypeError, IndexError, ValueError):
                pass  # Already caught by earlier validations
        
        return errors
    
    async def validate_dataframe(
        self,
        df: pd.DataFrame,
        schema_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, List[Tuple[int, str]]]]:
        """
        Validate a pandas DataFrame against a schema.
        
        Args:
            df: DataFrame to validate
            schema_name: Name of the schema to validate against
            context: Additional context for validation
            
        Returns:
            Tuple of (is_valid, errors) where errors is a dictionary mapping 
            field names to lists of (row_index, error_message) tuples
        """
        schema = self.get_schema(schema_name)
        if not schema:
            raise ValueError(f"Unknown schema: {schema_name}")
        
        if df.empty:
            return False, {"__root__": [(-1, "Empty DataFrame")]}
        
        # Convert DataFrame to list of dicts for validation
        records = df.reset_index().to_dict('records')
        
        # Validate each record
        all_errors = {}
        
        for i, record in enumerate(records):
            errors = schema.validate(record)
            
            # Add row-specific errors
            for field, field_errors in errors.items():
                if field not in all_errors:
                    all_errors[field] = []
                all_errors[field].extend([(i, err) for err in field_errors])
        
        # Send alerts for validation errors
        if all_errors and self.alert_manager:
            # Convert to the format expected by _send_validation_alert
            flat_errors = {}
            for field, err_list in all_errors.items():
                flat_errors[field] = [f"Row {idx}: {err}" for idx, err in err_list]
            
            await self._send_validation_alert(schema_name, flat_errors, context)
        
        return len(all_errors) == 0, all_errors
    
    async def _send_validation_alert(
        self,
        schema_name: str,
        errors: Dict[str, List[str]],
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send an alert for validation errors."""
        if not self.alert_manager:
            return
        
        # Prepare error summary
        error_count = sum(len(err_list) for err_list in errors.values())
        error_fields = list(errors.keys())
        
        # Truncate error messages if there are too many
        sample_errors = []
        remaining = 5  # Show up to 5 sample errors
        
        for field, err_list in errors.items():
            for err in err_list:
                if remaining > 0:
                    sample_errors.append(f"{field}: {err}")
                    remaining -= 1
                else:
                    break
            if remaining <= 0:
                break
        
        # Create alert message
        message = (
            f"Found {error_count} validation errors in {schema_name} data\n"
            f"Affected fields: {', '.join(error_fields[:5])}"
            f"{', ...' if len(error_fields) > 5 else ''}\n\n"
            f"Sample errors:\n" + "\n".join(f"- {err}" for err in sample_errors)
        )
        
        # Add context to details
        details = {
            "schema": schema_name,
            "error_count": error_count,
            "error_fields": error_fields,
            "sample_errors": sample_errors,
            "context": context or {}
        }
        
        # Determine severity based on error count and context
        severity = AlertSeverity.WARNING
        if error_count > 100 or (context and context.get("critical", False)):
            severity = AlertSeverity.CRITICAL
        
        alert = Alert(
            alert_id=f"validation_{schema_name}_{int(time.time())}",
            alert_type=AlertType.DATA_VALIDATION_ERROR,
            severity=severity,
            title=f"Data Validation Failed: {schema_name}",
            message=message,
            details=details,
            timestamp=datetime.utcnow(),
            tags={
                "component": "data_validation",
                "schema": schema_name,
                "error_count": str(error_count)
            }
        )
        
        await self.alert_manager.send_alert(alert)

# Factory function
def create_data_validator(alert_manager: Optional[AlertManager] = None) -> DataValidator:
    """Create a new data validator instance."""
    return DataValidator(alert_manager)
