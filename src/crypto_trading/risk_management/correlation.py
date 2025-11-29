""
Correlation Analysis Module

This module provides functionality for calculating and analyzing correlations
between different assets in a portfolio to manage risk through diversification.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@dataclass
class CorrelationConfig:
    """Configuration for correlation analysis"""
    lookback_days: int = 90  # Days of historical data to use
    min_correlation_samples: int = 10  # Minimum samples required for correlation
    correlation_threshold: float = 0.7  # Threshold for high correlation warning
    update_frequency: int = 24  # Update correlation matrix every X hours

class CorrelationMatrix:
    """Manages correlation matrix for a set of assets"""
    
    def __init__(self, config: Optional[CorrelationConfig] = None):
        self.config = config or CorrelationConfig()
        self.correlation_matrix: pd.DataFrame = pd.DataFrame()
        self.last_updated: Optional[datetime] = None
        self.price_data: Dict[str, pd.Series] = {}
    
    def update_prices(self, symbol: str, prices: pd.Series) -> None:
        """Update price data for a symbol"""
        self.price_data[symbol] = prices
        self._invalidate_cache()
    
    def remove_symbol(self, symbol: str) -> None:
        """Remove a symbol from the correlation matrix"""
        self.price_data.pop(symbol, None)
        self._invalidate_cache()
    
    def _invalidate_cache(self) -> None:
        """Invalidate the cached correlation matrix"""
        self.correlation_matrix = pd.DataFrame()
    
    def calculate_correlations(self, force_update: bool = False) -> pd.DataFrame:
        """Calculate correlation matrix for all symbols"""
        if not force_update and not self.correlation_matrix.empty:
            return self.correlation_matrix
        
        # Prepare price data
        returns = {}
        for symbol, prices in self.price_data.items():
            if len(prices) < 2:
                continue
            returns[symbol] = prices.pct_change().dropna()
        
        if not returns:
            return pd.DataFrame()
        
        # Align all return series by date
        returns_df = pd.DataFrame(returns).dropna()
        
        if len(returns_df) < self.config.min_correlation_samples:
            logger.warning(
                f"Insufficient data points ({len(returns_df)}) "
                f"for correlation analysis (min: {self.config.min_correlation_samples})"
            )
            return pd.DataFrame()
        
        # Calculate correlation matrix
        self.correlation_matrix = returns_df.corr()
        self.last_updated = datetime.utcnow()
        
        return self.correlation_matrix
    
    def get_highly_correlated_pairs(self, threshold: Optional[float] = None) -> List[Tuple[str, str, float]]:
        """Get pairs of symbols with correlation above threshold"""
        if threshold is None:
            threshold = self.config.correlation_threshold
        
        corr_matrix = self.calculate_correlations()
        if corr_matrix.empty:
            return []
        
        # Get upper triangle of correlation matrix
        corr_triu = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        
        # Find pairs with correlation above threshold
        pairs = []
        for i, col in enumerate(corr_triu.columns):
            for row in corr_triu.index[i+1:]:
                corr = corr_triu.loc[row, col]
                if pd.notna(corr) and abs(corr) >= threshold:
                    pairs.append((row, col, corr))
        
        return sorted(pairs, key=lambda x: abs(x[2]), reverse=True)
    
    def get_portfolio_beta(self, portfolio: Dict[str, float], benchmark: str = 'BTC/USDT') -> float:
        """Calculate portfolio beta relative to a benchmark"""
        if benchmark not in self.price_data:
            logger.error(f"Benchmark {benchmark} not found in price data")
            return 0.0
        
        # Calculate returns
        returns = {}
        for symbol in portfolio.keys():
            if symbol in self.price_data:
                returns[symbol] = self.price_data[symbol].pct_change().dropna()
        
        if not returns:
            return 0.0
        
        # Align returns with benchmark
        returns_df = pd.DataFrame(returns).dropna()
        benchmark_returns = self.price_data[benchmark].pct_change().dropna()
        
        # Align indices
        common_index = returns_df.index.intersection(benchmark_returns.index)
        if len(common_index) < self.config.min_correlation_samples:
            logger.warning("Insufficient common data points for beta calculation")
            return 0.0
        
        returns_df = returns_df.loc[common_index]
        benchmark_returns = benchmark_returns[common_index]
        
        # Calculate portfolio beta
        portfolio_returns = (returns_df * list(portfolio.values())).sum(axis=1)
        covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
        variance = np.var(benchmark_returns, ddof=1)
        
        return covariance / variance if variance != 0 else 0.0

class PortfolioRiskAnalyzer:
    """Analyzes portfolio risk using correlation and other metrics"""
    
    def __init__(self, correlation_matrix: CorrelationMatrix):
        self.correlation_matrix = correlation_matrix
    
    def calculate_portfolio_risk(
        self,
        portfolio: Dict[str, float],
        volatility: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate portfolio risk metrics"""
        if not portfolio:
            return {}
        
        # Calculate portfolio weights
        total_value = sum(portfolio.values())
        weights = {k: v / total_value for k, v in portfolio.items()}
        
        # Get correlation matrix
        corr_matrix = self.correlation_matrix.calculate_correlations()
        if corr_matrix.empty:
            return {}
        
        # Filter for assets in portfolio
        symbols = list(portfolio.keys())
        symbols = [s for s in symbols if s in corr_matrix.columns]
        
        if not symbols:
            return {}
        
        # Subset correlation matrix
        corr_matrix = corr_matrix.loc[symbols, symbols]
        
        # Calculate portfolio volatility
        weights_vec = np.array([weights[s] for s in symbols])
        vol_vec = np.array([volatility.get(s, 0) for s in symbols])
        
        # Portfolio variance = w^T * Σ * w
        portfolio_variance = np.dot(weights_vec.T, np.dot(corr_matrix * np.outer(vol_vec, vol_vec), weights_vec))
        portfolio_volatility = np.sqrt(portfolio_variance)
        
        # Calculate component risk contributions
        marginal_risk = np.dot(corr_matrix * vol_vec, weights_vec)
        risk_contributions = weights_vec * marginal_risk / portfolio_volatility if portfolio_volatility > 0 else np.zeros_like(weights_vec)
        
        return {
            'portfolio_volatility': portfolio_volatility,
            'risk_contributions': dict(zip(symbols, risk_contributions)),
            'diversification_ratio': sum(weights_vec * vol_vec) / portfolio_volatility if portfolio_volatility > 0 else 0,
            'concentration_index': sum(weights_vec**2)  # Herfindahl-Hirschman Index
        }
    
    def suggest_hedge(
        self,
        portfolio: Dict[str, float],
        target_volatility: float = 0.2,
        max_hedge_ratio: float = 0.3
    ) -> Dict[str, float]:
        """Suggest hedge positions to reduce portfolio risk"""
        # This is a simplified example - in practice, you'd use more sophisticated optimization
        current_vol = self.calculate_portfolio_risk(portfolio, {}).get('portfolio_volatility', 0)
        
        if current_vol <= target_volatility:
            return {}
        
        # Simple hedge: reduce positions in most volatile assets
        symbols = list(portfolio.keys())
        if not symbols:
            return {}
        
        # Calculate current weights
        total_value = sum(portfolio.values())
        if total_value <= 0:
            return {}
            
        weights = {k: v / total_value for k, v in portfolio.items()}
        
        # Sort assets by weight (descending)
        sorted_assets = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        
        # Calculate total reduction needed
        reduction_needed = (current_vol - target_volatility) / current_vol
        reduction_needed = min(reduction_needed, max_hedge_ratio)
        
        # Distribute reduction across top assets
        hedge = {}
        remaining_reduction = reduction_needed
        
        for symbol, weight in sorted_assets:
            if remaining_reduction <= 0:
                break
                
            # Reduce position by a portion of the reduction needed
            reduction = min(weight * 0.5, remaining_reduction)  # Don't reduce by more than half
            hedge[symbol] = -reduction * total_value  # Negative for selling
            remaining_reduction -= reduction
        
        return hedge

# Example usage
if __name__ == "__main__":
    # Create sample price data
    np.random.seed(42)
    dates = pd.date_range(end=datetime.utcnow(), periods=100, freq='D')
    
    # Generate correlated returns
    n_assets = 5
    means = [0.0005] * n_assets
    cov = np.eye(n_assets) * 0.0001
    cov[0, 1] = cov[1, 0] = 0.00008  # High correlation between first two assets
    
    returns = np.random.multivariate_normal(means, cov, len(dates))
    prices = (1 + returns).cumprod(axis=0)
    
    # Create correlation matrix
    config = CorrelationConfig(
        lookback_days=90,
        min_correlation_samples=10,
        correlation_threshold=0.6
    )
    
    corr_matrix = CorrelationMatrix(config)
    
    # Add price data
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'LTC/USDT', 'ADA/USDT']
    for i, symbol in enumerate(symbols):
        corr_matrix.update_prices(symbol, pd.Series(prices[:, i], index=dates))
    
    # Calculate correlations
    print("Correlation Matrix:")
    print(corr_matrix.calculate_correlations().round(2))
    
    # Find highly correlated pairs
    print("\nHighly Correlated Pairs:")
    for pair in corr_matrix.get_highly_correlated_pairs():
        print(f"{pair[0]} - {pair[1]}: {pair[2]:.2f}")
    
    # Analyze portfolio risk
    portfolio = {
        'BTC/USDT': 5000,
        'ETH/USDT': 3000,
        'XRP/USDT': 2000
    }
    
    # Assume some volatility values (in practice, calculate from returns)
    volatility = {s: 0.02 for s in portfolio.keys()}
    
    analyzer = PortfolioRiskAnalyzer(corr_matrix)
    risk_metrics = analyzer.calculate_portfolio_risk(portfolio, volatility)
    
    print("\nPortfolio Risk Metrics:")
    print(f"Portfolio Volatility: {risk_metrics['portfolio_volatility']:.2%}")
    print("Risk Contributions:")
    for asset, contrib in risk_metrics['risk_contributions'].items():
        print(f"  {asset}: {contrib:.2%}")
