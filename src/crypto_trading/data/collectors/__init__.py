""
Data collectors for various exchanges.

This package contains implementations of the DataCollector base class
for different cryptocurrency exchanges.
"""
from typing import Dict, Type, Any, Optional

from ..base_collector import DataCollector
from .binance_collector import BinanceCollector, create_binance_collector
from .bitfinex_collector import BitfinexCollector, create_bitfinex_collector

# Registry of available collectors
COLLECTORS: Dict[str, Type[DataCollector]] = {
    'binance': BinanceCollector,
    'bitfinex': BitfinexCollector,
}

# Factory functions for creating collector instances
COLLECTOR_FACTORIES = {
    'binance': create_binance_collector,
    'bitfinex': create_bitfinex_collector,
}

def get_available_collectors() -> Dict[str, Type[DataCollector]]:
    """Get a dictionary of all available collector classes."""
    return dict(COLLECTORS)

def create_collector(exchange: str, *args, **kwargs) -> Optional[DataCollector]:
    """
    Create a collector instance for the specified exchange.
    
    Args:
        exchange: Exchange name (e.g., 'binance', 'bitfinex')
        *args: Positional arguments to pass to the collector constructor
        **kwargs: Keyword arguments to pass to the collector constructor
        
    Returns:
        An instance of the specified collector, or None if not found
    """
    factory = COLLECTOR_FACTORIES.get(exchange.lower())
    if factory:
        return factory(*args, **kwargs)
    return None

__all__ = [
    'BinanceCollector',
    'BitfinexCollector',
    'create_binance_collector',
    'create_bitfinex_collector',
    'get_available_collectors',
    'create_collector',
]
