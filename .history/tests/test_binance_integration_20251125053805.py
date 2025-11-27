"""Integration tests for Binance exchange."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crypto_trading.exchanges import BinanceExchange

# Mock data
MOCK_TICKER = {
    'symbol': 'BTCUSDT',
    'priceChange': '150.20',
    'priceChangePercent': '1.23',
    'weightedAvgPrice': '12345.67',
    'prevClosePrice': '12200.50',
    'lastPrice': '12350.75',
    'lastQty': '0.25',
    'bidPrice': '12350.00',
    'bidQty': '1.25',
    'askPrice': '12351.00',
    'askQty': '0.75',
    'openPrice': '12200.50',
    'highPrice': '12400.00',
    'lowPrice': '12150.25',
    'volume': '2500.50',
    'quoteVolume': '30893750.25',
    'openTime': 1633046400000,
    'closeTime': 1633132800000,
    'firstId': 123456789,
    'lastId': 123459876,
    'count': 12345
}

MOCK_ORDER_BOOK = {
    'lastUpdateId': 123456789,
    'bids': [
        ['12350.00', '1.25'],
        ['12349.50', '0.75'],
        ['12349.00', '2.10']
    ],
    'asks': [
        ['12351.00', '0.75'],
        ['12351.50', '1.50'],
        ['12352.00', '0.90']
    ]
}

MOCK_BALANCE = {
    'makerCommission': 10,
    'takerCommission': 10,
    'buyerCommission': 0,
    'sellerCommission': 0,
    'canTrade': True,
    'canWithdraw': True,
    'canDeposit': True,
    'updateTime': 1633132800000,
    'accountType': 'SPOT',
    'balances': [
        {'asset': 'BTC', 'free': '1.5', 'locked': '0.5'},
        {'asset': 'ETH', 'free': '10.0', 'locked': '2.0'},
        {'asset': 'USDT', 'free': '5000.0', 'locked': '1000.0'},
        {'asset': 'LTC', 'free': '0.0', 'locked': '0.0'}
    ]
}

class TestBinanceExchange(unittest.IsolatedAsyncioTestCase):
    """Test cases for BinanceExchange class."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.exchange = BinanceExchange(
            api_key='test_key',
            api_secret='test_secret'
        )
        
        # Mock the HTTP client session
        self.session_mock = AsyncMock()
        self.exchange._http_client._session = self.session_mock
    
    async def asyncTearDown(self):
        """Clean up after tests."""
        await self.exchange.disconnect()
    
    async def test_get_ticker(self):
        """Test getting ticker data."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TICKER
        self.session_mock.get.return_value.__aenter__.return_value = mock_response
        
        # Call the method
        ticker = await self.exchange.get_ticker('BTCUSDT')
        
        # Assert the results
        self.assertEqual(ticker.symbol, 'BTCUSDT')
        self.assertEqual(ticker.last, Decimal('12350.75'))
        self.assertEqual(ticker.bid, Decimal('12350.00'))
        self.assertEqual(ticker.ask, Decimal('12351.00'))
        self.assertEqual(ticker.base_volume, Decimal('2500.50'))
        self.assertEqual(ticker.quote_volume, Decimal('30893750.25'))
        
        # Verify the API call
        self.session_mock.get.assert_called_once_with(
            'https://api.binance.com/api/v3/ticker/24hr',
            params={'symbol': 'BTCUSDT'},
            headers=None
        )
    
    async def test_get_order_book(self):
        """Test getting order book."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_ORDER_BOOK
        self.session_mock.get.return_value.__aenter__.return_value = mock_response
        
        # Call the method
        order_book = await self.exchange.get_order_book('BTCUSDT', limit=100)
        
        # Assert the results
        self.assertEqual(len(order_book.bids), 3)
        self.assertEqual(len(order_book.asks), 3)
        self.assertEqual(order_book.bids[0][0], Decimal('12350.00'))
        self.assertEqual(order_book.bids[0][1], Decimal('1.25'))
        self.assertEqual(order_book.asks[0][0], Decimal('12351.00'))
        self.assertEqual(order_book.asks[0][1], Decimal('0.75'))
        
        # Verify the API call
        self.session_mock.get.assert_called_once_with(
            'https://api.binance.com/api/v3/depth',
            params={'symbol': 'BTCUSDT', 'limit': 100}
        )
    
    async def test_get_balance(self):
        """Test getting account balance."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_BALANCE
        self.session_mock.get.return_value.__aenter__.return_value = mock_response
        
        # Call the method
        balances = await self.exchange.get_balance()
        
        # Assert the results
        self.assertEqual(len(balances), 3)  # Only non-zero balances
        self.assertEqual(balances['BTC'], Decimal('1.5'))
        self.assertEqual(balances['ETH'], Decimal('10.0'))
        self.assertEqual(balances['USDT'], Decimal('5000.0'))
        
        # Verify the API call
        self.session_mock.get.assert_called_once()
        args, kwargs = self.session_mock.get.call_args
        self.assertIn('https://api.binance.com/api/v3/account', args[0])
        self.assertIn('X-MBX-APIKEY', kwargs['headers'])
        self.assertTrue(kwargs['params']['signature'])

    async def test_create_order(self):
        """Test creating an order."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'orderId': 123456,
            'symbol': 'BTCUSDT',
            'status': 'NEW',
            'type': 'LIMIT',
            'side': 'BUY',
            'price': '40000.00',
            'origQty': '0.1',
            'executedQty': '0.0',
            'timeInForce': 'GTC',
            'time': 1633132800000,
            'updateTime': 1633132800000,
            'isWorking': True
        }
        self.session_mock.post.return_value.__aenter__.return_value = mock_response
        
        # Call the method
        order = await self.exchange.create_order(
            symbol='BTCUSDT',
            order_type='limit',
            side='buy',
            amount=Decimal('0.1'),
            price=Decimal('40000.00')
        )
        
        # Assert the results
        self.assertEqual(order['orderId'], 123456)
        self.assertEqual(order['symbol'], 'BTCUSDT')
        self.assertEqual(order['status'], 'NEW')
        
        # Verify the API call
        self.session_mock.post.assert_called_once()
        args, kwargs = self.session_mock.post.call_args
        self.assertIn('https://api.binance.com/api/v3/order', args[0])
        self.assertIn('X-MBX-APIKEY', kwargs['headers'])
        self.assertTrue(kwargs['data']['signature'])
        self.assertEqual(kwargs['data']['symbol'], 'BTCUSDT')
        self.assertEqual(kwargs['data']['side'], 'BUY')
        self.assertEqual(kwargs['data']['type'], 'LIMIT')
        self.assertEqual(kwargs['data']['quantity'], '0.1')
        self.assertEqual(kwargs['data']['price'], '40000.00')

    async def test_connection_management(self):
        """Test connection management methods."""
        # Test connect
        await self.exchange.connect()
        self.exchange._session.get.assert_called_once_with(
            f"{self.exchange.api_url}/api/v3/ping"
        )

        # Test disconnect
        await self.exchange.disconnect()
        self.exchange._session.close.assert_awaited_once()
        self.assertIsNone(self.exchange._session)

if __name__ == '__main__':
    unittest.main()
