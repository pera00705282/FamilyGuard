"""
Database Connection Manager

This module provides a connection pool and management for database connections,
with support for connection pooling, retries, and health checks.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Type, TypeVar, Union

import aiosqlite

logger = logging.getLogger(__name__)

T = TypeVar('T')

class DatabaseType(str, Enum):
    """Supported database types."""
    SQLITE = "sqlite"
    POSTGRES = "postgres"
    MYSQL = "mysql"


@dataclass
class ConnectionConfig:
    """Database connection configuration."""
    db_type: DatabaseType = DatabaseType.SQLITE
    db_path: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    min_connections: int = 1
    max_connections: int = 10
    connect_timeout: float = 5.0
    command_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    pool_recycle: float = 3600.0  # Recycle connections after 1 hour


class ConnectionPool:
    """A simple connection pool for database connections."""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.pool: List[aiosqlite.Connection] = []
        self.in_use: Dict[aiosqlite.Connection, float] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        
    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new database connection."""
        if self.config.db_type == DatabaseType.SQLITE:
            conn = await aiosqlite.connect(
                database=self.config.db_path or ':memory:',
                timeout=self.config.command_timeout,
                isolation_level=None  # Enable autocommit mode
            )
            conn.row_factory = aiosqlite.Row
            
            # Configure SQLite for better performance
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA temp_store=MEMORY")
            await conn.execute("PRAGMA cache_size=-2000")  # 2MB cache
            await conn.execute("PRAGMA mmap_size=30000000000")  ~30GB
            await conn.commit()
            
            return conn
        else:
            raise NotImplementedError(f"{self.config.db_type} not yet implemented")
    
    async def acquire(self) -> aiosqlite.Connection:
        """Acquire a connection from the pool."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
            
        async with self._lock:
            # Try to get an available connection
            for conn in self.pool[:]:
                if conn not in self.in_use:
                    self.in_use[conn] = time.monotonic()
                    # Check if connection is still alive
                    try:
                        await conn.execute("SELECT 1")
                        return conn
                    except (sqlite3.Error, aiosqlite.Error):
                        # Remove dead connection
                        self.pool.remove(conn)
                        try:
                            await conn.close()
                        except Exception:
                            pass
            
            # If we get here, we need to create a new connection
            if len(self.pool) < self.config.max_connections:
                conn = await self._create_connection()
                self.pool.append(conn)
                self.in_use[conn] = time.monotonic()
                return conn
            
            # If we've reached max connections, wait for one to become available
            # with a timeout
            start_time = time.monotonic()
            while time.monotonic() - start_time < self.config.connect_timeout:
                for conn in list(self.in_use.keys()):
                    if time.monotonic() - self.in_use[conn] > self.config.command_timeout:
                        # Connection has been held too long, assume it's dead
                        logger.warning("Connection held too long, forcing release")
                        self.pool.remove(conn)
                        try:
                            await conn.close()
                        except Exception:
                            pass
                        self.in_use.pop(conn, None)
                        
                        # Create a new connection to replace it
                        new_conn = await self._create_connection()
                        self.pool.append(new_conn)
                        self.in_use[new_conn] = time.monotonic()
                        return new_conn
                
                await asyncio.sleep(0.1)
            
            raise TimeoutError("Timed out waiting for a database connection")
    
    async def release(self, conn: aiosqlite.Connection) -> None:
        """Release a connection back to the pool."""
        if self._closed:
            try:
                await conn.close()
            except Exception:
                pass
            return
            
        async with self._lock:
            if conn in self.in_use:
                # Check if connection needs to be recycled
                if time.monotonic() - self.in_use[conn] > self.config.pool_recycle:
                    self.pool.remove(conn)
                    try:
                        await conn.close()
                    except Exception:
                        pass
                else:
                    # Reset the connection state
                    try:
                        await conn.rollback()  # Rollback any open transactions
                        await conn.execute("PRAGMA optimize")  # Run optimization
                    except Exception as e:
                        logger.warning(f"Error resetting connection: {e}")
                        self.pool.remove(conn)
                        try:
                            await conn.close()
                        except Exception:
                            pass
                        return
                    
                    self.in_use.pop(conn, None)
            else:
                # Connection not from this pool, close it
                try:
                    await conn.close()
                except Exception:
                    pass
    
    async def close(self) -> None:
        """Close all connections in the pool."""
        if self._closed:
            return
            
        self._closed = True
        for conn in self.pool:
            try:
                await conn.close()
            except Exception:
                pass
        self.pool.clear()
        self.in_use.clear()
    
    async def __aenter__(self) -> 'ConnectionPool':
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


class DatabaseManager:
    """Manages database connections and provides a high-level API for database operations."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        if not self._initialized:
            self.config = config or ConnectionConfig()
            self._pool: Optional[ConnectionPool] = None
            self._initialized = True
    
    async def initialize(self) -> None:
        """Initialize the connection pool."""
        if self._pool is None:
            self._pool = ConnectionPool(self.config)
    
    async def close(self) -> None:
        """Close all database connections."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
    
    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Get a database connection from the pool."""
        if self._pool is None:
            await self.initialize()
            
        conn = None
        try:
            conn = await self._pool.acquire()
            yield conn
        except Exception as e:
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn is not None:
                await self._pool.release(conn)
    
    async def execute(self, query: str, params: Any = None) -> aiosqlite.Cursor:
        """Execute a query and return the cursor."""
        async with self.connection() as conn:
            try:
                return await conn.execute(query, params or ())
            except (sqlite3.Error, aiosqlite.Error) as e:
                logger.error(f"Error executing query: {query}")
                logger.error(f"Parameters: {params}")
                raise
    
    async def executemany(self, query: str, params_list: List[Any]) -> None:
        """Execute a query multiple times with different parameters."""
        async with self.connection() as conn:
            try:
                await conn.executemany(query, params_list)
            except (sqlite3.Error, aiosqlite.Error) as e:
                logger.error(f"Error executing query: {query}")
                logger.error(f"First parameters: {params_list[0] if params_list else 'None'}")
                raise
    
    async def fetch_all(self, query: str, params: Any = None) -> List[Dict[str, Any]]:
        """Execute a query and fetch all results as dictionaries."""
        async with self.connection() as conn:
            try:
                cursor = await conn.execute(query, params or ())
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
            except (sqlite3.Error, aiosqlite.Error) as e:
                logger.error(f"Error fetching all: {query}")
                raise
    
    async def fetch_one(self, query: str, params: Any = None) -> Optional[Dict[str, Any]]:
        """Execute a query and fetch one result as a dictionary."""
        async with self.connection() as conn:
            try:
                cursor = await conn.execute(query, params or ())
                row = await cursor.fetchone()
                return dict(row) if row else None
            except (sqlite3.Error, aiosqlite.Error) as e:
                logger.error(f"Error fetching one: {query}")
                raise
    
    async def execute_script(self, script: str) -> None:
        """Execute a SQL script."""
        async with self.connection() as conn:
            try:
                await conn.executescript(script)
            except (sqlite3.Error, aiosqlite.Error) as e:
                logger.error(f"Error executing script: {e}")
                raise


# Global database manager instance
db_manager = DatabaseManager()


async def init_db(config: Optional[ConnectionConfig] = None) -> DatabaseManager:
    """Initialize the global database manager."""
    global db_manager
    db_manager = DatabaseManager(config)
    await db_manager.initialize()
    return db_manager


async def close_db() -> None:
    """Close all database connections."""
    global db_manager
    if db_manager is not None:
        await db_manager.close()


# For backward compatibility
Database = DatabaseManager
