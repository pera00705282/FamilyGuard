"""Binance WebSocket client implementation.

This module provides WebSocket client for real-time market data and user updates
from Binance exchange.
"""
import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set
from decimal import Decimal

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed

from .base_websocket import BaseWebSocketClient
from .interfaces import TickerData, OrderBookData, TradeData, OrderInfo, OrderType, OrderSide

logger = logging.getLogger(__name__)


class BinanceWebSocketClient(BaseWebSocketClient):
    """WebSocket client for Binance API."""

    WS_URL = "wss://stream.binance.com:9443/ws"
    WS_TESTNET_URL = "wss://testnet.binance.vision/ws"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
        **kwargs
    ) -> None:
        """Initialize Binance WebSocket client.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Whether to use testnet
            **kwargs: Additional arguments for BaseWebSocketClient
        """
        self.ws_url = self.WS_TESTNET_URL if testnet else self.WS_URL
        self.api_key = api_key
        self.api_secret = api_secret
        self._ws = None
        self._subscriptions: Set[str] = set()
        self._listen_key = None
        self._keep_alive_task = None
        super().__init__(**kwargs)

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        if self._ws is not None and not self._ws.closed:
            return

        try:
            self._ws = await websockets.connect(self.ws_url, ping_interval=30, ping_timeout=10)
            logger.info("WebSocket connection established")
            
            # Start the message handler
            asyncio.create_task(self._message_handler())
            
            # Resubscribe to any existing subscriptions
            if self._subscriptions:
                await self._resubscribe()
                
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            raise

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            self._keep_alive_task = None
            
        if self._ws and not self._ws.closed:
            await self._ws.close()
            self._ws = None
            logger.info("WebSocket connection closed")

    async def _message_handler(self) -> None:
        """Handle incoming WebSocket messages."""
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse WebSocket message: {message}")
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
        except ConnectionClosed:
            logger.warning("WebSocket connection closed by server")
            await self._reconnect()
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            await self._reconnect()

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Process incoming WebSocket message."""
        if 'e' in data:  # Event type
            event_type = data['e']
            
            if event_type == 'depthUpdate':
                await self._handle_order_book_update(data)
            elif event_type == 'trade':
                await self._handle_trade_update(data)
            elif event_type == 'kline':
                await self._handle_kline_update(data)
            elif event_type == '24hrTicker':
                await self._handle_ticker_update(data)
            elif event_type == 'outboundAccountPosition':
                await self._handle_account_update(data)
            elif event_type == 'executionReport':
                await self._handle_order_update(data)
        
        # Handle aggregated trades
        elif 'e' in data and data['e'] == 'aggTrade':
            await self._handle_agg_trade(data)

    async def _handle_order_book_update(self, data: Dict[str, Any]) -> None:
        """Handle order book update."""
        symbol = data['s'].lower()
        order_book = OrderBookData(
            bids=[(Decimal(price), Decimal(qty)) for price, qty in data.get('b', [])],
            asks=[(Decimal(price), Decimal(qty)) for price, qty in data.get('a', [])],
            timestamp=data['E'] / 1000  # Convert to seconds
        )
        await self._notify('order_book', symbol, order_book)

    async def _handle_trade_update(self, data: Dict[str, Any]) -> None:
        """Handle trade update."""
        trade = TradeData(
            trade_id=str(data['t']),
            symbol=data['s'].lower(),
            price=Decimal(data['p']),
            quantity=Decimal(data['q']),
            side=OrderSide.BUY if data['m'] else OrderSide.SELL,
            timestamp=data['T'] / 1000  # Convert to seconds
        )
        await self._notify('trade', trade.symbol, trade)

    async def _handle_ticker_update(self, data: Dict[str, Any]) -> None:
        """Handle 24hr ticker update."""
        ticker = TickerData(
            symbol=data['s'].lower(),
            bid=Decimal(data['b']),
            ask=Decimal(data['a']),
            last=Decimal(data['c']),
            base_volume=Decimal(data['v']),
            quote_volume=Decimal(data['q']),
            timestamp=data['E'] / 1000  # Convert to seconds
        )
        await self._notify('ticker', ticker.symbol, ticker)

    async def _handle_order_update(self, data: Dict[str, Any]) -> None:
        """Handle order update."""
        order = OrderInfo(
            order_id=str(data['i']),
            symbol=data['s'].lower(),
            side=OrderSide.BUY if data['S'] == 'BUY' else OrderSide.SELL,
            order_type=OrderType[data['o'].upper()],
            price=Decimal(data['p']),
            quantity=Decimal(data['q']),
            filled_quantity=Decimal(data['z']),
            status=data['X'],
            time_in_force=data['f'],
            created_at=data['O'] / 1000,  # Convert to seconds
            updated_at=data['T'] / 1000   # Convert to seconds
        )
        await self._notify('order', order.symbol, order)

    async def subscribe_order_book(self, symbol: str) -> None:
        """Subscribe to order book updates for a symbol."""
        stream = f"{symbol.lower()}@depth"
        await self._subscribe(stream)

    async def subscribe_ticker(self, symbol: str) -> None:
        """Subscribe to ticker updates for a symbol."""
        stream = f"{symbol.lower()}@ticker"
        await self._subscribe(stream)

    async def subscribe_trades(self, symbol: str) -> None:
        """Subscribe to trade updates for a symbol."""
        stream = f"{symbol.lower()}@trade"
        await self._subscribe(stream)

    async def subscribe_user_data(self) -> None:
        """Subscribe to user data updates."""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret are required for user data subscription")
            
        # Get listen key
        async with aiohttp.ClientSession() as session:
            url = "https://api.binance.com/api/v3/userDataStream"
            if hasattr(self, 'testnet') and self.testnet:
                url = "https://testnet.binance.vision/api/v3/userDataStream"
                
            headers = {"X-MBX-APIKEY": self.api_key}
            async with session.post(url, headers=headers) as response:
                data = await response.json()
                self._listen_key = data['listenKey']
                
        # Start keep-alive task
        self._keep_alive_task = asyncio.create_task(self._keep_alive())
        
        # Subscribe to user data
        await self._subscribe(self._listen_key)

    async def _keep_alive(self) -> None:
        """Keep the user data stream alive."""
        while True:
            try:
                await asyncio.sleep(30 * 60)  # 30 minutes
                if not self._listen_key:
                    break
                    
                async with aiohttp.ClientSession() as session:
                    url = f"https://api.binance.com/api/v3/userDataStream?listenKey={self._listen_key}"
                    if hasattr(self, 'testnet') and self.testnet:
                        url = f"https://testnet.binance.vision/api/v3/userDataStream?listenKey={self._listen_key}"
                        
                    headers = {"X-MBX-APIKEY": self.api_key}
                    async with session.put(url, headers=headers):
                        pass
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error keeping stream alive: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _subscribe(self, stream: str) -> None:
        """Subscribe to a WebSocket stream."""
        if stream in self._subscriptions:
            return
            
        if self._ws is None or self._ws.closed:
            await self.connect()
            
        # For combined streams
        if isinstance(stream, list):
            stream = "/".join(stream)
            
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [stream],
            "id": int(time.time())
        }
        
        try:
            await self._ws.send(json.dumps(subscribe_msg))
            self._subscriptions.add(stream)
            logger.debug(f"Subscribed to {stream}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {stream}: {e}")
            raise

    async def _unsubscribe(self, stream: str) -> None:
        """Unsubscribe from a WebSocket stream."""
        if stream not in self._subscriptions:
            return
            
        if self._ws is None or self._ws.closed:
            return
            
        unsubscribe_msg = {
            "method": "UNSUBSCRIBE",
            "params": [stream],
            "id": int(time.time())
        }
        
        try:
            await self._ws.send(json.dumps(unsubscribe_msg))
            self._subscriptions.remove(stream)
            logger.debug(f"Unsubscribed from {stream}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {stream}: {e}")
            raise

    async def _resubscribe(self) -> None:
        """Resubscribe to all active subscriptions."""
        if not self._subscriptions:
            return
            
        if self._ws is None or self._ws.closed:
            await self.connect()
            
        for stream in list(self._subscriptions):
            await self._subscribe(stream)

    async def _reconnect(self) -> None:
        """Reconnect to the WebSocket server."""
        logger.info("Attempting to reconnect...")
        await self.disconnect()
        await asyncio.sleep(1)  # Wait before reconnecting
        await self.connect()
