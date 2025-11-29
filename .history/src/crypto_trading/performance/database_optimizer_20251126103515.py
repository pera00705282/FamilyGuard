"""
Database Optimization Module

This module provides functionality for optimizing database performance
through indexing, query optimization, and maintenance tasks.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Tuple, Union
import logging
import sqlite3
import pandas as pd
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class IndexType(Enum):
    """Types of database indexes"""
    BTREE = auto()
    HASH = auto()
    RTREE = auto()
    
class DatabaseType(Enum):
    """Supported database types"""
    SQLITE = "sqlite"
    POSTGRES = "postgresql"
    MYSQL = "mysql"

@dataclass
class IndexConfig:
    """Configuration for a database index"""
    table_name: str
    columns: List[str]
    index_name: Optional[str] = None
    index_type: IndexType = IndexType.BTREE
    unique: bool = False
    if_not_exists: bool = True

@dataclass
class DatabaseConfig:
    """Database configuration parameters"""
    db_type: DatabaseType = DatabaseType.SQLITE
    db_path: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    db_name: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    
    # Optimization parameters
    cache_size: int = -2000  # SQLite pages, negative means KB
    journal_mode: str = "WAL"  # WAL, DELETE, TRUNCATE, PERSIST, MEMORY, OFF
    synchronous: str = "NORMAL"  # OFF, NORMAL, FULL, EXTRA
    temp_store: str = "MEMORY"  # DEFAULT, FILE, MEMORY
    mmap_size: int = 1024 * 1024 * 100  # 100MB
    auto_vacuum: bool = True
    busy_timeout: int = 5000  # ms
    
    def get_connection_string(self) -> str:
        """Generate appropriate connection string based on DB type"""
        if self.db_type == DatabaseType.SQLITE:
            return f"sqlite:///{self.db_path}"
        elif self.db_type in (DatabaseType.POSTGRES, DatabaseType.MYSQL):
            auth = f"{self.user}:{self.password}@" if self.user and self.password else ""
            return f"{self.db_type.value}://{auth}{self.host}:{self.port}/{self.db_name}"
        raise ValueError(f"Unsupported database type: {self.db_type}")

class DatabaseOptimizer:
    """Handles database optimization tasks"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
        self._connect()
        self._apply_pragmas()
    
    def _connect(self) -> None:
        """Establish database connection"""
        if self.config.db_type == DatabaseType.SQLITE:
            self.connection = sqlite3.connect(
                self.config.db_path,
                timeout=self.config.busy_timeout / 1000,  # Convert to seconds
                isolation_level=None  # Enable autocommit mode
            )
            self.connection.row_factory = sqlite3.Row
        else:
            # For other databases, you would use their respective connectors
            raise NotImplementedError(f"{self.config.db_type} support not implemented yet")
    
    def _apply_pragmas(self) -> None:
        """Apply SQLite PRAGMA settings for performance"""
        if self.config.db_type != DatabaseType.SQLITE:
            return
            
        cursor = self.connection.cursor()
        
        # Set journal mode (WAL is faster for most workloads)
        cursor.execute(f"PRAGMA journal_mode={self.config.journal_mode}")
        
        # Set synchronous mode (NORMAL is a good balance between safety and speed)
        cursor.execute(f"PRAGMA synchronous={self.config.synchronous}")
        
        # Set cache size (negative value means KB)
        cursor.execute(f"PRAGMA cache_size={self.config.cache_size}")
        
        # Set temp_store (MEMORY is faster for temporary tables)
        cursor.execute(f"PRAGMA temp_store={self.config.temp_store}")
        
        # Enable memory-mapped I/O
        cursor.execute(f"PRAGMA mmap_size={self.config.mmap_size}")
        
        # Auto-vacuum to prevent database bloat
        if self.config.auto_vacuum:
            cursor.execute("PRAGMA auto_vacuum=FULL")
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        
        # Enable WAL checkpointing (for WAL mode)
        if self.config.journal_mode.upper() == "WAL":
            cursor.execute("PRAGMA wal_autocheckpoint=100")  # Checkpoint every 100 pages
    
    def create_indexes(self, indexes: List[IndexConfig]) -> None:
        """Create multiple indexes"""
        with self.connection:
            for idx in indexes:
                self._create_index(idx)
    
    def _create_index(self, index: IndexConfig) -> None:
        """Create a single index"""
        if not index.columns:
            raise ValueError("At least one column must be specified for the index")
            
        index_name = index.index_name or f"idx_{index.table_name}_{'_'.join(index.columns)}"
        columns = ", ".join(index.columns)
        unique = "UNIQUE" if index.unique else ""
        if_not_exists = "IF NOT EXISTS" if index.if_not_exists else ""
        
        # SQLite doesn't support index types in CREATE INDEX
        if self.config.db_type == DatabaseType.SQLITE:
            sql = f"""
            CREATE {unique} INDEX {if_not_exists} "{index_name}" 
            ON "{index.table_name}" ({columns})
            """
        else:
            # For other databases that support index types
            sql = f"""
            CREATE {unique} INDEX {if_not_exists} "{index_name}" 
            ON "{index.table_name}" USING {index.index_type.name} ({columns})
            """
        
        try:
            self.connection.execute(sql)
            logger.info(f"Created index {index_name} on {index.table_name}({columns})")
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            raise
    
    def analyze_query(self, query: str, params: Optional[tuple] = None) -> Dict[str, Any]:
        """Analyze a query's execution plan"""
        if self.config.db_type == DatabaseType.SQLITE:
            explain_query = f"EXPLAIN QUERY PLAN {query}"
            cursor = self.connection.cursor()
            cursor.execute(explain_query, params or ())
            plan = cursor.fetchall()
            return {"plan": plan, "query": explain_query}
        else:
            # For other databases, you would use their EXPLAIN syntax
            raise NotImplementedError(f"Query analysis not implemented for {self.config.db_type}")
    
    def optimize_tables(self, table_names: Optional[List[str]] = None) -> None:
        """Optimize database tables (ANALYZE, VACUUM, etc.)"""
        if self.config.db_type == DatabaseType.SQLITE:
            with self.connection:
                # Run ANALYZE to update query planner statistics
                self.connection.execute("ANALYZE")
                
                # VACUUM to rebuild the database file, repacking it into a minimal amount of disk space
                self.connection.execute("VACUUM")
                
                # For WAL mode, run checkpoint to ensure all changes are written to the main database
                if self.config.journal_mode.upper() == "WAL":
                    self.connection.execute("PRAGMA wal_checkpoint(FULL)")
        else:
            # For other databases, you would use their specific optimization commands
            raise NotImplementedError(f"Table optimization not implemented for {self.config.db_type}")
    
    def get_table_info(self, table_name: str) -> pd.DataFrame:
        """Get information about a table's structure and indexes"""
        if self.config.db_type == DatabaseType.SQLITE:
            # Get table info
            cursor = self.connection.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [dict(row) for row in cursor.fetchall()]
            
            # Get index info
            cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = []
            for idx in cursor.fetchall():
                idx_info = dict(idx)
                cursor.execute(f"PRAGMA index_info({idx_info['name']})")
                idx_columns = [dict(row)['name'] for row in cursor.fetchall()]
                idx_info['columns'] = idx_columns
                indexes.append(idx_info)
            
            # Convert to pandas DataFrame for better display
            df_columns = pd.DataFrame(columns)
            df_indexes = pd.DataFrame(indexes)
            
            return {"columns": df_columns, "indexes": df_indexes}
        else:
            # For other databases, you would query their system catalogs
            raise NotImplementedError(f"Table info not implemented for {self.config.db_type}")
    
    def query_to_dataframe(self, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """Execute a query and return results as a pandas DataFrame"""
        return pd.read_sql_query(query, self.connection, params=params)
    
    def batch_insert(self, table_name: str, data: List[Dict], batch_size: int = 1000) -> int:
        """Efficiently insert multiple rows in batches"""
        if not data:
            return 0
            
        columns = list(data[0].keys())
        placeholders = ", ".join([":" + col for col in columns])
        columns_str = ", ".join([f'"{col}"' for col in columns])
        
        sql = f"INSERT INTO \"{table_name}\" ({columns_str}) VALUES ({placeholders})"
        
        total_rows = 0
        cursor = self.connection.cursor()
        
        try:
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                cursor.executemany(sql, batch)
                total_rows += len(batch)
            self.connection.commit()
            return total_rows
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Batch insert failed: {e}")
            raise
    
    def close(self) -> None:
        """Close the database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Example usage
if __name__ == "__main__":
    import os
    import tempfile
    
    # Create a temporary SQLite database for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = tmp.name
    
    try:
        # Configure the database
        config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            db_path=db_path,
            cache_size=-20000,  # 20MB cache
            journal_mode="WAL",
            synchronous="NORMAL"
        )
        
        # Create a sample table
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                timestamp DATETIME,
                symbol TEXT,
                price REAL,
                volume REAL,
                PRIMARY KEY (timestamp, symbol)
            )
            """)
        
        # Initialize the optimizer
        with DatabaseOptimizer(config) as optimizer:
            # Create some indexes
            indexes = [
                IndexConfig("market_data", ["symbol"], index_name="idx_market_data_symbol"),
                IndexConfig("market_data", ["timestamp"], index_name="idx_market_data_timestamp"),
                IndexConfig("market_data", ["symbol", "timestamp"], index_name="idx_market_data_symbol_timestamp")
            ]
            optimizer.create_indexes(indexes)
            
            # Generate sample data
            symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
            now = datetime.utcnow()
            data = []
            
            for i in range(1000):
                for symbol in symbols:
                    data.append({
                        "timestamp": (now - timedelta(minutes=i)).isoformat(),
                        "symbol": symbol,
                        "price": 100 + (i % 50) + (hash(symbol) % 100) / 10,
                        "volume": 1000 + (i % 100) * 10
                    })
            
            # Batch insert the data
            optimizer.batch_insert("market_data", data)
            
            # Query the data
            df = optimizer.query_to_dataframe(
                """
                SELECT symbol, AVG(price) as avg_price, SUM(volume) as total_volume
                FROM market_data
                WHERE timestamp >= ?
                GROUP BY symbol
                ORDER BY total_volume DESC
                """,
                ((now - timedelta(hours=1)).isoformat(),)
            )
            
            print("\nMarket Data Summary (Last Hour):")
            print(df)
            
            # Get table info
            table_info = optimizer.get_table_info("market_data")
            print("\nTable Columns:")
            print(table_info["columns"])
            print("\nTable Indexes:")
            print(table_info["indexes"])
            
            # Analyze a query
            analysis = optimizer.analyze_query(
                "SELECT * FROM market_data WHERE symbol = ? AND timestamp >= ?",
                ("BTC/USDT", (now - timedelta(hours=1)).isoformat())
            )
            print("\nQuery Plan:")
            for row in analysis["plan"]:
                print(row)
            
    finally:
        # Clean up
        try:
            os.unlink(db_path)
        except:
            pass
