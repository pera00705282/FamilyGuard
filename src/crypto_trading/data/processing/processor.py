""
Data processing utilities for market data.
"""
from typing import Dict, List, Optional, Union, Any, Callable
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from enum import Enum
import talib
from dataclasses import dataclass, field
from ..monitoring.metrics import metrics

logger = logging.getLogger(__name__)

class DataQualityIssue(str, Enum):
    MISSING_VALUES = "missing_values"
    OUTLIERS = "outliers"
    DUPLICATES = "duplicates"
    INCONSISTENT_TIMESTAMPS = "inconsistent_timestamps"
    NEGATIVE_VOLUME = "negative_volume"
    ZERO_VOLUME = "zero_volume"
    INVALID_PRICE = "invalid_price"

@dataclass
class DataQualityReport:
    """Report of data quality issues found in a dataset."""
    issues: Dict[DataQualityIssue, List[Dict[str, Any]]] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def add_issue(self, issue_type: DataQualityIssue, details: Dict[str, Any]) -> None:
        """Add a data quality issue to the report."""
        if issue_type not in self.issues:
            self.issues[issue_type] = []
        self.issues[issue_type].append(details)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the report to a dictionary."""
        return {
            'issues': {k.value: v for k, v in self.issues.items()},
            'metrics': self.metrics
        }

class DataProcessor:
    """Process and enhance market data."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the data processor."""
        self.config = config or {}
        self._cached_indicators: Dict[str, Any] = {}
    
    async def process_data(
        self,
        data: Union[pd.DataFrame, List[Dict[str, Any]]],
        data_type: str,
        symbol: Optional[str] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Process market data with cleaning, normalization, and enhancement.
        
        Args:
            data: Input data as a DataFrame or list of dictionaries
            data_type: Type of data (e.g., 'trades', 'candles', 'orderbook')
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            **kwargs: Additional processing options
            
        Returns:
            Processed DataFrame
        """
        # Convert to DataFrame if needed
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        
        if df.empty:
            logger.warning("Empty DataFrame provided for processing")
            return df
        
        # Ensure timestamp is in datetime format and set as index
        if 'timestamp' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
        
        # Data cleaning
        df = self.clean_data(df, data_type, **kwargs)
        
        # Data quality check
        quality_report = self.check_data_quality(df, data_type, symbol, **kwargs)
        
        # Log quality issues
        for issue_type, issues in quality_report.issues.items():
            for issue in issues:
                logger.warning(f"Data quality issue - {issue_type}: {issue}")
        
        # Data enhancement
        df = self.enhance_data(df, data_type, **kwargs)
        
        # Add metadata
        if symbol:
            df['symbol'] = symbol
        df['data_type'] = data_type
        
        # Update metrics
        self._update_metrics(df, data_type, symbol, quality_report)
        
        return df
    
    def clean_data(
        self,
        df: pd.DataFrame,
        data_type: str,
        **kwargs
    ) -> pd.DataFrame:
        """Clean the data by handling missing values, duplicates, etc."""
        # Make a copy to avoid modifying the original
        df = df.copy()
        
        # Handle missing values
        if data_type == 'trades':
            # For trades, we might want to drop rows with missing prices or quantities
            df = df.dropna(subset=['price', 'quantity'])
        elif data_type == 'candles':
            # For candles, we might want to forward-fill OHLCV values
            ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
            existing_cols = [col for col in ohlcv_cols if col in df.columns]
            if existing_cols:
                df[existing_cols] = df[existing_cols].ffill()
        
        # Remove duplicates
        if 'trade_id' in df.columns:
            df = df.drop_duplicates(subset=['trade_id'])
        else:
            # For data without unique IDs, drop exact duplicates
            df = df.drop_duplicates()
        
        # Ensure numeric columns have the correct type
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Handle negative or zero values where they don't make sense
        if 'volume' in df.columns:
            df['volume'] = df['volume'].clip(lower=0)
        if 'price' in df.columns:
            df['price'] = df['price'].clip(lower=0)
        
        return df
    
    def check_data_quality(
        self,
        df: pd.DataFrame,
        data_type: str,
        symbol: Optional[str] = None,
        **kwargs
    ) -> DataQualityReport:
        """Check data quality and return a report of any issues."""
        report = DataQualityReport()
        
        if df.empty:
            return report
        
        # Check for missing values
        missing = df.isnull().sum()
        for col, count in missing.items():
            if count > 0:
                report.add_issue(
                    DataQualityIssue.MISSING_VALUES,
                    {
                        'column': col,
                        'count': int(count),
                        'percentage': float(count / len(df) * 100)
                    }
                )
        
        # Check for duplicates
        if df.index.duplicated().any():
            dupes = df.index.duplicated(keep='first')
            report.add_issue(
                DataQualityIssue.DUPLICATES,
                {
                    'count': int(dupes.sum()),
                    'percentage': float(dupes.mean() * 100),
                    'indices': df.index[dupes].tolist()
                }
            )
        
        # Check for inconsistent timestamps (only if we have a time index)
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
            time_diffs = df.index.to_series().diff().dropna()
            if not time_diffs.empty:
                min_diff = time_diffs.min()
                max_diff = time_diffs.max()
                avg_diff = time_diffs.mean()
                
                if min_diff != max_diff:
                    report.add_issue(
                        DataQualityIssue.INCONSISTENT_TIMESTAMPS,
                        {
                            'min_interval': str(min_diff),
                            'max_interval': str(max_diff),
                            'avg_interval': str(avg_diff)
                        }
                    )
        
        # Check for price/volume anomalies
        if 'price' in df.columns:
            prices = df['price']
            if (prices <= 0).any():
                invalid = (prices <= 0)
                report.add_issue(
                    DataQualityIssue.INVALID_PRICE,
                    {
                        'count': int(invalid.sum()),
                        'percentage': float(invalid.mean() * 100),
                        'min_price': float(prices.min()),
                        'max_price': float(prices.max())
                    }
                )
        
        if 'volume' in df.columns:
            volumes = df['volume']
            if (volumes < 0).any():
                negative = (volumes < 0)
                report.add_issue(
                    DataQualityIssue.NEGATIVE_VOLUME,
                    {
                        'count': int(negative.sum()),
                        'percentage': float(negative.mean() * 100)
                    }
                )
            
            if (volumes == 0).any():
                zero = (volumes == 0)
                report.add_issue(
                    DataQualityIssue.ZERO_VOLUME,
                    {
                        'count': int(zero.sum()),
                        'percentage': float(zero.mean() * 100)
                    }
                )
        
        # Add basic metrics
        report.metrics = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'start_time': df.index.min().isoformat() if not df.empty else None,
            'end_time': df.index.max().isoformat() if not df.empty else None,
            'data_type': data_type,
            'symbol': symbol
        }
        
        return report
    
    def enhance_data(
        self,
        df: pd.DataFrame,
        data_type: str,
        **kwargs
    ) -> pd.DataFrame:
        """Enhance the data with additional features and indicators."""
        if df.empty:
            return df
        
        # Make a copy to avoid modifying the original
        df = df.copy()
        
        # Add time-based features
        if isinstance(df.index, pd.DatetimeIndex):
            df['hour'] = df.index.hour
            df['day_of_week'] = df.index.dayofweek
            df['day_of_month'] = df.index.day
            df['month'] = df.index.month
            df['is_weekend'] = df.index.dayofweek >= 5
        
        # Add price-based features
        if 'close' in df.columns and len(df) > 1:
            # Simple Moving Averages
            for period in [5, 10, 20, 50, 100, 200]:
                df[f'sma_{period}'] = talib.SMA(df['close'], timeperiod=period)
            
            # Exponential Moving Averages
            for period in [9, 21, 50, 200]:
                df[f'ema_{period}'] = talib.EMA(df['close'], timeperiod=period)
            
            # Bollinger Bands
            upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20)
            df['bb_upper'] = upper
            df['bb_middle'] = middle
            df['bb_lower'] = lower
            df['bb_width'] = (upper - lower) / middle
            
            # RSI
            df['rsi_14'] = talib.RSI(df['close'], timeperiod=14)
            
            # MACD
            macd, signal, hist = talib.MACD(df['close'])
            df['macd'] = macd
            df['macd_signal'] = signal
            df['macd_hist'] = hist
            
            # ATR (Average True Range)
            if all(col in df.columns for col in ['high', 'low', 'close']):
                df['atr_14'] = talib.ATR(
                    df['high'], df['low'], df['close'], timeperiod=14
                )
            
            # Volume indicators
            if 'volume' in df.columns:
                df['volume_sma_20'] = talib.SMA(df['volume'], timeperiod=20)
                df['obv'] = talib.OBV(df['close'], df['volume'])
        
        # Add order book specific features
        if data_type == 'orderbook' and 'bids' in df.columns and 'asks' in df.columns:
            # Calculate order book depth
            def calculate_depth(row, levels=10):
                try:
                    bids = row['bids'][:levels] if isinstance(row['bids'], list) else []
                    asks = row['asks'][:levels] if isinstance(row['asks'], list) else []
                    
                    bid_vol = sum(price * qty for price, qty in bids) if bids else 0
                    ask_vol = sum(price * qty for price, qty in asks) if asks else 0
                    
                    mid_price = (bids[0][0] + asks[0][0]) / 2 if bids and asks else 0
                    spread = (asks[0][0] - bids[0][0]) / mid_price if mid_price > 0 else 0
                    
                    return pd.Series({
                        'bid_volume': bid_vol,
                        'ask_volume': ask_vol,
                        'order_imbalance': (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0,
                        'mid_price': mid_price,
                        'spread_bps': spread * 10000  # in basis points
                    })
                except (IndexError, TypeError):
                    return pd.Series({
                        'bid_volume': 0,
                        'ask_volume': 0,
                        'order_imbalance': 0,
                        'mid_price': 0,
                        'spread_bps': 0
                    })
            
            # Apply the function to each row
            ob_metrics = df.apply(calculate_depth, axis=1)
            df = pd.concat([df, ob_metrics], axis=1)
        
        return df
    
    def resample_data(
        self,
        df: pd.DataFrame,
        rule: str = '1T',
        ohlcv: bool = True
    ) -> pd.DataFrame:
        """
        Resample time series data to a different frequency.
        
        Args:
            df: Input DataFrame with a datetime index
            rule: Resampling rule (e.g., '1T' for 1 minute, '1H' for 1 hour)
            ohlcv: Whether to perform OHLCV resampling (True) or simple resampling (False)
            
        Returns:
            Resampled DataFrame
        """
        if df.empty or not isinstance(df.index, pd.DatetimeIndex):
            return df
        
        if ohlcv and all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume']):
            # OHLCV resampling
            ohlc_dict = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }
            
            # Include additional numeric columns with appropriate aggregation
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if col not in ohlc_dict:
                    ohlc_dict[col] = 'mean'
            
            return df.resample(rule).agg(ohlc_dict).dropna()
        else:
            # Simple resampling with mean aggregation for numeric columns
            return df.resample(rule).mean().dropna()
    
    def _update_metrics(
        self,
        df: pd.DataFrame,
        data_type: str,
        symbol: Optional[str],
        quality_report: DataQualityReport
    ) -> None:
        """Update monitoring metrics."""
        if df.empty:
            return
        
        # Update data quality metrics
        for issue_type, issues in quality_report.issues.items():
            metrics.record_histogram(
                f"data_quality_issues_count",
                len(issues),
                tags={
                    'issue_type': issue_type.value,
                    'data_type': data_type,
                    'symbol': symbol or 'unknown'
                }
            )
        
        # Update data volume metrics
        metrics.record_gauge(
            f"data_processing_row_count",
            len(df),
            tags={
                'data_type': data_type,
                'symbol': symbol or 'unknown'
            }
        )
        
        # Record processing time
        if 'processing_start' in df.attrs:
            processing_time = (datetime.utcnow() - df.attrs['processing_start']).total_seconds()
            metrics.record_histogram(
                f"data_processing_time_seconds",
                processing_time,
                tags={
                    'data_type': data_type,
                    'symbol': symbol or 'unknown'
                }
            )

# Factory function
def create_data_processor(config: Optional[Dict[str, Any]] = None) -> DataProcessor:
    """Create a new data processor instance."""
    return DataProcessor(config)
