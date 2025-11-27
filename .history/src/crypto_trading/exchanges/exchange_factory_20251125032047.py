


from typing import Dict, Type, Optional, Any

logger = logging.getLogger(__name__)

class ExchangeFactory:
    """Factory for creating and managing exchange instances."""

    _exchange_classes: Dict[str, Type[BaseExchange]] = {}
    _instances: Dict[str, BaseExchange] = {}

    @classmethod
    def register_exchange(cls, name: str, exchange_class: Type[BaseExchange]) -> None:
        """Register a new exchange class.

        Args:
            name: Exchange name (e.g., 'binance', 'kraken')
            exchange_class: The exchange class to register
        """
        if not issubclass(exchange_class, BaseExchange):
            raise TypeError(f"Exchange class must inherit from BaseExchange, got {exchange_class}")

        name = name.lower()
        if name in cls._exchange_classes:
            logger.warning(f"Exchange '{name}' is already registered. Overwriting...")

        cls._exchange_classes[name] = exchange_class
        logger.info(f"Registered exchange: {name}")

    @classmethod
    def create_exchange(cls, name: str, *args: Any, **kwargs: Any) -> BaseExchange:
        """Create a new exchange instance.

        Args:
            name: Name of the exchange to create
            *args: Positional arguments to pass to the exchange constructor
            **kwargs: Keyword arguments to pass to the exchange constructor

        Returns:
            An instance of the requested exchange

        Raises:
            ValueError: If the exchange is not registered
        """
        name = name.lower()
        if name not in cls._exchange_classes:
            # Try to auto-import the exchange module
            try:
                module_name = f"crypto_trading.exchanges.{name}_exchange"
                importlib.import_module(module_name)
                if name not in cls._exchange_classes:
                    raise ImportError(f"Exchange module {module_name} doesn't register the exchange")
            except ImportError as e:
                raise ValueError(f"Unknown exchange: {name}. Registered exchanges: {list(cls._exchange_classes.keys())}") from e

        # Create a key for the instance based on the arguments
        instance_key = f"{name}:{str(args)}:{str(sorted(kwargs.items()))}"

        # Return existing instance if it exists
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Create and store new instance
        exchange = cls._exchange_classes[name](*args, **kwargs)
        cls._instances[instance_key] = exchange
        return exchange

    @classmethod
    def get_available_exchanges(cls) -> list:
        """Get a list of available exchange names."""
        return list(cls._exchange_classes.keys())

    @classmethod
    async def close_all(cls) -> None:
        """Close all exchange connections."""
        for exchange in cls._instances.values():
            try:
                await exchange.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from {exchange.name}: {str(e)}")

        cls._instances.clear()

# Auto-register exchanges when the module is imported
try:
    from .binance_exchange import BinanceExchange
    ExchangeFactory.register_exchange('binance', BinanceExchange)
except ImportError as e:
    logger.warning(f"Failed to register Binance exchange: {e}")

try:
    from .poloniex_exchange import PoloniexExchange
    ExchangeFactory.register_exchange('poloniex', PoloniexExchange)
except ImportError as e:
    logger.warning(f"Failed to register Poloniex exchange: {e}")

try:
    from .bybit_exchange import BybitExchange
    ExchangeFactory.register_exchange('bybit', BybitExchange)
except ImportError as e:
    logger.warning(f"Failed to register Bybit exchange: {e}")