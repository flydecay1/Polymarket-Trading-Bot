"""Main arbitrage engine that coordinates all components."""
import asyncio
from typing import Dict, Any, List, Optional, Set
import structlog

from ..data_ingestion import LiveMatchFeed, GameState, PandaScoreClient
from ..probability_model import WinProbabilityPredictor
from ..polymarket import PolymarketClient, OrderBook, MarketMatcher
from .strategy import ArbitrageStrategy, TradeSignal

logger = structlog.get_logger(__name__)


class ArbitrageEngine:
    """Main arbitrage engine."""

    def __init__(
        self,
        pandascore_client: PandaScoreClient,
        polymarket_client: PolymarketClient,
        predictor: WinProbabilityPredictor,
        strategy: ArbitrageStrategy,
        market_matcher: MarketMatcher
    ):
        """Initialize arbitrage engine.

        Args:
            pandascore_client: PandaScore data client
            polymarket_client: Polymarket trading client
            predictor: Win probability predictor
            strategy: Trading strategy
            market_matcher: Market matching logic
        """
        self.pandascore_client = pandascore_client
        self.polymarket_client = polymarket_client
        self.predictor = predictor
        self.strategy = strategy
        self.market_matcher = market_matcher

        self.live_feed: Optional[LiveMatchFeed] = None
        self.running = False

        # Track active positions to avoid duplicate trades
        self.active_positions: Set[str] = set()

        # Risk management
        self.total_exposure = 0.0
        self.max_total_exposure = 1000.0

    def setup_live_feed(self, poll_interval: int = 2) -> None:
        """Set up live match feed.

        Args:
            poll_interval: Polling interval in seconds
        """
        self.live_feed = LiveMatchFeed(
            client=self.pandascore_client,
            poll_interval=poll_interval
        )

        # Register callback for state changes
        self.live_feed.on_state_change(self._on_game_state_update)

        logger.info("live_feed_configured", poll_interval=poll_interval)

    async def _on_game_state_update(self, game_state: GameState) -> None:
        """Handle game state updates.

        Args:
            game_state: Updated game state
        """
        try:
            logger.info(
                "game_state_update",
                match_id=game_state.match_id,
                game_number=game_state.game_number,
                team1=game_state.team1_name,
                team2=game_state.team2_name,
                gold_diff=game_state.gold_diff,
                time=game_state.game_time_minutes
            )

            # Skip if game too early
            if game_state.game_time_minutes < 10:
                logger.debug("game_too_early", time=game_state.game_time_minutes)
                return

            # Skip if game finished
            if game_state.is_finished:
                logger.debug("game_finished", match_id=game_state.match_id)
                return

            # Check for arbitrage opportunity
            await self._check_arbitrage_opportunity(game_state)

        except Exception as e:
            logger.error("error_handling_game_state", error=str(e))

    async def _check_arbitrage_opportunity(self, game_state: GameState) -> None:
        """Check for arbitrage opportunity and execute if found.

        Args:
            game_state: Current game state
        """
        try:
            # Get win probability from model
            model_prob = self.predictor.calculate_win_probability(game_state)

            logger.debug(
                "calculated_probability",
                match_id=game_state.match_id,
                model_prob=model_prob
            )

            # Find matching Polymarket market
            esports_markets = await asyncio.to_thread(
                self.polymarket_client.get_esports_markets
            )

            matching_market = self.market_matcher.find_matching_market(
                game_state,
                esports_markets
            )

            if not matching_market:
                logger.debug("no_matching_market", match_id=game_state.match_id)
                return

            # Get token ID for team1
            token_id = self.market_matcher.get_team1_token_id(matching_market, game_state)

            if not token_id:
                logger.warning("no_token_id", market_id=matching_market.get('condition_id'))
                return

            # Get orderbook
            orderbook_data = await asyncio.to_thread(
                self.polymarket_client.get_orderbook,
                token_id
            )

            orderbook = OrderBook(orderbook_data)

            # Evaluate opportunity
            signal = self.strategy.evaluate(
                game_state=game_state,
                model_prob=model_prob,
                orderbook=orderbook,
                token_id=token_id
            )

            if signal:
                await self._execute_trade(signal)

        except Exception as e:
            logger.error("error_checking_opportunity", error=str(e))

    async def _execute_trade(self, signal: TradeSignal) -> None:
        """Execute a trade signal.

        Args:
            signal: Trade signal to execute
        """
        try:
            # Check if we already have a position for this match
            position_key = f"{signal.match_id}_{signal.game_number}"

            if position_key in self.active_positions:
                logger.debug("position_already_exists", position_key=position_key)
                return

            # Check risk limits
            if self.total_exposure + signal.size > self.max_total_exposure:
                logger.warning(
                    "exposure_limit_exceeded",
                    current=self.total_exposure,
                    max=self.max_total_exposure
                )
                return

            logger.info(
                "executing_trade",
                match_id=signal.match_id,
                side=signal.side,
                size=signal.size,
                price=signal.limit_price,
                edge=signal.edge
            )

            # Place order
            order_response = await asyncio.to_thread(
                self.polymarket_client.place_order,
                token_id=signal.token_id,
                side=signal.side,
                size=signal.size,
                price=signal.limit_price
            )

            if order_response:
                # Track position
                self.active_positions.add(position_key)
                self.total_exposure += signal.size

                logger.info(
                    "trade_executed",
                    order_id=order_response.get('orderID'),
                    match_id=signal.match_id,
                    side=signal.side,
                    size=signal.size,
                    total_exposure=self.total_exposure
                )
            else:
                logger.error("trade_execution_failed", signal=signal)

        except Exception as e:
            logger.error("error_executing_trade", error=str(e))

    async def start(self) -> None:
        """Start the arbitrage engine."""
        if not self.live_feed:
            raise RuntimeError("Live feed not configured. Call setup_live_feed() first.")

        self.running = True
        logger.info("arbitrage_engine_started")

        # Start live feed
        await self.live_feed.start()

    def stop(self) -> None:
        """Stop the arbitrage engine."""
        self.running = False

        if self.live_feed:
            self.live_feed.stop()

        logger.info("arbitrage_engine_stopped")

    async def run_forever(self) -> None:
        """Run the engine indefinitely."""
        try:
            await self.start()
        except KeyboardInterrupt:
            logger.info("keyboard_interrupt_received")
            self.stop()
        except Exception as e:
            logger.error("engine_error", error=str(e))
            self.stop()
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get engine status.

        Returns:
            Status dictionary
        """
        return {
            'running': self.running,
            'active_positions': len(self.active_positions),
            'total_exposure': self.total_exposure,
            'max_exposure': self.max_total_exposure
        }
