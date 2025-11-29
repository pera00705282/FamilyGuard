""
Data reconciliation and consistency checking.
"""
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from enum import Enum
import asyncio
from dataclasses import dataclass, field
from collections import defaultdict
import json
import time

from ...monitoring.metrics import metrics
from ...monitoring.alerts import Alert, AlertSeverity, AlertType, AlertManager

logger = logging.getLogger(__name__)

class ReconciliationType(str, Enum):
    """Types of reconciliation checks."""
    CROSS_EXCHANGE = "cross_exchange"
    TIME_SERIES = "time_series"
    SUMMARY_STATS = "summary_stats"
    PRICE_VOLUME = "price_volume"
    ORDER_BOOK = "order_book"
    TRADE_COUNT = "trade_count"
    LATENCY = "latency"

@dataclass
class ReconciliationResult:
    """Result of a reconciliation check."""
    check_type: ReconciliationType
    status: bool  # True if check passed, False otherwise
    metrics: Dict[str, Any] = field(default_factory=dict)
    differences: List[Dict[str, Any]] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def add_difference(self, field: str, expected: Any, actual: Any, tolerance: float = 0.0) -> None:
        """Add a difference to the result."""
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)) and tolerance > 0:
            diff = abs(expected - actual)
            diff_pct = (diff / expected) * 100 if expected != 0 else float('inf')
            
            if diff_pct > tolerance:
                self.differences.append({
                    'field': field,
                    'expected': expected,
                    'actual': actual,
                    'difference': diff,
                    'difference_pct': diff_pct,
                    'tolerance_pct': tolerance,
                    'within_tolerance': diff_pct <= tolerance
                })
                
                if diff_pct > tolerance * 2:  # Severe difference
                    self.status = False
        else:
            if expected != actual:
                self.differences.append({
                    'field': field,
                    'expected': expected,
                    'actual': actual,
                    'difference': None,
                    'difference_pct': None,
                    'tolerance_pct': tolerance,
                    'within_tolerance': False
                })
                self.status = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary."""
        return {
            'check_type': self.check_type.value,
            'status': self.status,
            'metrics': self.metrics,
            'differences': self.differences,
            'details': self.details
        }

class DataReconciler:
    """Reconcile data between different sources and time periods."""
    
    def __init__(self, alert_manager: Optional[AlertManager] = None):
        """Initialize the data reconciler."""
        self.alert_manager = alert_manager
        self.checks: Dict[ReconciliationType, List[Callable]] = {
            ReconciliationType.CROSS_EXCHANGE: [
                self._check_cross_exchange_prices,
                self._check_cross_exchange_volumes
            ],
            ReconciliationType.TIME_SERIES: [
                self._check_time_series_continuity,
                self._check_time_series_outliers
            ],
            ReconciliationType.SUMMARY_STATS: [
                self._check_summary_statistics
            ],
            ReconciliationType.PRICE_VOLUME: [
                self._check_price_volume_relationship
            ],
            ReconciliationType.ORDER_BOOK: [
                self._check_order_book_integrity
            ],
            ReconciliationType.TRADE_COUNT: [
                self._check_trade_count_consistency
            ],
            ReconciliationType.LATENCY: [
                self._check_data_latency
            ]
        }
    
    async def reconcile(
        self,
        data_sources: Dict[str, Union[pd.DataFrame, Dict[str, Any]]],
        check_types: Optional[List[ReconciliationType]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, ReconciliationResult]:
        """
        Reconcile data between multiple sources.
        
        Args:
            data_sources: Dictionary mapping source names to DataFrames or dicts
            check_types: List of reconciliation types to perform (None for all)
            context: Additional context for reconciliation
            
        Returns:
            Dictionary mapping check types to ReconciliationResult objects
        """
        if not data_sources:
            raise ValueError("At least one data source is required")
        
        # Default to all check types if none specified
        if check_types is None:
            check_types = list(ReconciliationType)
        
        results = {}
        
        # Run each requested check
        for check_type in check_types:
            if check_type not in self.checks:
                logger.warning(f"Unknown reconciliation type: {check_type}")
                continue
            
            # Initialize result for this check type
            result = ReconciliationResult(check_type=check_type, status=True)
            
            # Run all checks of this type
            for check_func in self.checks[check_type]:
                try:
                    await check_func(data_sources, result, context or {})
                except Exception as e:
                    logger.error(f"Error in {check_func.__name__}: {e}", exc_info=True)
                    result.status = False
                    result.details['error'] = str(e)
            
            # Store result
            results[check_type.value] = result
            
            # Send alert if check failed
            if not result.status and self.alert_manager:
                await self._send_reconciliation_alert(result, context or {})
            
            # Update metrics
            self._update_metrics(result, context or {})
        
        return results
    
    async def _check_cross_exchange_prices(
        self,
        data_sources: Dict[str, Any],
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Check for price discrepancies across exchanges."""
        if len(data_sources) < 2:
            return  # Need at least two sources for comparison
        
        # Extract prices from each source
        prices = {}
        for source_name, data in data_sources.items():
            if isinstance(data, pd.DataFrame) and 'close' in data.columns:
                prices[source_name] = data['close'].iloc[-1] if not data.empty else None
            elif isinstance(data, dict) and 'price' in data:
                prices[source_name] = data['price']
        
        # Skip if we don't have enough price data
        if len(prices) < 2:
            return
        
        # Calculate statistics
        price_values = [p for p in prices.values() if p is not None]
        if not price_values:
            return
            
        min_price = min(price_values)
        max_price = max(price_values)
        avg_price = sum(price_values) / len(price_values)
        max_diff = max_price - min_price
        max_diff_pct = (max_diff / avg_price) * 100 if avg_price != 0 else float('inf')
        
        # Store metrics
        result.metrics.update({
            'min_price': min_price,
            'max_price': max_price,
            'avg_price': avg_price,
            'max_diff': max_diff,
            'max_diff_pct': max_diff_pct,
            'price_source_count': len(price_values)
        })
        
        # Check for significant differences
        tolerance_pct = context.get('price_tolerance_pct', 1.0)  # Default 1% tolerance
        
        if max_diff_pct > tolerance_pct:
            # Find the pair with the largest difference
            max_diff_pair = None
            max_pair_diff = 0
            
            sources = list(prices.keys())
            for i in range(len(sources)):
                for j in range(i + 1, len(sources)):
                    s1, s2 = sources[i], sources[j]
                    p1, p2 = prices[s1], prices[s2]
                    
                    if p1 is None or p2 is None:
                        continue
                    
                    diff = abs(p1 - p2)
                    diff_pct = (diff / ((p1 + p2) / 2)) * 100
                    
                    if diff_pct > max_pair_diff:
                        max_pair_diff = diff_pct
                        max_diff_pair = (s1, s2, p1, p2, diff, diff_pct)
            
            if max_diff_pair:
                s1, s2, p1, p2, diff, diff_pct = max_diff_pair
                result.add_difference(
                    f"price_{s1}_vs_{s2}",
                    p1,
                    p2,
                    tolerance_pct
                )
                
                result.details['max_diff_pair'] = {
                    'source1': s1,
                    'source2': s2,
                    'price1': p1,
                    'price2': p2,
                    'difference': diff,
                    'difference_pct': diff_pct
                }
    
    async def _check_cross_exchange_volumes(
        self,
        data_sources: Dict[str, Any],
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Check for volume discrepancies across exchanges."""
        if len(data_sources) < 2:
            return  # Need at least two sources for comparison
        
        # Extract volumes from each source
        volumes = {}
        for source_name, data in data_sources.items():
            if isinstance(data, pd.DataFrame) and 'volume' in data.columns:
                volumes[source_name] = data['volume'].sum() if not data.empty else 0
            elif isinstance(data, dict) and 'volume' in data:
                volumes[source_name] = data['volume']
        
        # Skip if we don't have enough volume data
        if len(volumes) < 2:
            return
        
        # Calculate statistics
        volume_values = [v for v in volumes.values() if v is not None]
        if not volume_values:
            return
            
        min_vol = min(volume_values)
        max_vol = max(volume_values)
        avg_vol = sum(volume_values) / len(volume_values)
        max_diff = max_vol - min_vol
        max_diff_pct = (max_diff / avg_vol) * 100 if avg_vol != 0 else float('inf')
        
        # Store metrics
        result.metrics.update({
            'min_volume': min_vol,
            'max_volume': max_vol,
            'avg_volume': avg_vol,
            'max_volume_diff': max_diff,
            'max_volume_diff_pct': max_diff_pct,
            'volume_source_count': len(volume_values)
        })
        
        # Check for significant differences
        tolerance_pct = context.get('volume_tolerance_pct', 10.0)  # Default 10% tolerance
        
        if max_diff_pct > tolerance_pct:
            # Find the pair with the largest difference
            max_diff_pair = None
            max_pair_diff = 0
            
            sources = list(volumes.keys())
            for i in range(len(sources)):
                for j in range(i + 1, len(sources)):
                    s1, s2 = sources[i], sources[j]
                    v1, v2 = volumes[s1], volumes[s2]
                    
                    if v1 is None or v2 is None or v1 == 0 or v2 == 0:
                        continue
                    
                    ratio = max(v1, v2) / min(v1, v2)
                    diff_pct = (ratio - 1) * 100
                    
                    if diff_pct > max_pair_diff:
                        max_pair_diff = diff_pct
                        max_diff_pair = (s1, s2, v1, v2, diff_pct)
            
            if max_diff_pair:
                s1, s2, v1, v2, diff_pct = max_diff_pair
                result.add_difference(
                    f"volume_{s1}_vs_{s2}",
                    v1,
                    v2,
                    tolerance_pct
                )
                
                result.details['max_volume_diff_pair'] = {
                    'source1': s1,
                    'source2': s2,
                    'volume1': v1,
                    'volume2': v2,
                    'difference_pct': diff_pct
                }
    
    async def _check_time_series_continuity(
        self,
        data_sources: Dict[str, Any],
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Check for gaps or inconsistencies in time series data."""
        for source_name, data in data_sources.items():
            if not isinstance(data, pd.DataFrame) or data.empty or 'timestamp' not in data.columns:
                continue
            
            # Ensure timestamp is datetime and sorted
            df = data.copy()
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            df = df.sort_values('timestamp')
            
            # Check for missing timestamps
            time_diff = df['timestamp'].diff().dropna()
            if len(time_diff) == 0:
                continue
                
            # Get expected time interval (most common difference)
            expected_interval = time_diff.mode().iloc[0] if not time_diff.empty else None
            
            if expected_interval is None:
                continue
            
            # Find gaps larger than expected
            gaps = time_diff[time_diff > expected_interval * 1.5]  # 50% tolerance
            gap_count = len(gaps)
            max_gap = gaps.max() if not gaps.empty else None
            
            # Store metrics
            result.metrics[f'{source_name}_gap_count'] = gap_count
            if max_gap is not None:
                result.metrics[f'{source_name}_max_gap_seconds'] = max_gap.total_seconds()
            
            # Add to differences if gaps found
            if gap_count > 0:
                result.add_difference(
                    f"{source_name}_time_gaps",
                    0,
                    gap_count,
                    tolerance=0  # Any gap is a difference
                )
                
                gap_details = []
                for idx, gap in gaps.items():
                    prev_time = df.loc[idx - 1, 'timestamp']
                    curr_time = df.loc[idx, 'timestamp']
                    gap_details.append({
                        'before': prev_time.isoformat(),
                        'after': curr_time.isoformat(),
                        'gap_seconds': gap.total_seconds()
                    })
                
                result.details[f'{source_name}_gaps'] = gap_details
    
    async def _check_time_series_outliers(
        self,
        data_sources: Dict[str, Any],
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Check for outliers in time series data."""
        for source_name, data in data_sources.items():
            if not isinstance(data, pd.DataFrame) or data.empty:
                continue
            
            # Check for price outliers if available
            if 'close' in data.columns:
                prices = data['close'].dropna()
                if len(prices) > 1:
                    # Use IQR method to detect outliers
                    Q1 = prices.quantile(0.25)
                    Q3 = prices.quantile(0.75)
                    IQR = Q3 - Q1
                    
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    
                    outliers = prices[(prices < lower_bound) | (prices > upper_bound)]
                    outlier_count = len(outliers)
                    
                    if outlier_count > 0:
                        result.metrics[f'{source_name}_price_outliers'] = outlier_count
                        result.details[f'{source_name}_price_outliers'] = {
                            'count': outlier_count,
                            'lower_bound': lower_bound,
                            'upper_bound': upper_bound,
                            'outlier_indices': outliers.index.tolist(),
                            'outlier_values': outliers.tolist()
                        }
                        
                        # Add to differences if significant number of outliers
                        outlier_pct = (outlier_count / len(prices)) * 100
                        if outlier_pct > 1.0:  # More than 1% outliers
                            result.add_difference(
                                f"{source_name}_price_outliers",
                                0,
                                outlier_count,
                                tolerance=0  # Any outlier is a difference
                            )
    
    async def _check_summary_statistics(
        self,
        data_sources: Dict[str, Any],
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Check summary statistics for consistency."""
        for source_name, data in data_sources.items():
            if not isinstance(data, pd.DataFrame) or data.empty:
                continue
            
            stats = {}
            
            # Basic statistics for numeric columns
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                col_stats = data[col].describe().to_dict()
                stats[col] = {k: float(v) if isinstance(v, (np.number, np.floating)) else v 
                            for k, v in col_stats.items()}
            
            # Add to metrics and details
            result.metrics[f'{source_name}_stats'] = stats
            result.details[f'{source_name}_stats'] = stats
    
    async def _check_price_volume_relationship(
        self,
        data_sources: Dict[str, Any],
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Check for unusual price-volume relationships."""
        for source_name, data in data_sources.items():
            if not isinstance(data, pd.DataFrame) or data.empty:
                continue
            
            if 'close' not in data.columns or 'volume' not in data.columns:
                continue
            
            df = data.copy()
            
            # Calculate price change and volume change
            df['price_change'] = df['close'].pct_change()
            df['volume_change'] = df['volume'].pct_change()
            
            # Calculate correlation between absolute price change and volume
            corr = df['price_change'].abs().corr(df['volume_change'])
            
            result.metrics[f'{source_name}_price_volume_corr'] = corr
            
            # Check for negative correlation (unusual)
            if corr < -0.3:  # Arbitrary threshold
                result.add_difference(
                    f"{source_name}_price_volume_correlation",
                    0.0,  # Expected positive correlation
                    corr,
                    tolerance=0.3
                )
                
                result.details[f'{source_name}_price_volume'] = {
                    'correlation': corr,
                    'expected_min': 0.0,
                    'is_anomalous': corr < -0.3
                }
    
    async def _check_order_book_integrity(
        self,
        data_sources: Dict[str, Any],
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Check order book integrity (bids < asks, etc.)."""
        for source_name, data in data_sources.items():
            if not isinstance(data, dict):
                continue
            
            issues = []
            
            # Check bids and asks
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            if bids and asks:
                best_bid = max(b[0] for b in bids if len(b) > 0)
                best_ask = min(a[0] for a in asks if len(a) > 0)
                
                if best_bid >= best_ask:
                    issues.append({
                        'type': 'crossed_market',
                        'best_bid': best_bid,
                        'best_ask': best_ask,
                        'message': f'Crossed market: best bid ({best_bid}) >= best ask ({best_ask})'
                    })
            
            # Check for empty or invalid price/quantity levels
            for side, levels in [('bids', bids), ('asks', asks)]:
                for i, level in enumerate(levels):
                    if len(level) < 2:
                        issues.append({
                            'type': 'invalid_level',
                            'side': side,
                            'index': i,
                            'level': level,
                            'message': f'Invalid {side} level at index {i}: {level}'
                        })
                        continue
                    
                    price, qty = level[0], level[1]
                    
                    if price <= 0:
                        issues.append({
                            'type': 'invalid_price',
                            'side': side,
                            'index': i,
                            'price': price,
                            'message': f'Invalid price in {side} at index {i}: {price} <= 0'
                        })
                    
                    if qty < 0:
                        issues.append({
                            'type': 'invalid_quantity',
                            'side': side,
                            'index': i,
                            'quantity': qty,
                            'message': f'Negative quantity in {side} at index {i}: {qty}'
                        })
            
            # Check for price monotonicity
            for side, levels in [('bids', bids), ('asks', asks)]:
                prices = [level[0] for level in levels if len(level) > 0]
                
                if side == 'bids' and prices != sorted(prices, reverse=True):
                    issues.append({
                        'type': 'non_monotonic_prices',
                        'side': side,
                        'message': f'Bid prices are not monotonically decreasing'
                    })
                elif side == 'asks' and prices != sorted(prices):
                    issues.append({
                        'type': 'non_monotonic_prices',
                        'side': side,
                        'message': f'Ask prices are not monotonically increasing'
                    })
            
            # Add issues to result
            if issues:
                result.status = False
                result.details[f'{source_name}_order_book_issues'] = issues
                
                # Add to differences
                for issue in issues:
                    result.add_difference(
                        f"{source_name}_order_book_{issue['type']}",
                        "Valid",
                        issue['message'],
                        tolerance=0
                    )
    
    async def _check_trade_count_consistency(
        self,
        data_sources: Dict[str, Any],
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Check for consistency in trade counts across time periods."""
        for source_name, data in data_sources.items():
            if not isinstance(data, pd.DataFrame) or data.empty or 'timestamp' not in data.columns:
                continue
            
            df = data.copy()
            
            # Ensure timestamp is datetime and sorted
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            df = df.sort_values('timestamp')
            
            # Resample to count trades per time period
            time_window = context.get('trade_count_window', '1T')  # Default 1 minute
            trade_counts = df.resample(time_window, on='timestamp').size()
            
            if len(trade_counts) < 2:
                continue
            
            # Check for significant drops in trade count
            mean_count = trade_counts.mean()
            std_count = trade_counts.std()
            
            if std_count == 0:
                continue  # All counts are the same
            
            # Find periods with unusually low trade counts
            z_scores = (trade_counts - mean_count) / std_count
            anomalies = trade_counts[z_scores < -2]  # More than 2 standard deviations below mean
            
            if not anomalies.empty:
                result.metrics[f'{source_name}_low_trade_periods'] = len(anomalies)
                result.details[f'{source_name}_low_trade_periods'] = {
                    'count': len(anomalies),
                    'mean_trades': mean_count,
                    'min_trades': trade_counts.min(),
                    'max_trades': trade_counts.max(),
                    'anomaly_indices': anomalies.index.tolist(),
                    'anomaly_values': anomalies.tolist()
                }
                
                # Add to differences if significant
                if len(anomalies) > 0.05 * len(trade_counts):  # More than 5% of periods
                    result.add_difference(
                        f"{source_name}_low_trade_periods",
                        mean_count,
                        anomalies.min(),
                        tolerance=2 * std_count / mean_count * 100  # 2 std dev as percentage of mean
                    )
    
    async def _check_data_latency(
        self,
        data_sources: Dict[str, Any],
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Check for excessive data latency."""
        current_time = pd.Timestamp.utcnow()
        max_latency = context.get('max_latency_seconds', 60)  # Default 60 seconds
        
        for source_name, data in data_sources.items():
            if isinstance(data, pd.DataFrame) and not data.empty and 'timestamp' in data.columns:
                # Get the most recent timestamp
                latest_ts = pd.to_datetime(data['timestamp']).max()
                latency = (current_time - latest_ts).total_seconds()
                
                result.metrics[f'{source_name}_latency_seconds'] = latency
                
                if latency > max_latency:
                    result.status = False
                    result.add_difference(
                        f"{source_name}_data_latency",
                        max_latency,
                        latency,
                        tolerance=0  # Any latency over max is a difference
                    )
                    
                    result.details[f'{source_name}_latency'] = {
                        'latest_timestamp': latest_ts.isoformat(),
                        'current_time': current_time.isoformat(),
                        'latency_seconds': latency,
                        'max_allowed_seconds': max_latency
                    }
            elif isinstance(data, dict) and 'timestamp' in data:
                # Handle single data point
                try:
                    latest_ts = pd.to_datetime(data['timestamp'])
                    latency = (current_time - latest_ts).total_seconds()
                    
                    result.metrics[f'{source_name}_latency_seconds'] = latency
                    
                    if latency > max_latency:
                        result.status = False
                        result.add_difference(
                            f"{source_name}_data_latency",
                            max_latency,
                            latency,
                            tolerance=0  # Any latency over max is a difference
                        )
                        
                        result.details[f'{source_name}_latency'] = {
                            'latest_timestamp': latest_ts.isoformat(),
                            'current_time': current_time.isoformat(),
                            'latency_seconds': latency,
                            'max_allowed_seconds': max_latency
                        }
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing timestamp from {source_name}: {e}")
    
    async def _send_reconciliation_alert(
        self,
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Send an alert for reconciliation failures."""
        if not self.alert_manager:
            return
        
        # Prepare alert details
        check_type = result.check_type.value
        difference_count = len(result.differences)
        
        # Create a summary of differences
        diff_summary = []
        for diff in result.differences[:5]:  # Include up to 5 differences
            if isinstance(diff['actual'], (int, float)) and isinstance(diff['expected'], (int, float)):
                diff_str = (
                    f"{diff['field']}: {diff['actual']} (expected ~{diff['expected']}, "
                    f"diff: {diff.get('difference_pct', 'N/A'):.2f}%)"
                )
            else:
                diff_str = f"{diff['field']}: {diff['actual']} (expected: {diff['expected']})"
            diff_summary.append(f"- {diff_str}")
        
        if difference_count > 5:
            diff_summary.append(f"... and {difference_count - 5} more differences")
        
        # Create alert message
        message = (
            f"Reconciliation check failed: {check_type}\n"
            f"Found {difference_count} differences\n\n"
            f"Sample differences:\n" + "\n".join(diff_summary)
        )
        
        # Create alert
        alert = Alert(
            alert_id=f"recon_{check_type}_{int(time.time())}",
            alert_type=AlertType.DATA_RECONCILIATION,
            severity=AlertSeverity.WARNING,
            title=f"Data Reconciliation Failed: {check_type}",
            message=message,
            details={
                'check_type': check_type,
                'differences_count': difference_count,
                'differences': result.differences[:20],  # Include up to 20 differences in details
                'metrics': result.metrics,
                'context': context
            },
            timestamp=datetime.utcnow(),
            tags={
                'component': 'data_reconciliation',
                'check_type': check_type,
                'status': 'failed',
                'difference_count': str(difference_count)
            }
        )
        
        await self.alert_manager.send_alert(alert)
    
    def _update_metrics(
        self,
        result: ReconciliationResult,
        context: Dict[str, Any]
    ) -> None:
        """Update monitoring metrics."""
        check_type = result.check_type.value
        
        # Record check status (1 for success, 0 for failure)
        status_value = 1 if result.status else 0
        metrics.record_gauge(
            "data_reconciliation_status",
            status_value,
            tags={
                'check_type': check_type,
                'status': 'success' if result.status else 'failure',
                **context.get('tags', {})
            }
        )
        
        # Record difference count
        difference_count = len(result.differences)
        metrics.record_gauge(
            "data_reconciliation_differences",
            difference_count,
            tags={
                'check_type': check_type,
                **context.get('tags', {})
            }
        )
        
        # Record custom metrics from the result
        for metric_name, metric_value in result.metrics.items():
            if isinstance(metric_value, (int, float)):
                metrics.record_gauge(
                    f"data_reconciliation_{metric_name}",
                    metric_value,
                    tags={
                        'check_type': check_type,
                        **context.get('tags', {})
                    }
                )

# Factory function
def create_data_reconciler(alert_manager: Optional[AlertManager] = None) -> 'DataReconciler':
    """Create a new data reconciler instance."""
    return DataReconciler(alert_manager)
