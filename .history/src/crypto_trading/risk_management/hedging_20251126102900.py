""
Hedging Strategies Module

This module provides functionality for implementing various hedging strategies
to manage portfolio risk, including delta hedging, pairs trading, and options-based hedging.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Callable
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class HedgeType(Enum):
    """Types of hedging strategies"""
    DELTA_NEUTRAL = auto()
    PAIRS_TRADING = auto()
    OPTIONS_HEDGE = auto()
    FUTURES_HEDGE = auto()

@dataclass
class HedgeConfig:
    """Configuration for hedging strategies"""
    hedge_type: HedgeType = HedgeType.DELTA_NEUTRAL
    max_hedge_ratio: float = 0.3  # Maximum portion of portfolio to hedge
    rebalance_threshold: float = 0.05  # Rebalance when hedge drifts by 5%
    lookback_period: int = 30  # Days to look back for correlation/historical analysis
    min_hedge_duration: int = 24  # Minimum hours to maintain a hedge (avoid whipsaws)
    max_hedge_duration: int = 168  # Maximum hours to maintain a hedge (1 week)

class HedgeManager:
    """Manages hedging strategies for a portfolio"""
    
    def __init__(self, config: Optional[HedgeConfig] = None):
        self.config = config or HedgeConfig()
        self.active_hedges: Dict[str, Dict] = {}
        self.hedge_history: List[Dict] = []
        self.hedge_created_at: Dict[str, datetime] = {}
    
    def calculate_delta_hedge(
        self,
        portfolio: Dict[str, float],
        deltas: Dict[str, float],
        prices: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calculate delta-neutral hedge positions
        
        Args:
            portfolio: Dictionary of {asset: position_size}
            deltas: Dictionary of {asset: delta} where delta is the sensitivity to market
            prices: Dictionary of {asset: current_price}
            
        Returns:
            Dictionary of {asset: hedge_position} to achieve delta neutrality
        """
        if not portfolio or not deltas or not prices:
            return {}
        
        # Calculate portfolio delta
        portfolio_delta = 0.0
        for asset, position in portfolio.items():
            if asset in deltas and asset in prices and prices[asset] > 0:
                portfolio_delta += position * deltas[asset] / prices[asset]
        
        # Find best assets to hedge with (most liquid, highest correlation)
        hedge_assets = self._find_best_hedge_assets(portfolio, deltas, prices)
        if not hedge_assets:
            return {}
        
        # Calculate hedge positions
        hedge_positions = {}
        remaining_delta = -portfolio_delta  # We want to offset the portfolio delta
        
        # Distribute hedge across available assets
        for asset in hedge_assets:
            if remaining_delta == 0:
                break
                
            if asset in deltas and asset in prices and prices[asset] > 0:
                # Calculate position to fully hedge remaining delta
                position = remaining_delta / (deltas[asset] / prices[asset])
                
                # Apply position limits
                max_position = self.config.max_hedge_ratio * sum(abs(v) for v in portfolio.values())
                position = max(-max_position, min(position, max_position))
                
                hedge_positions[asset] = position
                remaining_delta -= position * (deltas[asset] / prices[asset])
        
        return hedge_positions
    
    def calculate_pairs_hedge(
        self,
        portfolio: Dict[str, float],
        correlations: pd.DataFrame,
        prices: Dict[str, float],
        threshold: float = 0.7
    ) -> List[Tuple[str, str, float]]:
        """
        Identify pairs trading opportunities based on correlation
        
        Args:
            portfolio: Dictionary of {asset: position_size}
            correlations: DataFrame of asset correlations
            prices: Dictionary of {asset: current_price}
            threshold: Minimum correlation to consider for pairs trading
            
        Returns:
            List of (asset1, asset2, hedge_ratio) tuples
        """
        pairs = []
        assets = list(portfolio.keys())
        
        for i in range(len(assets)):
            for j in range(i+1, len(assets)):
                asset1, asset2 = assets[i], assets[j]
                
                # Check if assets are in correlation matrix
                if (asset1 in correlations.index and 
                    asset2 in correlations.columns and
                    asset1 in prices and 
                    asset2 in prices and
                    prices[asset1] > 0 and 
                    prices[asset2] > 0):
                    
                    corr = correlations.loc[asset1, asset2]
                    if abs(corr) >= threshold:
                        # Calculate hedge ratio (simplified - in practice, use cointegration)
                        hedge_ratio = prices[asset1] / prices[asset2]
                        pairs.append((asset1, asset2, hedge_ratio))
        
        return pairs
    
    def manage_hedges(
        self, 
        portfolio: Dict[str, float],
        market_data: Dict[str, Dict],
        force_rebalance: bool = False
    ) -> Dict[str, float]:
        """
        Manage all active hedges and determine if rebalancing is needed
        
        Args:
            portfolio: Current portfolio positions
            market_data: Dictionary with market data including prices, deltas, etc.
            force_rebalance: Whether to force rebalancing regardless of thresholds
            
        Returns:
            Dictionary of hedge adjustments to make
        """
        if not portfolio or not market_data:
            return {}
        
        current_time = datetime.utcnow()
        hedge_adjustments = {}
        
        # Check existing hedges
        for hedge_id, hedge in list(self.active_hedges.items()):
            if hedge_id not in self.hedge_created_at:
                self.hedge_created_at[hedge_id] = current_time
                continue
            
            # Check if hedge has expired
            hedge_age = current_time - self.hedge_created_at[hedge_id]
            if hedge_age > timedelta(hours=self.config.max_hedge_duration):
                logger.info(f"Closing expired hedge: {hedge_id}")
                self._close_hedge(hedge_id, "expired")
                continue
            
            # Check if hedge needs rebalancing
            if self._needs_rebalance(hedge, market_data) or force_rebalance:
                logger.info(f"Rebalancing hedge: {hedge_id}")
                adjustment = self._calculate_rebalance(hedge, market_data)
                if adjustment:
                    hedge_adjustments.update(adjustment)
        
        # Check if new hedges are needed
        if self.config.hedge_type == HedgeType.DELTA_NEUTRAL:
            deltas = market_data.get('deltas', {})
            prices = market_data.get('prices', {})
            new_hedge = self.calculate_delta_hedge(portfolio, deltas, prices)
            if new_hedge:
                hedge_id = f"delta_hedge_{int(current_time.timestamp())}"
                self.active_hedges[hedge_id] = {
                    'type': 'delta_neutral',
                    'positions': new_hedge,
                    'created_at': current_time,
                    'last_rebalanced': current_time
                }
                hedge_adjustments.update(new_hedge)
        
        return hedge_adjustments
    
    def _find_best_hedge_assets(
        self,
        portfolio: Dict[str, float],
        deltas: Dict[str, float],
        prices: Dict[str, float]
    ) -> List[str]:
        """Find the best assets to use for hedging"""
        # In a real implementation, this would consider liquidity, fees, and other factors
        # For simplicity, we'll just return assets with the highest deltas
        return sorted(
            [a for a in deltas.keys() if a in prices and prices[a] > 0],
            key=lambda x: abs(deltas[x]),
            reverse=True
        )
    
    def _needs_rebalance(self, hedge: Dict, market_data: Dict) -> bool:
        """Determine if a hedge needs rebalancing"""
        if 'last_rebalanced' not in hedge:
            return True
            
        # Check time since last rebalance
        last_rebalance = hedge['last_rebalanced']
        if not isinstance(last_rebalance, datetime):
            return True
            
        time_since_rebalance = datetime.utcnow() - last_rebalance
        if time_since_rebalance < timedelta(hours=1):  # Minimum time between rebalances
            return False
            
        # Check if hedge has drifted beyond threshold
        if 'type' not in hedge:
            return True
            
        if hedge['type'] == 'delta_neutral' and 'deltas' in market_data:
            # Calculate current delta exposure
            current_delta = 0.0
            for asset, position in hedge.get('positions', {}).items():
                if asset in market_data['deltas'] and asset in market_data.get('prices', {}):
                    price = market_data['prices'][asset]
                    if price > 0:
                        current_delta += position * market_data['deltas'][asset] / price
            
            # Check if delta has drifted beyond threshold
            return abs(current_delta) > self.config.rebalance_threshold
            
        return False
    
    def _calculate_rebalance(self, hedge: Dict, market_data: Dict) -> Dict[str, float]:
        """Calculate adjustments needed to rebalance a hedge"""
        if hedge.get('type') == 'delta_neutral' and 'deltas' in market_data:
            # In a real implementation, this would calculate the exact rebalancing needed
            # For simplicity, we'll just return the existing positions
            return hedge.get('positions', {})
        return {}
    
    def _close_hedge(self, hedge_id: str, reason: str = ""):
        """Close an existing hedge"""
        if hedge_id in self.active_hedges:
            hedge = self.active_hedges.pop(hedge_id)
            self.hedge_history.append({
                'id': hedge_id,
                'type': hedge.get('type', ''),
                'created_at': self.hedge_created_at.pop(hedge_id, None),
                'closed_at': datetime.utcnow(),
                'reason': reason,
                'positions': hedge.get('positions', {})
            })

class HedgeStrategy:
    """Base class for implementing specific hedging strategies"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
    
    def calculate_hedge(self, portfolio: Dict, market_data: Dict) -> Dict:
        """Calculate hedge positions"""
        raise NotImplementedError
    
    def should_hedge(self, portfolio: Dict, market_data: Dict) -> bool:
        """Determine if hedging is currently needed"""
        raise NotImplementedError

class DeltaNeutralStrategy(HedgeStrategy):
    """Delta-neutral hedging strategy"""
    
    def calculate_hedge(self, portfolio: Dict, market_data: Dict) -> Dict:
        if 'deltas' not in market_data or 'prices' not in market_data:
            return {}
            
        hedge_manager = HedgeManager()
        return hedge_manager.calculate_delta_hedge(
            portfolio,
            market_data['deltas'],
            market_data['prices']
        )
    
    def should_hedge(self, portfolio: Dict, market_data: Dict) -> bool:
        # Check if we have the necessary data
        if 'deltas' not in market_data or 'prices' not in market_data:
            return False
            
        # Check if portfolio has significant delta exposure
        total_delta = 0.0
        for asset, position in portfolio.items():
            if asset in market_data['deltas'] and asset in market_data['prices']:
                price = market_data['prices'][asset]
                if price > 0:
                    total_delta += position * market_data['deltas'][asset] / price
        
        # Hedge if delta exceeds threshold
        portfolio_value = sum(abs(v) for v in portfolio.values())
        if portfolio_value == 0:
            return False
            
        delta_pct = abs(total_delta) / portfolio_value
        return delta_pct > self.config.get('delta_threshold', 0.05)

# Example usage
if __name__ == "__main__":
    # Initialize hedge manager
    config = HedgeConfig(
        hedge_type=HedgeType.DELTA_NEUTRAL,
        max_hedge_ratio=0.3,
        rebalance_threshold=0.05,
        lookback_period=30,
        min_hedge_duration=24,
        max_hedge_duration=168
    )
    
    hedge_manager = HedgeManager(config)
    
    # Example portfolio and market data
    portfolio = {
        'BTC/USDT': 1.0,      # 1 BTC
        'ETH/USDT': 10.0,     # 10 ETH
        'SOL/USDT': 100.0     # 100 SOL
    }
    
    market_data = {
        'prices': {
            'BTC/USDT': 50000.0,
            'ETH/USDT': 3000.0,
            'SOL/USDT': 100.0,
            'BTC-PERP': 50100.0,  # Futures contract for hedging
            'ETH-PERP': 3010.0    # Futures contract for hedging
        },
        'deltas': {
            'BTC/USDT': 1.0,   # Spot BTC has delta of 1.0
            'ETH/USDT': 1.0,   # Spot ETH has delta of 1.0
            'SOL/USDT': 1.0,   # Spot SOL has delta of 1.0
            'BTC-PERP': 1.0,   # Perp futures have delta of 1.0
            'ETH-PERP': 1.0    # Perp futures have delta of 1.0
        }
    }
    
    # Calculate initial hedge
    hedge_positions = hedge_manager.calculate_delta_hedge(
        portfolio,
        market_data['deltas'],
        market_data['prices']
    )
    
    print("Initial Hedge Positions:")
    for asset, position in hedge_positions.items():
        print(f"{asset}: {position:.4f}")
    
    # Simulate market move and rebalance
    print("\nAfter Market Move:")
    market_data['prices']['BTC/USDT'] = 52000.0  # BTC price increased
    market_data['prices']['ETH/USDT'] = 2900.0   # ETH price decreased
    
    # Check if rebalance is needed
    rebalance = hedge_manager.manage_hedges(portfolio, market_data)
    if rebalance:
        print("\nRebalancing Hedge:")
        for asset, position in rebalance.items():
            print(f"{asset}: {position:.4f}")
    else:
        print("\nNo rebalancing needed")
