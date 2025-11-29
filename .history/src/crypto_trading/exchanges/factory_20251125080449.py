""
Factory for creating exchange client instances.

This module provides a factory class for creating and managing exchange clients.
"""
from typing import Dict, Type, Optional, Union, Any
import logging
from .interfaces import BaseExchangeClient, BaseWebSocketClient, ExchangeError

# Import exchange implementations
from .binance_exchange import BinanceExchangeClient
from .binance_websocket import BinanceWebSocketClient

logger = logging.getLogger(__name__)

class ExchangeFactory:
    """Factory for creating and managing exchange clients.
    
    This class provides a centralized way to create and manage exchange client
    instances, with support for both REST and WebSocket APIs.
    """
    
    # Mapping of exchange names to their respective client classes
    _EXCHANGE_CLIENTS = {
        'binance': {
            'rest': BinanceExchangeClient,
            'websocket': BinanceWebSocketClient
        },
        # Add other exchanges here as they are implemented
    }
    
    @classmethod
    def get_available_exchanges(cls) -> list:
        """Get a list of available exchanges.
        
        Returns:
            list: List of available exchange names
        """
        return list(cls._EXCHANGE_CLIENTS.keys())
    
    @classmethod
    async def create_client(
        cls,
        exchange: str,
        client_type: str = 'rest',
        **kwargs
    ) -> Union[BaseExchangeClient, BaseWebSocketClient]:
        """Create a new exchange client instance.
        
        Args:
            exchange: Exchange name (e.g., 'binance')
            client_type: Type of client ('rest' or 'websocket')
            **kwargs: Additional arguments to pass to the client constructor
            
        Returns:
            Union[BaseExchangeClient, BaseWebSocketClient]: Exchange client instance
            
        Raises:
            ValueError: If the exchange or client type is not supported
        """
        exchange = exchange.lower()
        client_type = client_type.lower()
        
        if exchange not in cls._EXCHANGE_CLIENTS:
            raise ValueError(f"Unsupported exchange: {exchange}")
            
        if client_type not in cls._EXCHANGE_CLIENTS[exchange]:
            raise ValueError(
                f"Unsupported client type '{client_type}' for exchange {exchange}"
            )
        
        client_class = cls._EXCHANGE_CLIENTS[exchange][client_type]
        
        try:
            # Create and return the client instance
            if client_type == 'websocket':
                return client_class(**kwargs)
            else:
                return await client_class.create(**kwargs)
                
        except Exception as e:
            logger.error(f"Failed to create {exchange} {client_type} client: {e}")
            raise ExchangeError(f"Failed to initialize {exchange} client: {e}") from e
    
    @classmethod
    def register_exchange(
        cls,
        exchange: str,
        rest_client: Optional[Type[BaseExchangeClient]] = None,
        websocket_client: Optional[Type[BaseWebSocketClient]] = None
    ) -> None:
        """Register a new exchange implementation.
        
        This method allows adding support for new exchanges at runtime.
        
        Args:
            exchange: Exchange name (e.g., 'bitfinex')
            rest_client: REST client class for the exchange
            websocket_client: WebSocket client class for the exchange
        """
        exchange = exchange.lower()
        
        if exchange not in cls._EXCHANGE_CLIENTS:
            cls._EXCHANGE_CLIENTS[exchange] = {}
        
        if rest_client is not None:
            if not issubclass(rest_client, BaseExchangeClient):
                raise TypeError("REST client must be a subclass of BaseExchangeClient")
            cls._EXCHANGE_CLIENTS[exchange]['rest'] = rest_client
        
        if websocket_client is not None:
            if not issubclass(websocket_client, BaseWebSocketClient):
                raise TypeError("WebSocket client must be a subclass of BaseWebSocketClient")
            cls._EXCHANGE_CLIENTS[exchange]['websocket'] = websocket_client


# Example usage:
# factory = ExchangeFactory()
# client = await factory.create_client('binance', 'rest', api_key='...', api_secret='...')
