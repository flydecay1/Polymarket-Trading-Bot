"""Orderbook analysis and liquidity calculations."""
from typing import Dict, Any, List, Tuple, Optional
import structlog

logger = structlog.get_logger(__name__)


class OrderBook:
    """Orderbook analyzer for Polymarket markets."""

    def __init__(self, orderbook_data: Dict[str, Any]):
        """Initialize orderbook.

        Args:
            orderbook_data: Raw orderbook data with bids and asks
        """
        self.bids: List[Dict[str, Any]] = orderbook_data.get('bids', [])
        self.asks: List[Dict[str, Any]] = orderbook_data.get('asks', [])

    @property
    def best_bid(self) -> Optional[float]:
        """Get best bid price."""
        if not self.bids:
            return None
        return float(self.bids[0]['price'])

    @property
    def best_ask(self) -> Optional[float]:
        """Get best ask price."""
        if not self.asks:
            return None
        return float(self.asks[0]['price'])

    @property
    def midpoint(self) -> Optional[float]:
        """Get midpoint price."""
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_percentage(self) -> Optional[float]:
        """Get spread as percentage of midpoint."""
        if self.midpoint and self.spread:
            return (self.spread / self.midpoint) * 100
        return None

    def get_liquidity(self, levels: int = 5) -> Dict[str, float]:
        """Calculate available liquidity.

        Args:
            levels: Number of orderbook levels to consider

        Returns:
            Dictionary with bid and ask liquidity
        """
        bid_liquidity = 0.0
        ask_liquidity = 0.0

        for i, bid in enumerate(self.bids[:levels]):
            bid_liquidity += float(bid.get('size', 0))

        for i, ask in enumerate(self.asks[:levels]):
            ask_liquidity += float(ask.get('size', 0))

        return {
            'bid_liquidity': bid_liquidity,
            'ask_liquidity': ask_liquidity,
            'total_liquidity': bid_liquidity + ask_liquidity
        }

    def get_implied_probability(self) -> Optional[float]:
        """Get market's implied probability from midpoint.

        Returns:
            Implied probability (0.0 to 1.0)
        """
        # In Polymarket, prices are already probabilities (0.0 to 1.0)
        return self.midpoint

    def calculate_slippage(self, side: str, size: float) -> Tuple[float, float]:
        """Calculate expected slippage for a market order.

        Args:
            side: "BUY" or "SELL"
            size: Order size

        Returns:
            Tuple of (average_price, slippage_percentage)
        """
        levels = self.asks if side == "BUY" else self.bids

        if not levels:
            return 0.0, 0.0

        remaining_size = size
        total_cost = 0.0

        for level in levels:
            level_price = float(level['price'])
            level_size = float(level['size'])

            fill_size = min(remaining_size, level_size)
            total_cost += fill_size * level_price
            remaining_size -= fill_size

            if remaining_size <= 0:
                break

        if remaining_size > 0:
            # Not enough liquidity
            logger.warning("insufficient_liquidity", side=side, size=size, remaining=remaining_size)

        average_price = total_cost / size if size > 0 else 0.0

        # Calculate slippage vs best price
        best_price = self.best_ask if side == "BUY" else self.best_bid
        if best_price and best_price > 0:
            slippage_pct = abs((average_price - best_price) / best_price) * 100
        else:
            slippage_pct = 0.0

        return average_price, slippage_pct

    def is_tradeable(
        self,
        min_liquidity: float = 100.0,
        max_spread: float = 0.05
    ) -> bool:
        """Check if market is tradeable.

        Args:
            min_liquidity: Minimum total liquidity required
            max_spread: Maximum spread allowed (as decimal)

        Returns:
            True if market meets trading criteria
        """
        liquidity = self.get_liquidity()
        total_liquidity = liquidity['total_liquidity']

        if total_liquidity < min_liquidity:
            logger.debug("insufficient_liquidity", liquidity=total_liquidity, min=min_liquidity)
            return False

        if self.spread and self.spread > max_spread:
            logger.debug("spread_too_wide", spread=self.spread, max=max_spread)
            return False

        return True
