"""
Data storage and retrieval for market data.
"""
import os
import json
import gzip
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, AsyncIterator, Tuple
from pathlib import Path
import logging
from enum import Enum
import aiosqlite
import pandas as pd
import numpy as np

from ..config import config
from ..monitoring.metrics import metrics

logger = logging.getLogger(__name__)

class StorageFormat(str, Enum):
    """Supported storage formats."""
    PARQUET = "parquet"
    CSV = "csv"
    JSON = "json"
    SQLITE = "sqlite"

class DataStorage:
    """Handles storage and retrieval of market data."""
    
    def __init__(
        self,
        base_dir: Optional[str] = None,
        storage_format: StorageFormat = StorageFormat.PARQUET,
        max_file_size_mb: int = 100,
        compression: bool = True,
    ):
        """
        Initialize the data storage.
        
        Args:
            base_dir: Base directory for data storage
            storage_format: Storage format to use
            max_file_size_mb: Maximum file size in MB before creating a new file
            compression: Whether to use compression for stored files
        """
        self.base_dir = Path(base_dir or config.data_dir) / "market_data"
        self.storage_format = StorageFormat(storage_format)
        self.max_file_size = max_file_size_mb * 1024 * 1024  # Convert MB to bytes
        self.compression = compression
        self._connections: Dict[str, aiosqlite.Connection] = {}
        
        # Create base directory if it doesn't exist
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Initialize metrics
        self._init_metrics()
    
    def _init_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        # Data storage metrics
        metrics.metrics["data_storage_operations"] = metrics.Counter(
            "data_storage_operations",
            "Number of storage operations",
            ["operation", "data_type", "exchange", "symbol"]
        )
        
        metrics.metrics["data_storage_errors"] = metrics.Counter(
            "data_storage_errors",
            "Number of storage errors",
            ["error_type", "operation", "data_type"]
        )
        
        metrics.metrics["data_storage_size_bytes"] = metrics.Gauge(
            "data_storage_size_bytes",
            "Total size of stored data in bytes",
            ["data_type", "exchange", "symbol"]
        )
        
        metrics.metrics["data_storage_latency_seconds"] = metrics.Histogram(
            "data_storage_latency_seconds",
            "Latency of storage operations in seconds",
            ["operation", "data_type"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        )
    
    def _get_file_path(
        self,
        data_type: str,
        exchange: str,
        symbol: str,
        timestamp: Optional[datetime] = None,
        create_dir: bool = True
    ) -> Path:
        """
        Get the file path for storing data.
        
        Args:
            data_type: Type of data (e.g., 'trades', 'ohlcv')
            exchange: Exchange name
            symbol: Trading pair symbol
            timestamp: Timestamp for time-based partitioning
            create_dir: Whether to create the directory if it doesn't exist
            
        Returns:
            Path to the data file
        """
        # Clean and normalize inputs
        exchange = exchange.lower().replace(" ", "_")
        symbol = symbol.replace("/", "-").upper()
        
        # Create directory structure: base/exchange/data_type/symbol/
        if timestamp:
            # Time-based partitioning: YYYY/MM/DD
            date_str = timestamp.strftime("%Y/%m/%d")
            dir_path = self.base_dir / exchange / data_type / symbol / date_str
        else:
            dir_path = self.base_dir / exchange / data_type / symbol
        
        if create_dir:
            os.makedirs(dir_path, exist_ok=True)
        
        # Determine file extension
        if self.storage_format == StorageFormat.PARQUET:
            ext = ".parquet"
            if self.compression:
                ext += ".gz"
        elif self.storage_format == StorageFormat.CSV:
            ext = ".csv"
            if self.compression:
                ext += ".gz"
        elif self.storage_format == StorageFormat.JSON:
            ext = ".json"
            if self.compression:
                ext += ".gz"
        else:
            ext = ".db"
        
        # Create filename
        if timestamp:
            # Include timestamp in filename for time-series data
            filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}{ext}"
        else:
            # For non-time-series data or when timestamp is not provided
            filename = f"data{ext}"
        
        return dir_path / filename
    
    async def store_data(
        self,
        data_type: str,
        exchange: str,
        symbol: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        timestamp: Optional[datetime] = None,
        **kwargs
    ) -> None:
        """
        Store market data.
        
        Args:
            data_type: Type of data (e.g., 'trades', 'ohlcv')
            exchange: Exchange name
            symbol: Trading pair symbol
            data: Data to store (can be a single record or a list)
            timestamp: Timestamp for the data (default: current time)
            **kwargs: Additional parameters for specific storage formats
        """
        if not data:
            return
            
        timestamp = timestamp or datetime.utcnow()
        
        # Convert single record to list
        if isinstance(data, dict):
            data = [data]
        
        try:
            # Update metrics
            metrics.metrics["data_storage_operations"].labels(
                operation="store",
                data_type=data_type,
                exchange=exchange,
                symbol=symbol
            ).inc(len(data))
            
            # Store based on format
            if self.storage_format == StorageFormat.SQLITE:
                await self._store_sqlite(data_type, exchange, symbol, data, timestamp, **kwargs)
            else:
                await self._store_file(data_type, exchange, symbol, data, timestamp, **kwargs)
            
            # Update storage size metric
            await self._update_storage_metrics()
            
        except Exception as e:
            logger.error(f"Error storing {data_type} data for {exchange}/{symbol}: {e}", exc_info=True)
            metrics.metrics["data_storage_errors"].labels(
                error_type="storage_error",
                operation="store",
                data_type=data_type
            ).inc()
    
    async def _store_file(
        self,
        data_type: str,
        exchange: str,
        symbol: str,
        data: List[Dict[str, Any]],
        timestamp: datetime,
        **kwargs
    ) -> None:
        """Store data in a file (Parquet, CSV, or JSON)."""
        file_path = self._get_file_path(data_type, exchange, symbol, timestamp)
        
        # Convert to DataFrame for easier handling
        df = pd.DataFrame(data)
        
        # Ensure timestamp is in datetime format
        if 'timestamp' in df.columns:
            if pd.api.types.is_numeric_dtype(df['timestamp']):
                # Assume timestamp is in milliseconds
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Store based on format
        if self.storage_format == StorageFormat.PARQUET:
            compression = 'gzip' if self.compression else None
            df.to_parquet(file_path, compression=compression, index=False)
            
        elif self.storage_format == StorageFormat.CSV:
            if self.compression:
                with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                    df.to_csv(f, index=False)
            else:
                df.to_csv(file_path, index=False)
                
        elif self.storage_format == StorageFormat.JSON:
            if self.compression:
                with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                    json.dump(df.to_dict(orient='records'), f)
            else:
                with open(file_path, 'w') as f:
                    json.dump(df.to_dict(orient='records'), f, indent=2)
    
    async def _store_sqlite(
        self,
        data_type: str,
        exchange: str,
        symbol: str,
        data: List[Dict[str, Any]],
        timestamp: datetime,
        batch_size: int = 1000,
        **kwargs
    ) -> None:
        """Store data in SQLite database."""
        if not data:
            return
            
        # Get or create database connection
        db_path = self._get_file_path(data_type, exchange, symbol, create_dir=True).with_suffix('.db')
        conn = await self._get_db_connection(str(db_path))
        
        # Create table if it doesn't exist
        table_name = f"{data_type}_{symbol.replace('-', '_').lower()}"
        await self._create_table_if_not_exists(conn, table_name, data[0])
        
        # Insert data in batches
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            columns = batch[0].keys()
            placeholders = ', '.join(['?'] * len(columns))
            columns_str = ', '.join(columns)
            
            # Prepare data for batch insert
            values = []
            for item in batch:
                row = []
                for col in columns:
                    val = item.get(col)
                    # Convert datetime to ISO format string
                    if isinstance(val, datetime):
                        val = val.isoformat()
                    row.append(val)
                values.append(tuple(row))
            
            # Execute batch insert
            query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
            try:
                await conn.executemany(query, values)
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                logger.error(f"Error inserting batch {i//batch_size + 1}: {e}")
                raise
    
    async def _get_db_connection(self, db_path: str) -> aiosqlite.Connection:
        """Get or create a database connection."""
        if db_path not in self._connections:
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Connect to SQLite database
            conn = await aiosqlite.connect(db_path)
            conn.row_factory = aiosqlite.Row
            self._connections[db_path] = conn
            
            # Enable WAL mode for better concurrency
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.commit()
            
        return self._connections[db_path]
    
    async def _create_table_if_not_exists(
        self,
        conn: aiosqlite.Connection,
        table_name: str,
        sample_data: Dict[str, Any]
    ) -> None:
        """Create a table if it doesn't exist."""
        # Generate column definitions
        columns = []
        for col, val in sample_data.items():
            if isinstance(val, (int, float, bool)) and not isinstance(val, bool):
                col_type = "REAL" if isinstance(val, float) else "INTEGER"
            elif isinstance(val, bool):
                col_type = "INTEGER"  # SQLite doesn't have a boolean type
            elif isinstance(val, (str, datetime)):
                col_type = "TEXT"
            else:
                col_type = "TEXT"  # Default to TEXT for other types
                
            columns.append(f"{col} {col_type}")
        
        # Add timestamp if not present
        if 'timestamp' not in sample_data:
            columns.append("timestamp TEXT")
        
        # Create table
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {', '.join(columns)},
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        await conn.execute(create_table_sql)
        await conn.commit()
        
        # Create index on timestamp if it exists
        if 'timestamp' in sample_data or 'timestamp' in [c.split()[0] for c in columns]:
            try:
                await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp ON {table_name}(timestamp)")
                await conn.commit()
            except Exception as e:
                logger.warning(f"Failed to create timestamp index: {e}")
    
    async def query_data(
        self,
        data_type: str,
        exchange: str,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        **filters
    ) -> List[Dict[str, Any]]:
        """
        Query stored market data.
        
        Args:
            data_type: Type of data to query
            exchange: Exchange name
            symbol: Trading pair symbol
            start_time: Start time for the query
            end_time: End time for the query
            limit: Maximum number of records to return
            **filters: Additional filters
            
        Returns:
            List of matching records
        """
        try:
            start = datetime.utcnow()
            
            if self.storage_format == StorageFormat.SQLITE:
                result = await self._query_sqlite(
                    data_type, exchange, symbol, 
                    start_time, end_time, limit, **filters
                )
            else:
                result = await self._query_files(
                    data_type, exchange, symbol,
                    start_time, end_time, limit, **filters
                )
            
            # Update metrics
            metrics.metrics["data_storage_operations"].labels(
                operation="query",
                data_type=data_type,
                exchange=exchange,
                symbol=symbol
            ).inc()
            
            metrics.metrics["data_storage_latency_seconds"].labels(
                operation="query",
                data_type=data_type
            ).observe((datetime.utcnow() - start).total_seconds())
            
            return result
            
        except Exception as e:
            logger.error(f"Error querying {data_type} data for {exchange}/{symbol}: {e}", exc_info=True)
            metrics.metrics["data_storage_errors"].labels(
                error_type="query_error",
                operation="query",
                data_type=data_type
            ).inc()
            raise
    
    async def _query_sqlite(
        self,
        data_type: str,
        exchange: str,
        symbol: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: Optional[int],
        **filters
    ) -> List[Dict[str, Any]]:
        """Query data from SQLite database."""
        # Get database connection
        db_path = self._get_file_path(data_type, exchange, symbol).with_suffix('.db')
        if not os.path.exists(db_path):
            return []
            
        conn = await self._get_db_connection(str(db_path))
        
        # Build query
        table_name = f"{data_type}_{symbol.replace('-', '_').lower()}"
        query = f"SELECT * FROM {table_name}"
        params = []
        conditions = []
        
        # Add time range conditions
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
            
        # Add filter conditions
        for key, value in filters.items():
            if value is not None:
                conditions.append(f"{key} = ?")
                params.append(value)
        
        # Combine conditions
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # Add ordering and limit
        query += " ORDER BY timestamp"
        if limit:
            query += f" LIMIT {limit}"
        
        # Execute query
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        
        # Convert to list of dicts
        result = [dict(row) for row in rows]
        
        # Convert string timestamps back to datetime objects
        for item in result:
            if 'timestamp' in item and isinstance(item['timestamp'], str):
                try:
                    item['timestamp'] = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass
        
        return result
    
    async def _query_files(
        self,
        data_type: str,
        exchange: str,
        symbol: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: Optional[int],
        **filters
    ) -> List[Dict[str, Any]]:
        """Query data from files."""
        # Find all matching files
        base_dir = self.base_dir / exchange / data_type / symbol.replace("/", "-")
        if not os.path.exists(base_dir):
            return []
        
        # Get all files that could contain data in the time range
        files = []
        for root, _, filenames in os.walk(base_dir):
            for filename in filenames:
                if filename.startswith('.') or not filename.endswith(self._get_file_extension()):
                    continue
                    
                file_path = Path(root) / filename
                file_time = self._get_file_time(file_path)
                
                # Skip files outside the time range
                if start_time and file_time and file_time.date() < start_time.date():
                    continue
                if end_time and file_time and file_time.date() > end_time.date():
                    continue
                    
                files.append(file_path)
        
        # Sort files by time (oldest first)
        files.sort(key=lambda f: self._get_file_time(f) or datetime.min)
        
        # Read and filter data
        result = []
        for file_path in files:
            try:
                df = await self._read_file(file_path)
                if df is None or df.empty:
                    continue
                
                # Filter by time range
                if 'timestamp' in df.columns:
                    if pd.api.types.is_numeric_dtype(df['timestamp']):
                        # Convert timestamp from milliseconds to datetime
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    else:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                    if start_time:
                        df = df[df['timestamp'] >= start_time]
                    if end_time:
                        df = df[df['timestamp'] <= end_time]
                
                # Apply additional filters
                for key, value in filters.items():
                    if key in df.columns and value is not None:
                        df = df[df[key] == value]
                
                # Add to results
                result.extend(df.to_dict('records'))
                
                # Check if we've reached the limit
                if limit and len(result) >= limit:
                    result = result[:limit]
                    break
                    
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                continue
        
        return result
    
    def _get_file_extension(self) -> str:
        """Get the file extension for the current storage format."""
        if self.storage_format == StorageFormat.PARQUET:
            return ".parquet" + (".gz" if self.compression else "")
        elif self.storage_format == StorageFormat.CSV:
            return ".csv" + (".gz" if self.compression else "")
        elif self.storage_format == StorageFormat.JSON:
            return ".json" + (".gz" if self.compression else "")
        return ".db"
    
    def _get_file_time(self, file_path: Path) -> Optional[datetime]:
        """Extract timestamp from filename or return file modification time."""
        try:
            # Try to extract timestamp from filename (format: YYYYMMDD_HHMMSS.ext)
            filename = file_path.stem
            if '_' in filename:
                timestamp_str = filename.split('_')[0]
                if len(timestamp_str) == 8:  # YYYYMMDD
                    return datetime.strptime(timestamp_str, '%Y%m%d')
        except (ValueError, IndexError):
            pass
            
        # Fall back to file modification time
        try:
            return datetime.fromtimestamp(file_path.stat().st_mtime)
        except (OSError, AttributeError):
            return None
    
    async def _read_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Read data from a file."""
        if not file_path.exists():
            return None
            
        try:
            if file_path.suffix == '.parquet' or file_path.suffix == '.parquet.gz':
                return pd.read_parquet(file_path)
            elif file_path.suffix == '.csv' or (file_path.suffix == '.gz' and file_path.stem.endswith('.csv')):
                if str(file_path).endswith('.gz'):
                    return pd.read_csv(file_path, compression='gzip')
                return pd.read_csv(file_path)
            elif file_path.suffix == '.json' or (file_path.suffix == '.gz' and file_path.stem.endswith('.json')):
                if str(file_path).endswith('.gz'):
                    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                        data = json.load(f)
                else:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                return pd.DataFrame(data)
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    async def _update_storage_metrics(self) -> None:
        """Update storage size metrics."""
        try:
            # Walk through the data directory and calculate sizes
            for root, _, files in os.walk(self.base_dir):
                for file in files:
                    if file.startswith('.'):
                        continue
                        
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(self.base_dir)
                    
                    # Extract exchange, data_type, and symbol from path
                    parts = rel_path.parts
                    if len(parts) >= 3:  # exchange/data_type/symbol/...
                        exchange = parts[0]
                        data_type = parts[1]
                        symbol = parts[2]
                        
                        # Update metrics
                        try:
                            file_size = file_path.stat().st_size
                            metrics.metrics["data_storage_size_bytes"].labels(
                                data_type=data_type,
                                exchange=exchange,
                                symbol=symbol
                            ).inc(file_size)
                        except OSError:
                            pass
        except Exception as e:
            logger.error(f"Error updating storage metrics: {e}")
    
    async def cleanup_old_data(
        self,
        max_age_days: int = 30,
        data_types: Optional[List[str]] = None,
        exchanges: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None
    ) -> int:
        """
        Clean up old data files.
        
        Args:
            max_age_days: Maximum age of files to keep (in days)
            data_types: List of data types to clean up (None for all)
            exchanges: List of exchanges to clean up (None for all)
            symbols: List of symbols to clean up (None for all)
            
        Returns:
            Number of files deleted
        """
        cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
        deleted_count = 0
        
        try:
            for root, _, files in os.walk(self.base_dir):
                for file in files:
                    if file.startswith('.'):
                        continue
                        
                    file_path = Path(root) / file
                    file_time = self._get_file_time(file_path)
                    
                    # Skip files newer than cutoff
                    if file_time and file_time > cutoff_time:
                        continue
                    
                    # Check if file matches filters
                    rel_path = file_path.relative_to(self.base_dir)
                    parts = rel_path.parts
                    
                    if len(parts) >= 3:  # exchange/data_type/symbol/...
                        exchange = parts[0]
                        data_type = parts[1]
                        symbol = parts[2].split('.')[0]  # Remove file extension
                        
                        if data_types and data_type not in data_types:
                            continue
                        if exchanges and exchange not in exchanges:
                            continue
                        if symbols and symbol not in symbols:
                            continue
                        
                        # Delete the file
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                            logger.debug(f"Deleted old file: {file_path}")
                        except OSError as e:
                            logger.error(f"Error deleting file {file_path}: {e}")
            
            # Vacuum SQLite databases if any were modified
            await self._vacuum_databases()
            
            # Update metrics
            metrics.metrics["data_storage_operations"].labels(
                operation="cleanup",
                data_type=",".join(data_types) if data_types else "all",
                exchange=",".join(exchanges) if exchanges else "all",
                symbol=",".join(symbols) if symbols else "all"
            ).inc()
            
            logger.info(f"Cleaned up {deleted_count} old data files")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during data cleanup: {e}")
            metrics.metrics["data_storage_errors"].labels(
                error_type="cleanup_error",
                operation="cleanup",
                data_type="all"
            ).inc()
            raise
    
    async def _vacuum_databases(self) -> None:
        """Run VACUUM on all SQLite databases to reclaim disk space."""
        for db_path, conn in list(self._connections.items()):
            try:
                await conn.execute("VACUUM")
                await conn.commit()
            except Exception as e:
                logger.error(f"Error vacuuming database {db_path}: {e}")
    
    async def backup_data(
        self,
        backup_dir: Optional[str] = None,
        compress: bool = True,
        data_types: Optional[List[str]] = None,
        exchanges: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None
    ) -> str:
        """
        Create a backup of the stored data.
        
        Args:
            backup_dir: Directory to store the backup (default: base_dir/backups)
            compress: Whether to compress the backup
            data_types: List of data types to include (None for all)
            exchanges: List of exchanges to include (None for all)
            symbols: List of symbols to include (None for all)
            
        Returns:
            Path to the backup file
        """
        import shutil
        import tempfile
        from datetime import datetime
        
        # Create backup directory
        backup_dir = Path(backup_dir or (self.base_dir / 'backups'))
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create a temporary directory for the backup
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            backup_name = f"trading_data_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            backup_path = temp_dir / backup_name
            
            # Copy files to the temporary directory
            for root, dirs, files in os.walk(self.base_dir):
                # Skip backup directory
                if 'backups' in root.split(os.sep):
                    continue
                
                # Create relative path
                rel_path = Path(root).relative_to(self.base_dir)
                
                # Check if this path should be included based on filters
                parts = rel_path.parts
                if len(parts) >= 2:  # exchange/data_type/...
                    exchange = parts[0]
                    data_type = parts[1]
                    symbol = parts[2] if len(parts) > 2 else None
                    
                    if data_types and data_type not in data_types:
                        continue
                    if exchanges and exchange not in exchanges:
                        continue
                    if symbols and symbol and symbol not in symbols:
                        continue
                
                # Create target directory
                target_dir = backup_path / rel_path
                os.makedirs(target_dir, exist_ok=True)
                
                # Copy files
                for file in files:
                    if file.startswith('.'):
                        continue
                        
                    src_file = Path(root) / file
                    dst_file = target_dir / file
                    shutil.copy2(src_file, dst_file)
            
            # Create archive
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{backup_name}.{'tar.gz' if compress else 'tar'}"
            final_backup_path = backup_dir / backup_filename
            
            # Create tar archive
            if compress:
                shutil.make_archive(
                    str(backup_path),
                    'gztar',
                    root_dir=temp_dir,
                    base_dir=backup_name
                )
                shutil.move(f"{backup_path}.tar.gz", final_backup_path)
            else:
                shutil.make_archive(
                    str(backup_path),
                    'tar',
                    root_dir=temp_dir,
                    base_dir=backup_name
                )
                shutil.move(f"{backup_path}.tar", final_backup_path)
            
            # Update metrics
            backup_size = final_backup_path.stat().st_size
            metrics.metrics["data_storage_operations"].labels(
                operation="backup",
                data_type=",".join(data_types) if data_types else "all",
                exchange=",".join(exchanges) if exchanges else "all",
                symbol=",".join(symbols) if symbols else "all"
            ).inc()
            
            logger.info(f"Created backup: {final_backup_path} ({backup_size/1024/1024:.2f} MB)")
            return str(final_backup_path)
    
    async def close(self) -> None:
        """Close all database connections and clean up resources."""
        for conn in self._connections.values():
            try:
                await conn.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
        
        self._connections.clear()
        logger.info("Data storage closed")
    
    def __del__(self) -> None:
        """Ensure resources are cleaned up when the object is destroyed."""
        if hasattr(self, '_connections') and self._connections:
            for conn in self._connections.values():
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(conn.close())
                    else:
                        loop.run_until_complete(conn.close())
                except Exception:
                    pass

# Singleton instance
storage = DataStorage()

async def init_storage() -> DataStorage:
    """Initialize the global storage instance."""
    global storage
    storage = DataStorage()
    return storage

async def close_storage() -> None:
    """Close the global storage instance."""
    global storage
    if storage:
        await storage.close()
