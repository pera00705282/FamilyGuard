"""
Bitfinex exchange data collector.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode

import aiohttp
import pandas as pd

from ..base_collector import DataCollector, DataType, Timeframe
from ...exchanges.bitfinex_websocket import BitfinexWebSocketClient
from ...config import config
from ...monitoring.metrics import metrics

logger = logging.getLogger(__name__)

class BitfinexCollector(DataCollector):
    """Bitfinex exchange data collector."""
    
    BASE_API_URL = "https://api.bitfinex.com/v2"
    BASE_WS_URL = "wss://api-pub.bitfinex.com/ws/2"
    
    def __init__(self, api_key: str = "", api_secret: str = ""):
        """
        Initialize the Bitfinex collector.
        
        Args:
            api_key: Bitfinex API key
            api_secret: Bitfinex API secret
        """
        super().__init__("bitfinex")
        self.api_key = api_key or config.exchanges.get("bitfinex", {}).get("api_key", "")
        self.api_secret = api_secret or config.exchanges.get("bitfinex", {}).get("api_secret", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = 0
        self._rate_limit_remaining = 90  # Default rate limit (per minute)
        self._rate_limit_reset = 60  # Reset time in seconds
        self._channel_map: Dict[int, Dict[str, Any]] = {}
    
    async def _init_websocket(self) -> BitfinexWebSocketClient:
        """Initialize and return a WebSocket client."""
        ws = BitfinexWebSocketClient(
            self.BASE_WS_URL,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        
        # Register message handlers
        ws.register_callback(self._handle_ws_message)
        
        return ws
    
    async def _start_websocket(self) -> None:
        """Start the WebSocket connection."""
        if not self._websocket:
            self._websocket = await self._init_websocket()
            
        if not self._websocket.connected:
            await self._websocket.connect()
            
            # Resubscribe to any existing subscriptions
            for subscription in list(self._subscribers):
                _, data_type, symbol = subscription.split(':', 2)
                await self._subscribe_websocket(DataType(data_type), symbol)
    
    async def _subscribe_websocket(self, data_type: DataType, symbol: str, **kwargs) -> None:
        """Subscribe to WebSocket updates for a symbol."""
        if not self._websocket or not self._websocket.connected:
            return
            
        channel_name = self._get_channel_name(data_type, symbol, **kwargs)
        if channel_name:
            # Store subscription info to map channel IDs back to symbols and data types
            channel_id = await self._websocket.subscribe(channel_name, symbol)
            if channel_id:
                self._channel_map[channel_id] = {
                    'data_type': data_type,
                    'symbol': symbol,
                    'channel': channel_name
                }
    
    async def _unsubscribe_websocket(self, data_type: DataType, symbol: str) -> None:
        """Unsubscribe from WebSocket updates for a symbol."""
        if not self._websocket or not self._websocket.connected:
            return
            
        # Find the channel ID for this symbol and data type
        channel_id = None
        for cid, info in self._channel_map.items():
            if info['data_type'] == data_type and info['symbol'] == symbol:
                channel_id = cid
                break
                
        if channel_id is not None:
            await self._websocket.unsubscribe(channel_id)
            if channel_id in self._channel_map:
                del self._channel_map[channel_id]
    
    def _get_channel_name(self, data_type: DataType, symbol: str, **kwargs) -> Optional[str]:
        """Get the WebSocket channel name for the given data type and symbol."""
        # Convert symbol to Bitfinex format (e.g., 'BTC/USDT' -> 'tBTCUSD')
        bfx_symbol = self._convert_symbol(symbol)
        
        if data_type == DataType.TRADES:
            return f"trades:{bfx_symbol}"
        elif data_type == DataType.ORDER_BOOK:
            precision = kwargs.get('precision', 'P0')  # P0, P1, P2, P3, P4, R0
            freq = kwargs.get('freq', 'F0')  # F0, F1
            length = kwargs.get('length', 25)  # 1, 25, 100
            return f"book:{bfx_symbol}:{precision}:{freq}:{length}"
        elif data_type == DataType.OHLCV:
            timeframe = self._convert_timeframe(kwargs.get('timeframe', '1m'))
            return f"candles:{timeframe}:{bfx_symbol}"
        elif data_type == DataType.TICKER:
            return f"ticker:{bfx_symbol}"
        
        return None
    
    async def _handle_ws_message(self, message: Union[List, Dict]) -> None:
        """Handle incoming WebSocket messages."""
        try:
            # Heartbeat message
            if message == {"event": "pong"}:
                return
                
            # Subscription confirmation
            if isinstance(message, dict) and message.get('event') == 'subscribed':
                self._handle_subscription_confirmation(message)
                return
                
            # Data message
            if isinstance(message, list) and len(message) >= 2:
                channel_id = message[0]
                data = message[1:]
                
                # Look up channel info
                channel_info = self._channel_map.get(channel_id)
                if not channel_info:
                    return
                    
                data_type = channel_info['data_type']
                symbol = channel_info['symbol']
                
                # Process based on data type
                if data_type == DataType.TRADES:
                    await self._process_trades(symbol, data)
                elif data_type == DataType.ORDER_BOOK:
                    await self._process_order_book(symbol, data, channel_info.get('snapshot', False))
                    channel_info['snapshot'] = False  # Reset snapshot flag after first update
                elif data_type == DataType.OHLCV:
                    await self._process_candles(symbol, data)
                elif data_type == DataType.TICKER:
                    await self._process_ticker(symbol, data)
                    
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
    
    def _handle_subscription_confirmation(self, message: Dict) -> None:
        """Handle subscription confirmation message."""
        channel_id = message.get('chanId')
        channel_name = message.get('channel')
        symbol = message.get('symbol', '').replace('t', '').replace('f', '')
        
        # Map the channel ID back to our internal tracking
        if channel_id is not None:
            # Find the matching subscription
            for sub_key, info in self._channel_map.items():
                if isinstance(sub_key, str) and info.get('channel') == channel_name:
                    # Update with the actual channel ID
                    self._channel_map[channel_id] = info
                    if channel_id != sub_key:
                        del self._channel_map[sub_key]
                    
                    # Mark that we're expecting a snapshot for order books
                    if channel_name.startswith('book'):
                        info['snapshot'] = True
                    break
    
    async def _process_trades(self, symbol: str, data: List) -> None:
        """Process trade data."""
        # Format: [ID, TIMESTAMP, AMOUNT, PRICE]
        if not isinstance(data[0], list):
            data = [data]  # Single trade update
            
        trades = []
        for trade in data:
            if len(trade) < 4:
                continue
                
            trades.append({
                'exchange': 'bitfinex',
                'symbol': symbol,
                'trade_id': str(trade[0]),
                'timestamp': datetime.fromtimestamp(trade[1] / 1000),
                'amount': float(trade[2]),
                'price': float(trade[3]),
                'side': 'buy' if trade[2] > 0 else 'sell'
            })
        
        # Notify subscribers for each trade
        for trade in trades:
            await self._notify_subscribers(DataType.TRADES, symbol, trade)
    
    async def _process_order_book(self, symbol: str, data: List, is_snapshot: bool = False) -> None:
        """Process order book data."""
        order_book = {
            'exchange': 'bitfinex',
            'symbol': symbol,
            'timestamp': datetime.utcnow(),
            'bids': [],
            'asks': []
        }
        
        if is_snapshot:
            # Full snapshot: [[PRICE, COUNT, AMOUNT], ...]
            for item in data:
                if len(item) < 3:
                    continue
                    
                price = float(item[0])
                count = int(item[1])
                amount = float(item[2])
                
                if count > 0:  # Only include active orders
                    if amount > 0:
                        order_book['bids'].append([price, abs(amount)])
                    else:
                        order_book['asks'].append([price, abs(amount)])
        else:
            # Update: [PRICE, COUNT, AMOUNT] or [PRICE, 0, AMOUNT] for removal
            if len(data) >= 3:
                price = float(data[0])
                count = int(data[1])
                amount = float(data[2])
                
                # Determine if it's a bid or ask
                is_bid = amount > 0
                
                # Remove the price level if count is 0
                if count == 0:
                    if is_bid:
                        order_book['bids'] = [b for b in order_book['bids'] if b[0] != price]
                    else:
                        order_book['asks'] = [a for a in order_book['asks'] if a[0] != price]
                else:
                    # Add or update the price level
                    level = [price, abs(amount)]
                    if is_bid:
                        # Insert in descending order
                        inserted = False
                        for i, bid in enumerate(order_book['bids']):
                            if bid[0] == price:
                                order_book['bids'][i] = level
                                inserted = True
                                break
                            elif bid[0] < price:
                                order_book['bids'].insert(i, level)
                                inserted = True
                                break
                        if not inserted:
                            order_book['bids'].append(level)
                    else:
                        # Insert in ascending order
                        inserted = False
                        for i, ask in enumerate(order_book['asks']):
                            if ask[0] == price:
                                order_book['asks'][i] = level
                                inserted = True
                                break
                            elif ask[0] > price:
                                order_book['asks'].insert(i, level)
                                inserted = True
                                break
                        if not inserted:
                            order_book['asks'].append(level)
        
        # Sort bids (descending) and asks (ascending)
        order_book['bids'].sort(reverse=True, key=lambda x: x[0])
        order_book['asks'].sort(key=lambda x: x[0])
        
        # Notify subscribers
        await self._notify_subscribers(DataType.ORDER_BOOK, symbol, order_book)
    
    async def _process_candles(self, symbol: str, data: List) -> None:
        """Process candle/OHLCV data."""
        # Format: [TIMESTAMP, OPEN, CLOSE, HIGH, LOW, VOLUME]
        if not isinstance(data[0], list):
            data = [data]  # Single candle update
            
        for candle in data:
            if len(candle) < 6:
                continue
                
            ohlcv = {
                'exchange': 'bitfinex',
                'symbol': symbol,
                'timestamp': datetime.fromtimestamp(candle[0] / 1000),
                'open': float(candle[1]),
                'close': float(candle[2]),
                'high': float(candle[3]),
                'low': float(candle[4]),
                'volume': float(candle[5])
            }
            
            # Notify subscribers
            await self._notify_subscribers(DataType.OHLCV, symbol, ohlcv)
    
    async def _process_ticker(self, symbol: str, data: List) -> None:
        """Process ticker data."""
        # Format: [BID, BID_SIZE, ASK, ASK_SIZE, DAILY_CHANGE, DAILY_CHANGE_RELATIVE, 
        #          LAST_PRICE, VOLUME, HIGH, LOW]
        if len(data) < 10:
            return
            
        ticker = {
            'exchange': 'bitfinex',
            'symbol': symbol,
            'timestamp': datetime.utcnow(),
            'bid_price': float(data[0]),
            'bid_size': float(data[1]),
            'ask_price': float(data[2]),
            'ask_size': float(data[3]),
            'daily_change': float(data[4]),
            'daily_change_percent': float(data[5]) * 100,  # Convert to percentage
            'last_price': float(data[6]),
            'volume': float(data[7]),
            'high': float(data[8]),
            'low': float(data[9])
        }
        
        # Notify subscribers
        await self._notify_subscribers(DataType.TICKER, symbol, ticker)
    
    async def _fetch_historical_data(
        self,
        data_type: DataType,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Fetch historical data from the exchange's REST API."""
        # Convert symbol to Bitfinex format
        bfx_symbol = self._convert_symbol(symbol)
        
        if data_type == DataType.TRADES:
            return await self._fetch_historical_trades(bfx_symbol, start_time, end_time, limit)
        elif data_type == DataType.OHLCV:
            timeframe = kwargs.get('timeframe', '1m')
            return await self._fetch_historical_candles(bfx_symbol, timeframe, start_time, end_time, limit)
        elif data_type == DataType.ORDER_BOOK:
            precision = kwargs.get('precision', 'P0')
            return [await self._fetch_order_book(bfx_symbol, precision)]
        elif data_type == DataType.TICKER:
            return [await self._fetch_ticker(bfx_symbol)]
        else:
            raise ValueError(f"Unsupported data type for historical data: {data_type}")
    
    async def _fetch_historical_trades(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch historical trades."""
        endpoint = f"/trades/{symbol}/hist"
        
        params = {
            'limit': min(limit, 10000)  # Bitfinex max limit is 10000
        }
        
        if start_time:
            params['start'] = start_time
        if end_time:
            params['end'] = end_time
        
        data = await self._request('GET', endpoint, params=params)
        
        trades = []
        for trade in data:
            # Format: [ID, TIMESTAMP, AMOUNT, PRICE]
            trades.append({
                'exchange': 'bitfinex',
                'symbol': symbol.replace('t', '').replace('f', ''),
                'trade_id': str(trade[0]),
                'timestamp': datetime.fromtimestamp(trade[1] / 1000),
                'amount': float(trade[2]),
                'price': float(trade[3]),
                'side': 'buy' if trade[2] > 0 else 'sell'
            })
        
        return trades
    
    async def _fetch_historical_candles(
        self,
        symbol: str,
        timeframe: str = '1m',
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch historical OHLCV candles."""
        # Convert timeframe to Bitfinex format
        tf = self._convert_timeframe(timeframe)
        
        endpoint = f"/candles/trade:{tf}:{symbol}/hist"
        
        params = {
            'limit': min(limit, 10000)  # Bitfinex max limit is 10000
        }
        
        if start_time:
            params['start'] = start_time
        if end_time:
            params['end'] = end_time
        
        data = await self._request('GET', endpoint, params=params)
        
        candles = []
        for candle in data:
            # Format: [TIMESTAMP, OPEN, CLOSE, HIGH, LOW, VOLUME]
            candles.append({
                'exchange': 'bitfinex',
                'symbol': symbol.replace('t', '').replace('f', ''),
                'timestamp': datetime.fromtimestamp(candle[0] / 1000),
                'open': float(candle[1]),
                'close': float(candle[2]),
                'high': float(candle[3]),
                'low': float(candle[4]),
                'volume': float(candle[5])
            })
        
        return candles
    
    async def _fetch_order_book(self, symbol: str, precision: str = 'P0') -> Dict[str, Any]:
        """Fetch order book."""
        endpoint = f"/book/{symbol}/{precision}"
        
        data = await self._request('GET', endpoint)
        
        order_book = {
            'exchange': 'bitfinex',
            'symbol': symbol.replace('t', '').replace('f', ''),
            'timestamp': datetime.utcnow(),
            'bids': [],
            'asks': []
        }
        
        for item in data:
            # Format: [PRICE, COUNT, AMOUNT] or [PRICE, R0, COUNT, AMOUNT] for R0 precision
            if len(item) >= 3:
                if precision == 'R0':
                    price = float(item[0])
                    count = int(item[2])
                    amount = float(item[3])
                else:
                    price = float(item[0])
                    count = int(item[1])
                    amount = float(item[2])
                
                if count > 0:  # Only include active orders
                    if amount > 0:
                        order_book['bids'].append([price, amount])
                    else:
                        order_book['asks'].append([price, abs(amount)])
        
        # Sort bids (descending) and asks (ascending)
        order_book['bids'].sort(reverse=True, key=lambda x: x[0])
        order_book['asks'].sort(key=lambda x: x[0])
        
        return order_book
    
    async def _fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch ticker."""
        endpoint = f"/ticker/{symbol}"
        
        data = await self._request('GET', endpoint)
        
        # Format: [BID, BID_SIZE, ASK, ASK_SIZE, DAILY_CHANGE, DAILY_CHANGE_RELATIVE, 
        #          LAST_PRICE, VOLUME, HIGH, LOW]
        return {
            'exchange': 'bitfinex',
            'symbol': symbol.replace('t', '').replace('f', ''),
            'timestamp': datetime.utcnow(),
            'bid_price': float(data[0]),
            'bid_size': float(data[1]),
            'ask_price': float(data[2]),
            'ask_size': float(data[3]),
            'daily_change': float(data[4]),
            'daily_change_percent': float(data[5]) * 100,  # Convert to percentage
            'last_price': float(data[6]),
            'volume': float(data[7]),
            'high': float(data[8]),
            'low': float(data[9])
        }
    
    def _convert_symbol(self, symbol: str) -> str:
        """Convert standard symbol format to Bitfinex format."""
        # Example: 'BTC/USDT' -> 'tBTCUST' or 'tBTCUSD' if USDT not supported
        if '/' in symbol:
            base, quote = symbol.split('/')
            return f"t{base}{quote}"
        # If already in Bitfinex format (tBTCUSD, fUSD, etc.)
        elif symbol.startswith(('t', 'f')):
            return symbol
        # Assume it's a pair without separator (e.g., 'BTCUSD')
        else:
            return f"t{symbol}"
    
    def _convert_timeframe(self, timeframe: str) -> str:
        """Convert standard timeframe to Bitfinex format."""
        # Convert from standard format (e.g., '1m', '1h', '1d') to Bitfinex format
        timeframe_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '3h': '3h',
            '6h': '6h',
            '12h': '12h',
            '1d': '1D',
            '1w': '7D',
            '14d': '14D',
            '1M': '1M'
        }
        
        return timeframe_map.get(timeframe, timeframe)  # Return as-is if not in the map
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information including supported symbols and limits."""
        # Get platform status
        status = await self._request('GET', '/platform/status')
        
        # Get symbols
        symbols = await self._request('GET', '/conf/pub:list:pair:exchange')
        
        # Get symbols details
        symbols_details = await self._request('GET', '/conf/pub:info:pair')
        
        return {
            'status': status[0],
            'symbols': symbols[0],
            'symbols_details': symbols_details[0]
        }
    
    async def get_symbols(self) -> List[str]:
        """Get a list of all available trading pairs."""
        try:
            info = await self.get_exchange_info()
            return info.get('symbols', [])
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            return []
    
    async def get_server_time(self) -> Dict[str, Any]:
        """Get the current server time."""
        # Bitfinex doesn't have a dedicated time endpoint, so we'll use the platform status
        status = await self._request('GET', '/platform/status')
        return {
            'server_time': int(time.time() * 1000),  # Current time in ms
            'platform_status': status[0] if status else None
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> Any:
        """Make an HTTP request to the Bitfinex API."""
        # Ensure we're not exceeding rate limits
        await self._check_rate_limit()
        
        # Create session if it doesn't exist
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
        # Add API key to headers if needed
        headers = {}
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API key and secret are required for signed requests")
                
            # Create authentication headers
            nonce = str(int(time.time() * 1000))
            signature = self._generate_signature(nonce)
            
            headers.update({
                'bfx-nonce': nonce,
                'bfx-apikey': self.api_key,
                'bfx-signature': signature
            })
        
        # Make the request
        url = f"{self.BASE_API_URL}{endpoint}"
        
        try:
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers,
                timeout=30
            ) as response:
                # Update rate limit info from headers
                self._update_rate_limit_headers(response.headers)
                
                # Check for errors
                if response.status != 200:
                    error_data = await response.text()
                    raise Exception(f"API error {response.status}: {error_data}")
                
                return await response.json()
                
        except asyncio.TimeoutError:
            raise Exception("Request to Bitfinex API timed out")
        except Exception as e:
            logger.error(f"Error making request to Bitfinex API: {e}")
            raise
    
    def _generate_signature(self, nonce: str) -> str:
        """Generate signature for authenticated requests."""
        message = f"{nonce}{self.api_key}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            msg=message.encode('utf-8'),
            digestmod=hashlib.sha384
        ).hexdigest()
        
        return signature
    
    def _update_rate_limit_headers(self, headers: Dict[str, str]) -> None:
        """Update rate limit information from response headers."""
        if 'x-ratelimit-remaining' in headers:
            self._rate_limit_remaining = int(headers.get('x-ratelimit-remaining', 0))
        if 'x-ratelimit-reset' in headers:
            self._rate_limit_reset = int(headers.get('x-ratelimit-reset', 60))
    
    async def _check_rate_limit(self) -> None:
        """Check if we're approaching rate limits and sleep if needed."""
        min_remaining = 10  # Start slowing down when we have 10 requests left
        
        if self._rate_limit_remaining < min_remaining:
            sleep_time = self._rate_limit_reset + 1  # Add 1 second buffer
            logger.warning(f"Approaching rate limit. Sleeping for {sleep_time} seconds...")
            await asyncio.sleep(sleep_time)
            
            # Reset rate limit counter after sleeping
            self._rate_limit_remaining = 90  # Default rate limit
    
    async def close(self) -> None:
        """Close the collector and release resources."""
        await super().close()
        
        # Close the HTTP session
        if self._session:
            await self._session.close()
            self._session = None

# Factory function
def create_bitfinex_collector(api_key: str = "", api_secret: str = "") -> BitfinexCollector:
    """Create a new Bitfinex collector instance."""
    return BitfinexCollector(api_key=api_key, api_secret=api_secret)
