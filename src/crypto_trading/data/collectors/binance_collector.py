"""
Binance exchange data collector.
"""
import asyncio
import logging
import time
import hmac
import hashlib
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from urllib.parse import urlencode

import aiohttp
import pandas as pd

from ..base_collector import DataCollector, DataType, Timeframe
from ...exchanges.binance_websocket import BinanceWebSocketClient
from ...config import config
from ...monitoring.metrics import metrics

logger = logging.getLogger(__name__)

class BinanceCollector(DataCollector):
    """Binance exchange data collector."""
    
    BASE_API_URL = "https://api.binance.com"
    TESTNET_API_URL = "https://testnet.binance.vision"
    FUTURES_API_URL = "https://fapi.binance.com"
    FUTURES_TESTNET_API_URL = "https://testnet.binancefuture.com"
    
    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = False, futures: bool = False):
        """
        Initialize the Binance collector.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Whether to use the testnet
            futures: Whether to use the futures API
        """
        super().__init__("binance")
        self.api_key = api_key or config.exchanges.get("binance", {}).get("api_key", "")
        self.api_secret = api_secret or config.exchanges.get("binance", {}).get("api_secret", "")
        self.testnet = testnet
        self.futures = futures
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = 0
        self._rate_limit_remaining = 1200  # Default rate limit
        self._rate_limit_reset = 60  # Default reset time in seconds
        
        # Configure base URLs based on testnet and futures flags
        if self.futures:
            self.base_url = self.FUTURES_TESTNET_API_URL if self.testnet else self.FUTURES_API_URL
            self.ws_url = "wss://fstream.binance.com/ws" if not self.testnet else "wss://stream.binancefuture.com/ws"
        else:
            self.base_url = self.TESTNET_API_URL if self.testnet else self.BASE_API_URL
            self.ws_url = "wss://stream.binance.com:9443/ws" if not self.testnet else "wss://testnet.binance.vision/ws"
    
    async def _init_websocket(self) -> BinanceWebSocketClient:
        """Initialize and return a WebSocket client."""
        ws = BinanceWebSocketClient(
            self.ws_url,
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.testnet,
            futures=self.futures
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
            
        stream_name = self._get_stream_name(data_type, symbol, **kwargs)
        if stream_name:
            await self._websocket.subscribe([stream_name])
    
    async def _unsubscribe_websocket(self, data_type: DataType, symbol: str) -> None:
        """Unsubscribe from WebSocket updates for a symbol."""
        if not self._websocket or not self._websocket.connected:
            return
            
        stream_name = self._get_stream_name(data_type, symbol)
        if stream_name:
            await self._websocket.unsubscribe([stream_name])
    
    def _get_stream_name(self, data_type: DataType, symbol: str, **kwargs) -> Optional[str]:
        """Get the WebSocket stream name for the given data type and symbol."""
        symbol = symbol.replace('/', '').lower()
        
        if data_type == DataType.TRADES:
            return f"{symbol}@trade"
        elif data_type == DataType.ORDER_BOOK:
            depth = kwargs.get('depth', 20)  # Default depth is 20
            return f"{symbol}@depth{depth}@100ms"
        elif data_type == DataType.OHLCV:
            interval = kwargs.get('interval', '1m')
            return f"{symbol}@kline_{interval}"
        elif data_type == DataType.TICKER:
            return f"{symbol}@ticker"
        elif data_type == DataType.FUNDING_RATE and self.futures:
            return f"{symbol}@markPrice@1s"
        
        return None
    
    async def _handle_ws_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming WebSocket messages."""
        try:
            stream = message.get('stream', '')
            data = message.get('data', {})
            
            if not stream or not data:
                return
                
            # Extract data type and symbol from stream name
            parts = stream.split('@')
            if len(parts) < 2:
                return
                
            symbol = parts[0].upper()
            if len(symbol) > 0:
                # Add a slash for proper symbol formatting (e.g., 'BTCUSDT' -> 'BTC/USDT')
                if len(symbol) > 3 and not symbol.endswith(('USDT', 'BUSD', 'USDC', 'BTC', 'ETH')):
                    # Try to split symbol into base and quote
                    for quote in ['USDT', 'BUSD', 'USDC', 'BTC', 'ETH']:
                        if symbol.endswith(quote):
                            base = symbol[:-len(quote)]
                            symbol = f"{base}/{quote}"
                            break
            
            # Determine data type and process accordingly
            if 'trade' in stream:
                await self._process_trade(symbol, data)
            elif 'depth' in stream:
                await self._process_order_book(symbol, data)
            elif 'kline' in stream:
                await self._process_ohlcv(symbol, data)
            elif 'ticker' in stream:
                await self._process_ticker(symbol, data)
            elif 'markPrice' in stream and self.futures:
                await self._process_funding_rate(symbol, data)
                
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
    
    async def _process_trade(self, symbol: str, data: Dict[str, Any]) -> None:
        """Process trade data."""
        trade = {
            'exchange': 'binance',
            'symbol': symbol,
            'trade_id': str(data.get('t')),
            'price': float(data.get('p', 0)),
            'quantity': float(data.get('q', 0)),
            'timestamp': datetime.fromtimestamp(data.get('T', 0) / 1000),
            'is_buyer_maker': data.get('m', False),
            'is_best_match': data.get('M', False)
        }
        
        # Notify subscribers
        await self._notify_subscribers(DataType.TRADES, symbol, trade)
    
    async def _process_order_book(self, symbol: str, data: Dict[str, Any]) -> None:
        """Process order book data."""
        order_book = {
            'exchange': 'binance',
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(data.get('E', 0) / 1000),
            'bids': [[float(price), float(qty)] for price, qty in data.get('bids', [])],
            'asks': [[float(price), float(qty)] for price, qty in data.get('asks', [])]
        }
        
        # Notify subscribers
        await self._notify_subscribers(DataType.ORDER_BOOK, symbol, order_book)
    
    async def _process_ohlcv(self, symbol: str, data: Dict[str, Any]) -> None:
        """Process OHLCV data."""
        kline = data.get('k', {})
        
        ohlcv = {
            'exchange': 'binance',
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(kline.get('t', 0) / 1000),
            'open': float(kline.get('o', 0)),
            'high': float(kline.get('h', 0)),
            'low': float(kline.get('l', 0)),
            'close': float(kline.get('c', 0)),
            'volume': float(kline.get('v', 0)),
            'quote_volume': float(kline.get('q', 0)),
            'trades': kline.get('n', 0),
            'is_closed': kline.get('x', False)
        }
        
        # Notify subscribers
        await self._notify_subscribers(DataType.OHLCV, symbol, ohlcv)
    
    async def _process_ticker(self, symbol: str, data: Dict[str, Any]) -> None:
        """Process ticker data."""
        ticker = {
            'exchange': 'binance',
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(data.get('E', 0) / 1000),
            'price_change': float(data.get('p', 0)),
            'price_change_percent': float(data.get('P', 0)),
            'weighted_avg_price': float(data.get('w', 0)),
            'prev_close_price': float(data.get('x', 0)),
            'last_price': float(data.get('c', 0)),
            'last_qty': float(data.get('Q', 0)),
            'bid_price': float(data.get('b', 0)),
            'bid_qty': float(data.get('B', 0)),
            'ask_price': float(data.get('a', 0)),
            'ask_qty': float(data.get('A', 0)),
            'open_price': float(data.get('o', 0)),
            'high_price': float(data.get('h', 0)),
            'low_price': float(data.get('l', 0)),
            'volume': float(data.get('v', 0)),
            'quote_volume': float(data.get('q', 0)),
            'open_time': datetime.fromtimestamp(data.get('O', 0) / 1000),
            'close_time': datetime.fromtimestamp(data.get('C', 0) / 1000),
            'first_trade_id': data.get('F', 0),
            'last_trade_id': data.get('L', 0),
            'trade_count': data.get('n', 0)
        }
        
        # Notify subscribers
        await self._notify_subscribers(DataType.TICKER, symbol, ticker)
    
    async def _process_funding_rate(self, symbol: str, data: Dict[str, Any]) -> None:
        """Process funding rate data (futures only)."""
        if not self.futures:
            return
            
        funding_rate = {
            'exchange': 'binance',
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(data.get('E', 0) / 1000),
            'mark_price': float(data.get('p', 0)),
            'index_price': float(data.get('i', 0)),
            'estimated_settlement_price': float(data.get('P', 0)),
            'funding_rate': float(data.get('r', 0)),
            'next_funding_time': datetime.fromtimestamp(data.get('T', 0) / 1000)
        }
        
        # Notify subscribers
        await self._notify_subscribers(DataType.FUNDING_RATE, symbol, funding_rate)
    
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
        symbol = symbol.replace('/', '').upper()
        
        if data_type == DataType.TRADES:
            return await self._fetch_historical_trades(symbol, start_time, end_time, limit)
        elif data_type == DataType.OHLCV:
            interval = kwargs.get('interval', '1m')
            return await self._fetch_historical_klines(symbol, interval, start_time, end_time, limit)
        elif data_type == DataType.ORDER_BOOK:
            depth = kwargs.get('depth', 20)
            return [await self._fetch_order_book(symbol, depth)]
        elif data_type == DataType.TICKER:
            return [await self._fetch_ticker(symbol)]
        elif data_type == DataType.FUNDING_RATE and self.futures:
            return await self._fetch_funding_rate_history(symbol, start_time, end_time, limit)
        else:
            raise ValueError(f"Unsupported data type for historical data: {data_type}")
    
    async def _fetch_historical_trades(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch historical trades."""
        endpoint = "/fapi/v1/aggTrades" if self.futures else "/api/v3/aggTrades"
        params = {
            'symbol': symbol,
            'limit': min(limit, 1000)  # Binance max limit is 1000
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        data = await self._request('GET', endpoint, params=params)
        
        trades = []
        for trade in data:
            trades.append({
                'exchange': 'binance',
                'symbol': symbol,
                'trade_id': str(trade['a']),
                'price': float(trade['p']),
                'quantity': float(trade['q']),
                'timestamp': datetime.fromtimestamp(trade['T'] / 1000),
                'is_buyer_maker': trade['m'],
                'is_best_match': trade['M']
            })
        
        return trades
    
    async def _fetch_historical_klines(
        self,
        symbol: str,
        interval: str = '1m',
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch historical klines/candlestick data."""
        endpoint = "/fapi/v1/klines" if self.futures else "/api/v3/klines"
        
        # Convert interval to Binance format if needed
        interval = self._convert_interval(interval)
        
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': min(limit, 1000)  # Binance max limit is 1000
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        data = await self._request('GET', endpoint, params=params)
        
        klines = []
        for k in data:
            klines.append({
                'exchange': 'binance',
                'symbol': symbol,
                'timestamp': datetime.fromtimestamp(k[0] / 1000),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5]),
                'close_time': datetime.fromtimestamp(k[6] / 1000),
                'quote_asset_volume': float(k[7]),
                'number_of_trades': k[8],
                'taker_buy_base_asset_volume': float(k[9]),
                'taker_buy_quote_asset_volume': float(k[10])
            })
        
        return klines
    
    async def _fetch_order_book(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """Fetch order book."""
        endpoint = "/fapi/v1/depth" if self.futures else "/api/v3/depth"
        
        params = {
            'symbol': symbol,
            'limit': min(depth, 5000)  # Binance max limit is 5000
        }
        
        data = await self._request('GET', endpoint, params=params)
        
        return {
            'exchange': 'binance',
            'symbol': symbol,
            'timestamp': datetime.now(),
            'bids': [[float(price), float(qty)] for price, qty in data.get('bids', [])],
            'asks': [[float(price), float(qty)] for price, qty in data.get('asks', [])]
        }
    
    async def _fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch 24hr ticker."""
        endpoint = "/fapi/v1/ticker/24hr" if self.futures else "/api/v3/ticker/24hr"
        
        params = {'symbol': symbol}
        data = await self._request('GET', endpoint, params=params)
        
        return {
            'exchange': 'binance',
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(data.get('closeTime', 0) / 1000),
            'price_change': float(data.get('priceChange', 0)),
            'price_change_percent': float(data.get('priceChangePercent', 0)),
            'weighted_avg_price': float(data.get('weightedAvgPrice', 0)),
            'prev_close_price': float(data.get('prevClosePrice', 0)),
            'last_price': float(data.get('lastPrice', 0)),
            'last_qty': float(data.get('lastQty', 0)),
            'bid_price': float(data.get('bidPrice', 0)),
            'bid_qty': float(data.get('bidQty', 0)),
            'ask_price': float(data.get('askPrice', 0)),
            'ask_qty': float(data.get('askQty', 0)),
            'open_price': float(data.get('openPrice', 0)),
            'high_price': float(data.get('highPrice', 0)),
            'low_price': float(data.get('lowPrice', 0)),
            'volume': float(data.get('volume', 0)),
            'quote_volume': float(data.get('quoteVolume', 0)),
            'open_time': datetime.fromtimestamp(data.get('openTime', 0) / 1000),
            'close_time': datetime.fromtimestamp(data.get('closeTime', 0) / 1000),
            'first_trade_id': data.get('firstId', 0),
            'last_trade_id': data.get('lastId', 0),
            'trade_count': data.get('count', 0)
        }
    
    async def _fetch_funding_rate_history(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch funding rate history (futures only)."""
        if not self.futures:
            return []
            
        endpoint = "/fapi/v1/fundingRate"
        
        params = {
            'symbol': symbol,
            'limit': min(limit, 1000)  # Binance max limit is 1000
        }
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        data = await self._request('GET', endpoint, params=params)
        
        rates = []
        for rate in data:
            rates.append({
                'exchange': 'binance',
                'symbol': symbol,
                'funding_rate': float(rate['fundingRate']),
                'funding_time': datetime.fromtimestamp(rate['fundingTime'] / 1000),
                'mark_price': float(rate.get('markPrice', 0))
            })
        
        return rates
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information including supported symbols and limits."""
        endpoint = "/fapi/v1/exchangeInfo" if self.futures else "/api/v3/exchangeInfo"
        return await self._request('GET', endpoint)
    
    async def get_symbols(self) -> List[str]:
        """Get a list of all available trading pairs."""
        info = await self.get_exchange_info()
        return [s['symbol'] for s in info.get('symbols', [])]
    
    async def get_server_time(self) -> Dict[str, Any]:
        """Get the current server time."""
        endpoint = "/fapi/v1/time" if self.futures else "/api/v3/time"
        return await self._request('GET', endpoint)
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> Any:
        """Make an HTTP request to the Binance API."""
        # Ensure we're not exceeding rate limits
        await self._check_rate_limit()
        
        # Create session if it doesn't exist
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
        # Add API key to headers if needed
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        # Add signature if this is a signed request
        if signed:
            if not self.api_secret:
                raise ValueError("API secret is required for signed requests")
                
            # Add timestamp to parameters
            if params is None:
                params = {}
                
            params['timestamp'] = int(time.time() * 1000)
            
            # Create signature
            query_string = urlencode(params)
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            params['signature'] = signature
        
        # Make the request
        url = f"{self.base_url}{endpoint}"
        
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
                    error_data = await response.json()
                    raise Exception(f"API error {response.status}: {error_data.get('msg', 'Unknown error')}")
                
                return await response.json()
                
        except asyncio.TimeoutError:
            raise Exception("Request to Binance API timed out")
        except Exception as e:
            logger.error(f"Error making request to Binance API: {e}")
            raise
    
    def _update_rate_limit_headers(self, headers: Dict[str, str]) -> None:
        """Update rate limit information from response headers."""
        if 'X-MBX-USED-WEIGHT-1M' in headers:
            self._rate_limit_remaining = int(headers.get('X-MBX-USED-WEIGHT-1M', 0))
        if 'X-MBX-ORDER-COUNT-1M' in headers:
            self._rate_limit_remaining = min(
                self._rate_limit_remaining,
                int(headers.get('X-MBX-ORDER-COUNT-1M', 0))
            )
    
    async def _check_rate_limit(self) -> None:
        """Check if we're approaching rate limits and sleep if needed."""
        # Simple rate limiting - adjust based on your needs
        min_remaining = 50  # Start slowing down when we have 50 requests left
        
        if self._rate_limit_remaining < min_remaining:
            sleep_time = (60 - (time.time() % 60)) + 1  # Sleep until the next minute
            logger.warning(f"Approaching rate limit. Sleeping for {sleep_time:.1f} seconds...")
            await asyncio.sleep(sleep_time)
            
            # Reset rate limit counter after sleeping
            self._rate_limit_remaining = 1000  # Rough estimate, will be updated on next request
    
    def _convert_interval(self, interval: str) -> str:
        """Convert standard interval format to Binance format."""
        # Convert from standard format (e.g., '1h', '4h', '1d') to Binance format
        interval_map = {
            '1m': '1m',
            '3m': '3m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '2h': '2h',
            '4h': '4h',
            '6h': '6h',
            '8h': '8h',
            '12h': '12h',
            '1d': '1d',
            '3d': '3d',
            '1w': '1w',
            '1M': '1M'
        }
        
        return interval_map.get(interval, interval)  # Return as-is if not in the map
    
    async def close(self) -> None:
        """Close the collector and release resources."""
        await super().close()
        
        # Close the HTTP session
        if self._session:
            await self._session.close()
            self._session = None

# Factory function
def create_binance_collector(api_key: str = "", api_secret: str = "", testnet: bool = False, futures: bool = False) -> BinanceCollector:
    """Create a new Binance collector instance."""
    return BinanceCollector(api_key=api_key, api_secret=api_secret, testnet=testnet, futures=futures)
