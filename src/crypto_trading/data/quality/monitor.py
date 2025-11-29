""
Data quality monitoring and validation.
"""
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from enum import Enum
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Callable
import hashlib
import time

from ...monitoring.metrics import metrics
from ...monitoring.alerts import Alert, AlertSeverity, AlertType, AlertManager

logger = logging.getLogger(__name__)

class DataQualityMetric(str, Enum):
    """Data quality metrics that can be monitored."""
    MISSING_VALUES = "missing_values"
    DUPLICATES = "duplicates"
    OUTLIERS = "outliers"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    SPREAD = "spread"
    LATENCY = "latency"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    VALIDITY = "validity"

@dataclass
class DataQualityCheck:
    """A data quality check with conditions and alert thresholds."""
    name: str
    metric: DataQualityMetric
    condition: Callable[[pd.Series], bool]
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    message: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    
    def check(self, series: pd.Series) -> bool:
        """Check if the condition is met."""
        try:
            return self.condition(series) > self.threshold
        except Exception as e:
            logger.error(f"Error in data quality check '{self.name}': {e}")
            return False

class DataQualityMonitor:
    """Monitor data quality and generate alerts for issues."""
    
    def __init__(self, alert_manager: Optional[AlertManager] = None):
        """Initialize the data quality monitor."""
        self.checks: Dict[str, DataQualityCheck] = {}
        self.alert_manager = alert_manager or AlertManager()
        self._setup_default_checks()
    
    def _setup_default_checks(self) -> None:
        """Set up default data quality checks."""
        # Missing values check
        self.add_check(
            DataQualityCheck(
                name="missing_values_high",
                metric=DataQualityMetric.MISSING_VALUES,
                condition=lambda s: s.isna().mean(),
                threshold=0.05,  # 5% missing values
                severity=AlertSeverity.WARNING,
                message="High percentage of missing values detected",
                tags={"component": "data_quality"}
            )
        )
        
        # Duplicates check
        self.add_check(
            DataQualityCheck(
                name="duplicate_rows_high",
                metric=DataQualityMetric.DUPLICATES,
                condition=lambda s: s.duplicated().mean() if hasattr(s, 'duplicated') else 0,
                threshold=0.1,  # 10% duplicates
                severity=AlertSeverity.WARNING,
                message="High percentage of duplicate rows detected",
                tags={"component": "data_quality"}
            )
        )
        
        # Price volatility check
        self.add_check(
            DataQualityCheck(
                name="price_volatility_high",
                metric=DataQualityMetric.VOLATILITY,
                condition=lambda s: s.pct_change().std() if hasattr(s, 'pct_change') else 0,
                threshold=0.05,  # 5% standard deviation in price changes
                severity=AlertSeverity.WARNING,
                message="High price volatility detected",
                tags={"component": "market_data", "data_type": "price"}
            )
        )
        
        # Volume anomaly check
        self.add_check(
            DataQualityCheck(
                name="volume_anomaly",
                metric=DataQualityMetric.VOLUME,
                condition=self._volume_anomaly_condition,
                threshold=3.0,  # 3 standard deviations from mean
                severity=AlertSeverity.WARNING,
                message="Volume anomaly detected",
                tags={"component": "market_data", "data_type": "volume"}
            )
        )
    
    def _volume_anomaly_condition(self, series: pd.Series, window: int = 20) -> float:
        """Check for volume anomalies using z-score."""
        if len(series) < window + 1:
            return 0.0
            
        rolling_mean = series.rolling(window=window).mean()
        rolling_std = series.rolling(window=window).std()
        
        if rolling_std.iloc[-1] == 0:
            return 0.0
            
        z_scores = (series - rolling_mean) / rolling_std
        return z_scores.abs().max()
    
    def add_check(self, check: DataQualityCheck) -> None:
        """Add a data quality check."""
        self.checks[check.name] = check
    
    def remove_check(self, name: str) -> None:
        """Remove a data quality check by name."""
        self.checks.pop(name, None)
    
    async def check_dataframe(
        self,
        df: pd.DataFrame,
        data_type: str = "unknown",
        symbol: str = "unknown",
        source: str = "unknown"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check a DataFrame for data quality issues.
        
        Args:
            df: Input DataFrame to check
            data_type: Type of data (e.g., 'trades', 'candles', 'orderbook')
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            source: Data source (e.g., 'binance', 'bitfinex')
            
        Returns:
            Dictionary of issues found, keyed by check name
        """
        if df.empty:
            logger.warning("Empty DataFrame provided for data quality check")
            return {}
        
        issues = {}
        
        # Add basic context to all alerts
        alert_context = {
            'data_type': data_type,
            'symbol': symbol,
            'source': source,
            'row_count': len(df),
            'column_count': len(df.columns),
            'start_time': df.index.min().isoformat() if not df.empty else None,
            'end_time': df.index.max().isoformat() if not df.empty else None,
            'check_time': datetime.utcnow().isoformat()
        }
        
        # Run each check
        for check_name, check in self.checks.items():
            # Skip checks that don't apply to this data type if specified
            if 'data_type' in check.tags and check.tags['data_type'] != data_type:
                continue
                
            for col in df.select_dtypes(include=[np.number]).columns:
                try:
                    if check.check(df[col]):
                        # Get check details
                        check_value = check.condition(df[col])
                        
                        # Create issue details
                        issue = {
                            'check_name': check_name,
                            'metric': check.metric.value,
                            'column': col,
                            'check_value': float(check_value),
                            'threshold': float(check.threshold),
                            'severity': check.severity.value,
                            'message': check.message or f"Data quality issue detected in {col}",
                            'context': {
                                **alert_context,
                                'column': col,
                                'min_value': float(df[col].min()),
                                'max_value': float(df[col].max()),
                                'mean_value': float(df[col].mean()),
                                'std_dev': float(df[col].std()),
                                'missing_count': int(df[col].isna().sum())
                            }
                        }
                        
                        # Add to issues
                        if check_name not in issues:
                            issues[check_name] = []
                        issues[check_name].append(issue)
                        
                        # Send alert
                        await self._send_alert(issue, check)
                        
                except Exception as e:
                    logger.error(f"Error running check '{check_name}' on column '{col}': {e}")
        
        # Update metrics
        self._update_metrics(issues, data_type, symbol, source)
        
        return issues
    
    async def _send_alert(self, issue: Dict[str, Any], check: DataQualityCheck) -> None:
        """Send an alert for a data quality issue."""
        if not self.alert_manager:
            return
            
        alert = Alert(
            alert_id=f"dqm_{check.name}_{issue['column']}_{int(time.time())}",
            alert_type=AlertType.DATA_QUALITY_ISSUE,
            severity=check.severity,
            title=f"Data Quality: {check.message or check.name}",
            message=(
                f"{issue['message']}\n"
                f"Column: {issue['column']}\n"
                f"Value: {issue['check_value']:.6f} (threshold: {check.threshold:.6f})\n"
                f"Data Type: {issue['context']['data_type']}\n"
                f"Symbol: {issue['context']['symbol']}\n"
                f"Source: {issue['context']['source']}\n"
                f"Time Range: {issue['context']['start_time']} to {issue['context']['end_time']}"
            ),
            details=issue,
            timestamp=datetime.utcnow(),
            tags={
                **check.tags,
                'metric': check.metric.value,
                'column': issue['column'],
                'data_type': issue['context']['data_type'],
                'symbol': issue['context']['symbol'],
                'source': issue['context']['source']
            }
        )
        
        await self.alert_manager.send_alert(alert)
    
    def _update_metrics(
        self,
        issues: Dict[str, List[Dict[str, Any]]],
        data_type: str,
        symbol: str,
        source: str
    ) -> None:
        """Update monitoring metrics."""
        # Count issues by severity and metric
        severity_counts = {}
        metric_counts = {}
        
        for check_issues in issues.values():
            for issue in check_issues:
                # Count by severity
                severity = issue['severity']
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                # Count by metric
                metric = issue['metric']
                metric_counts[metric] = metric_counts.get(metric, 0) + 1
        
        # Record severity counts
        for severity, count in severity_counts.items():
            metrics.record_counter(
                "data_quality_issues_total",
                count,
                tags={
                    'severity': severity,
                    'data_type': data_type,
                    'symbol': symbol,
                    'source': source
                }
            )
        
        # Record metric counts
        for metric, count in metric_counts.items():
            metrics.record_counter(
                "data_quality_metrics_total",
                count,
                tags={
                    'metric': metric,
                    'data_type': data_type,
                    'symbol': symbol,
                    'source': source
                }
            )
    
    async def check_streaming_data(
        self,
        data_point: Dict[str, Any],
        data_type: str = "unknown",
        symbol: str = "unknown",
        source: str = "unknown"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check a single data point in a streaming context.
        
        Args:
            data_point: Single data point as a dictionary
            data_type: Type of data (e.g., 'trades', 'candles', 'orderbook')
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            source: Data source (e.g., 'binance', 'bitfinex')
            
        Returns:
            Dictionary of issues found, keyed by check name
        """
        # Convert single data point to DataFrame for consistent checking
        df = pd.DataFrame([data_point])
        
        # Set timestamp as index if available
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
        
        return await self.check_dataframe(df, data_type, symbol, source)

# Factory function
def create_data_quality_monitor(alert_manager: Optional[AlertManager] = None) -> DataQualityMonitor:
    """Create a new data quality monitor instance."""
    return DataQualityMonitor(alert_manager)
