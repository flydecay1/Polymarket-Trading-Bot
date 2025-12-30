"""Arbitrage trading strategy."""
from typing import Dict, Any, Optional
from dataclasses import dataclass
import structlog

from ..data_ingestion.game_state import GameState
from ..polymarket.orderbook import OrderBook

logger = structlog.get_logger(__name__)


@dataclass
class TradeSignal:
    """Signal to execute a trade."""

    match_id: str
    game_number: int
    token_id: str
    side: str  # "BUY" or "SELL"
    size: float
    limit_price: float
    edge: float
    model_prob: float
    market_prob: float
    game_state: GameState


class ArbitrageStrategy:
    """Strategy for identifying arbitrage opportunities."""

    def __init__(
        self,
        min_edge: float = 0.05,
        max_position_size: float = 100.0,
        min_liquidity: float = 500.0,
        max_spread: float = 0.02,
        slippage_tolerance: float = 0.01,
        use_kelly_criterion: bool = True,
        kelly_fraction: float = 0.25
    ):
        """Initialize strategy.

        Args:
            min_edge: Minimum edge required to trade (5% = 0.05)
            max_position_size: Maximum position size in USD
            min_liquidity: Minimum market liquidity required
            max_spread: Maximum bid-ask spread allowed
            slippage_tolerance: Maximum slippage tolerance
            use_kelly_criterion: Use Kelly Criterion for position sizing
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
        """
        self.min_edge = min_edge
        self.max_position_size = max_position_size
        self.min_liquidity = min_liquidity
        self.max_spread = max_spread
        self.slippage_tolerance = slippage_tolerance
        self.use_kelly_criterion = use_kelly_criterion
        self.kelly_fraction = kelly_fraction

    def evaluate(
        self,
        game_state: GameState,
        model_prob: float,
        orderbook: OrderBook,
        token_id: str
    ) -> Optional[TradeSignal]:
        """Evaluate if there's a trading opportunity.

        Args:
            game_state: Current game state
            model_prob: Model's probability for team1
            orderbook: Market orderbook
            token_id: Token ID for team1

        Returns:
            TradeSignal if opportunity exists, None otherwise
        """
        # Get market probability
        market_prob = orderbook.get_implied_probability()

        if market_prob is None:
            logger.debug("no_market_price", match_id=game_state.match_id)
            return None

        # Calculate edge
        edge = model_prob - market_prob

        logger.debug(
            "evaluating_opportunity",
            match_id=game_state.match_id,
            model_prob=model_prob,
            market_prob=market_prob,
            edge=edge,
            min_edge=self.min_edge
        )

        # Check if edge is sufficient
        if abs(edge) < self.min_edge:
            logger.debug("edge_too_small", edge=edge, min_edge=self.min_edge)
            return None

        # Check if market is tradeable
        if not orderbook.is_tradeable(self.min_liquidity, self.max_spread):
            logger.debug("market_not_tradeable", match_id=game_state.match_id)
            return None

        # Determine trade direction
        if edge > 0:
            # Model favors team1 more than market -> BUY
            side = "BUY"
            limit_price = orderbook.best_ask
        else:
            # Model favors team2 more than market -> SELL
            side = "SELL"
            limit_price = orderbook.best_bid

        if limit_price is None:
            logger.debug("no_price_available", side=side)
            return None

        # Calculate position size
        if self.use_kelly_criterion:
            size = self._calculate_kelly_size(edge, limit_price, model_prob)
        else:
            # Fixed size with edge-based scaling
            size = min(self.max_position_size, self.max_position_size * abs(edge) / self.min_edge)

        # Check slippage
        avg_price, slippage_pct = orderbook.calculate_slippage(side, size)
        if slippage_pct > self.slippage_tolerance * 100:
            logger.warning(
                "slippage_too_high",
                slippage=slippage_pct,
                max=self.slippage_tolerance * 100
            )
            return None

        # Create trade signal
        signal = TradeSignal(
            match_id=game_state.match_id,
            game_number=game_state.game_number,
            token_id=token_id,
            side=side,
            size=size,
            limit_price=limit_price,
            edge=edge,
            model_prob=model_prob,
            market_prob=market_prob,
            game_state=game_state
        )

        logger.info(
            "trade_signal_generated",
            match_id=game_state.match_id,
            side=side,
            size=size,
            price=limit_price,
            edge=edge
        )

        return signal

    def _calculate_kelly_size(self, edge: float, price: float, win_prob: float) -> float:
        """Calculate position size using Kelly Criterion.

        Kelly formula: f = (bp - q) / b
        where:
          f = fraction of bankroll to bet
          b = odds received (decimal odds - 1)
          p = probability of winning
          q = probability of losing (1 - p)

        We use fractional Kelly (default 0.25) for safety.

        Args:
            edge: Edge (model_prob - market_prob)
            price: Market price
            win_prob: Model's win probability

        Returns:
            Position size in USD
        """
        # Convert price to decimal odds
        # In Polymarket, price IS the probability, so odds = 1/price - 1
        # But for Kelly, we need the payout odds
        if price <= 0 or price >= 1:
            return self.max_position_size * 0.1  # Fallback to small size

        # For binary outcomes on Polymarket:
        # If we buy at price p, we pay $p to potentially get $1 (payout = $1 - $p)
        # So decimal odds b = (1 - p) / p = 1/p - 1
        b = (1.0 / price) - 1.0

        p = win_prob
        q = 1 - p

        # Kelly fraction
        kelly = (b * p - q) / b

        # Apply fractional Kelly for safety
        kelly = kelly * self.kelly_fraction

        # Ensure non-negative
        kelly = max(0, kelly)

        # Convert to position size (cap at max_position_size)
        # Kelly gives us fraction of bankroll, we use max_position_size as reference
        size = kelly * self.max_position_size * 10  # Assume bankroll = 10x max position

        # Cap at max position size
        size = min(size, self.max_position_size)

        logger.debug(
            "kelly_sizing",
            edge=edge,
            price=price,
            win_prob=win_prob,
            kelly_fraction=kelly,
            size=size
        )

        return size
