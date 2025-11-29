"""
Base data collector for fetching market data from exchanges.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Any, AsyncIterator
from datetime import datetime, timedelta
import asyncio
import logging
from enum import Enum

from ..exchanges.base_websocket import BaseWebSocketClient
from ..config import config
from ..monitoring.metrics import metrics

logger = logging.getLogger(__name__)

class DataType(str, Enum):
    """Types of market data."""
    TRADES = "trades"
    ORDER_BOOK = "order_book"
    OHLCV = "ohlcv"
    TICKER = "ticker"
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"

class Timeframe(str, Enum):
    """Timeframes for OHLCV data."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"

class DataCollector(ABC):
    """Abstract base class for data collectors."""
    
    def __init__(self, exchange_name: str):
        """
        Initialize the data collector.
        
        Args:
            exchange_name: Name of the exchange
        """
        self.exchange_name = exchange_name
        self.running = False
        self._subscribers = set()
        self._websocket: Optional[BaseWebSocketClient] = None
        self._last_update: Dict[str, datetime] = {}
        
    async def start(self) -> None:
        """Start the data collector."""
        if self.running:
            return
            
        self.running = True
        logger.info(f"Starting {self.exchange_name} data collector")
        
        # Initialize WebSocket connection if needed
        if self._websocket is None:
            self._websocket = await self._init_websocket()
            
        await self._start_websocket()
    
    async def stop(self) -> None:
        """Stop the data collector."""
        if not self.running:
            return
            
        self.running = False
        logger.info(f"Stopping {self.exchange_name} data collector")
        
        if self._websocket:
            await self._websocket.disconnect()
            self._websocket = None
    
    async def subscribe(self, data_type: DataType, symbol: str, **kwargs) -> None:
        """
        Subscribe to market data.
        
        Args:
            data_type: Type of data to subscribe to
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            **kwargs: Additional parameters specific to the data type
        """
        normalized_symbol = self.normalize_symbol(symbol)
        subscription_key = f"{data_type.value}:{normalized_symbol}"
        
        if subscription_key in self._subscribers:
            return
            
        self._subscribers.add(subscription_key)
        logger.info(f"Subscribed to {data_type.value} for {normalized_symbol}")
        
        # Update metrics
        metrics.metrics["data_subscriptions"].labels(
            exchange=self.exchange_name,
            data_type=data_type.value,
            symbol=normalized_symbol
        ).inc()
        
        # Forward to WebSocket if connected
        if self._websocket and self._websocket.connected:
            await self._subscribe_websocket(data_type, normalized_symbol, **kwargs)
    
    async def unsubscribe(self, data_type: DataType, symbol: str) -> None:
        """
        Unsubscribe from market data.
        
        Args:
            data_type: Type of data to unsubscribe from
            symbol: Trading pair symbol
        """
        normalized_symbol = self.normalize_symbol(symbol)
        subscription_key = f"{data_type.value}:{normalized_symbol}"
        
        if subscription_key not in self._subscribers:
            return
            
        self._subscribers.remove(subscription_key)
        logger.info(f"Unsubscribed from {data_type.value} for {normalized_symbol}")
        
        # Forward to WebSocket if connected
        if self._websocket and self._websocket.connected:
            await self._unsubscribe_websocket(data_type, normalized_symbol)
    
    async def get_historical_data(
        self,
        data_type: DataType,
        symbol: str,
        start_time: Optional[Union[datetime, int, str]] = None,
        end_time: Optional[Union[datetime, int, str]] = None,
        limit: int = 1000,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical market data.
        
        Args:
            data_type: Type of data to fetch
            symbol: Trading pair symbol
            start_time: Start time for the data
            end_time: End time for the data
            limit: Maximum number of data points to return
            **kwargs: Additional parameters specific to the data type
            
        Returns:
            List of data points
        """
        normalized_symbol = self.normalize_symbol(symbol)
        
        # Convert timestamps to milliseconds if needed
        if isinstance(start_time, datetime):
            start_time = int(start_time.timestamp() * 1000)
        if isinstance(end_time, datetime):
            end_time = int(end_time.timestamp() * 1000)
            
        # Record metrics
        metrics.metrics["historical_data_requests"].labels(
            exchange=self.exchange_name,
            data_type=data_type.value,
            symbol=normalized_symbol
        ).inc()
        
        # Fetch the data
        try:
            data = await self._fetch_historical_data(
                data_type=data_type,
                symbol=normalized_symbol,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                **kwargs
            )
            
            # Update metrics
            metrics.metrics["historical_data_points"].labels(
                exchange=self.exchange_name,
                data_type=data_type.value,
                symbol=normalized_symbol
            ).inc(len(data))
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching historical {data_type.value} data for {normalized_symbol}: {e}")
            metrics.metrics["data_errors"].labels(
                exchange=self.exchange_name,
                error_type="historical_data_fetch"
            ).inc()
            raise
    
    def register_callback(self, callback: callable) -> None:
        """
        Register a callback function to receive market data updates.
        
        Args:
            callback: Callback function with signature (data_type, symbol, data)
        """
        if not callable(callback):
            raise ValueError("Callback must be a callable function")
            
        if not hasattr(self, '_callbacks'):
            self._callbacks = set()
            
        self._callbacks.add(callback)
    
    def unregister_callback(self, callback: callable) -> None:
        """
        Unregister a callback function.
        
        Args:
            callback: Callback function to unregister
        """
        if hasattr(self, '_callbacks') and callback in self._callbacks:
            self._callbacks.remove(callback)
    
    async def _notify_subscribers(self, data_type: DataType, symbol: str, data: Any) -> None:
        """
        Notify all registered callbacks of new data.
        
        Args:
            data_type: Type of data
            symbol: Trading pair symbol
            data: Market data
        """
        if not hasattr(self, '_callbacks') or not self._callbacks:
            return
            
        for callback in list(self._callbacks):
            try:
                await self._execute_callback(callback, data_type, symbol, data)
            except Exception as e:
                logger.error(f"Error in data callback: {e}", exc_info=True)
                
    async def _execute_callback(self, callback: callable, *args, **kwargs):
        """Execute a callback, handling both sync and async functions."""
        if asyncio.iscoroutinefunction(callback):
            await callback(*args, **kwargs)
        else:
            # Run sync callbacks in a thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, callback, *args, **kwargs)
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize a trading pair symbol to the exchange's format.
        
        Args:
            symbol: Trading pair symbol in any format
            
        Returns:
            Normalized symbol
        """
        # Default implementation, can be overridden by subclasses
        return symbol.upper().replace('-', '/')
    
    @abstractmethod
    async def _init_websocket(self) -> BaseWebSocketClient:
        """Initialize and return a WebSocket client."""
        pass
        
    @abstractmethod
    async def _start_websocket(self) -> None:
        """Start the WebSocket connection."""
        pass
        
    @abstractmethod
    async def _subscribe_websocket(self, data_type: DataType, symbol: str, **kwargs) -> None:
        """Subscribe to WebSocket updates for a symbol."""
        pass
        
    @abstractmethod
    async def _unsubscribe_websocket(self, data_type: DataType, symbol: str) -> None:
        """Unsubscribe from WebSocket updates for a symbol."""
        pass
        
    @abstractmethod
    async def _fetch_historical_data(
        self,
        data_type: DataType,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Fetch historical data from the exchange's REST API."""
        pass
    
    @abstractmethod
    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information including supported symbols and limits."""
        pass
    
    @abstractmethod
    async def get_symbols(self) -> List[str]:
        """Get a list of all available trading pairs."""
        pass
    
    @abstractmethod
    async def get_server_time(self) -> Dict[str, Any]:
        """Get the current server time."""
        pass

class DataCollectorError(Exception):
    """Base exception for data collector errors."""
    pass

class DataValidationError(DataCollectorError):
    """Raised when data validation fails."""
    pass

class DataUnavailableError(DataCollectorError):
    """Raised when requested data is not available."""
    pass
