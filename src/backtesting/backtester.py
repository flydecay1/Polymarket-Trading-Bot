"""Backtesting engine for strategy validation."""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import structlog

from ..data_ingestion.game_state import GameState
from ..probability_model import WinProbabilityPredictor
from ..arbitrage.strategy import ArbitrageStrategy, TradeSignal
from ..polymarket.orderbook import OrderBook

logger = structlog.get_logger(__name__)


@dataclass
class Trade:
    """Record of a simulated trade."""
    timestamp: datetime
    match_id: str
    side: str  # BUY or SELL
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    edge: float
    model_prob: float
    market_prob: float
    game_time: float
    outcome: str  # WIN or LOSS


@dataclass
class BacktestResults:
    """Backtest performance results."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    total_pnl: float = 0.0
    total_return: float = 0.0

    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0

    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0

    avg_edge: float = 0.0
    edge_realization: float = 0.0  # Actual edge vs predicted

    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

    def __str__(self) -> str:
        """Format results as string."""
        return f"""
Backtest Results
================
Total Trades: {self.total_trades}
Win Rate: {self.win_rate:.2%}
Total P&L: ${self.total_pnl:.2f}
Total Return: {self.total_return:.2%}

Performance Metrics:
  Sharpe Ratio: {self.sharpe_ratio:.2f}
  Max Drawdown: {self.max_drawdown:.2%}

Trade Analysis:
  Winning Trades: {self.winning_trades} (Avg: ${self.avg_win:.2f})
  Losing Trades: {self.losing_trades} (Avg: ${self.avg_loss:.2f})

Edge Analysis:
  Avg Predicted Edge: {self.avg_edge:.2%}
  Edge Realization: {self.edge_realization:.2%}
"""


class Backtester:
    """Backtest trading strategies on historical data."""

    def __init__(
        self,
        predictor: WinProbabilityPredictor,
        strategy: ArbitrageStrategy,
        initial_capital: float = 10000.0,
        commission: float = 0.001,  # 0.1% per trade
        slippage: float = 0.002  # 0.2% slippage
    ):
        """Initialize backtester.

        Args:
            predictor: Win probability predictor
            strategy: Trading strategy
            initial_capital: Starting capital
            commission: Commission rate per trade
            slippage: Average slippage per trade
        """
        self.predictor = predictor
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

        self.trades: List[Trade] = []
        self.capital = initial_capital

    def run(self, merged_df: pd.DataFrame) -> BacktestResults:
        """Run backtest on historical data.

        Args:
            merged_df: DataFrame with match data and market prices

        Returns:
            Backtest results
        """
        logger.info("starting_backtest", rows=len(merged_df))

        self.trades = []
        self.capital = self.initial_capital
        equity_curve = [self.initial_capital]

        # Group by match
        for match_id in merged_df['match_id'].unique():
            match_data = merged_df[merged_df['match_id'] == match_id].sort_values('timestamp')

            # Simulate this match
            match_pnl = self._simulate_match(match_data)
            self.capital += match_pnl
            equity_curve.append(self.capital)

        # Calculate results
        results = self._calculate_results(equity_curve)

        logger.info(
            "backtest_complete",
            trades=results.total_trades,
            win_rate=results.win_rate,
            total_pnl=results.total_pnl
        )

        return results

    def _simulate_match(self, match_data: pd.DataFrame) -> float:
        """Simulate trading for a single match.

        Args:
            match_data: Match data sorted by timestamp

        Returns:
            P&L for this match
        """
        match_pnl = 0.0
        position = None  # Current open position

        for idx, row in match_data.iterrows():
            # Skip if missing required data
            if pd.isna(row.get('market_prob_team1')):
                continue

            # Skip early game (< 10 min)
            if row['game_time_seconds'] < 600:
                continue

            # Create GameState from row
            game_state = self._row_to_game_state(row)
            if not game_state:
                continue

            # Get model probability
            try:
                model_prob = self.predictor.calculate_win_probability(game_state)
            except Exception as e:
                logger.error("prediction_error", error=str(e))
                continue

            # Create mock orderbook from market data
            market_prob = row['market_prob_team1']
            orderbook = self._create_mock_orderbook(market_prob)

            # Check if we should open a position
            if position is None:
                signal = self.strategy.evaluate(
                    game_state=game_state,
                    model_prob=model_prob,
                    orderbook=orderbook,
                    token_id="mock_token"
                )

                if signal:
                    # Open position
                    position = {
                        'side': signal.side,
                        'entry_price': signal.limit_price,
                        'size': signal.size,
                        'edge': signal.edge,
                        'model_prob': model_prob,
                        'market_prob': market_prob,
                        'entry_time': row['timestamp'],
                        'game_time': game_state.game_time_minutes
                    }

            # Check if game finished - close position
            if position and row.get('is_finished', False):
                # Determine exit price based on outcome
                winner = int(row.get('winner', 0))

                if position['side'] == 'BUY':
                    # We bought team1 to win
                    exit_price = 1.0 if winner == 1 else 0.0
                else:
                    # We sold team1 to win (bet on team2)
                    exit_price = 0.0 if winner == 1 else 1.0

                # Apply slippage and commission
                entry_cost = position['entry_price'] * position['size']
                exit_value = exit_price * position['size']

                # Adjust for slippage (worse fill)
                if position['side'] == 'BUY':
                    entry_cost *= (1 + self.slippage)
                else:
                    exit_value *= (1 - self.slippage)

                # Calculate P&L
                if position['side'] == 'BUY':
                    pnl = exit_value - entry_cost
                else:
                    pnl = entry_cost - exit_value

                # Subtract commission (both sides)
                pnl -= (entry_cost + exit_value) * self.commission

                # Record trade
                trade = Trade(
                    timestamp=row['timestamp'],
                    match_id=str(row['match_id']),
                    side=position['side'],
                    entry_price=position['entry_price'],
                    exit_price=exit_price,
                    size=position['size'],
                    pnl=pnl,
                    edge=position['edge'],
                    model_prob=position['model_prob'],
                    market_prob=position['market_prob'],
                    game_time=position['game_time'],
                    outcome='WIN' if pnl > 0 else 'LOSS'
                )

                self.trades.append(trade)
                match_pnl += pnl

                # Clear position
                position = None

        return match_pnl

    def _row_to_game_state(self, row: pd.Series) -> Optional[GameState]:
        """Convert DataFrame row to GameState."""
        try:
            return GameState.from_dict({
                'match_id': str(row['match_id']),
                'game_number': int(row.get('game_number', 1)),
                'game_time_seconds': int(row['game_time_seconds']),
                'team1_name': row['team1_name'],
                'team2_name': row['team2_name'],
                'team1': {
                    'gold': int(row.get('team1_gold', 0)),
                    'kills': int(row.get('team1_kills', 0)),
                    'towers': int(row.get('team1_towers', 0)),
                    'dragons': int(row.get('team1_dragons', 0)),
                    'barons': int(row.get('team1_barons', 0)),
                    'inhibs': int(row.get('team1_inhibs', 0))
                },
                'team2': {
                    'gold': int(row.get('team2_gold', 0)),
                    'kills': int(row.get('team2_kills', 0)),
                    'towers': int(row.get('team2_towers', 0)),
                    'dragons': int(row.get('team2_dragons', 0)),
                    'barons': int(row.get('team2_barons', 0)),
                    'inhibs': int(row.get('team2_inhibs', 0))
                },
                'timestamp': row['timestamp'].isoformat(),
                'is_finished': bool(row.get('is_finished', False)),
                'winner': int(row.get('winner', 0))
            })
        except Exception as e:
            logger.error("failed_to_create_game_state", error=str(e))
            return None

    def _create_mock_orderbook(self, market_prob: float) -> OrderBook:
        """Create mock orderbook from market probability."""
        spread = 0.01
        bid = market_prob - spread / 2
        ask = market_prob + spread / 2

        orderbook_data = {
            'bids': [{'price': bid, 'size': 1000}],
            'asks': [{'price': ask, 'size': 1000}]
        }

        return OrderBook(orderbook_data)

    def _calculate_results(self, equity_curve: List[float]) -> BacktestResults:
        """Calculate backtest results from trades.

        Args:
            equity_curve: List of capital over time

        Returns:
            BacktestResults object
        """
        if not self.trades:
            return BacktestResults()

        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl <= 0)

        total_pnl = sum(t.pnl for t in self.trades)
        total_return = (self.capital - self.initial_capital) / self.initial_capital

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # Average win/loss
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [t.pnl for t in self.trades if t.pnl <= 0]

        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0

        # Sharpe ratio (assuming daily trades)
        returns = np.diff(equity_curve) / equity_curve[:-1]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0

        # Max drawdown
        peak = equity_curve[0]
        max_drawdown = 0
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Edge analysis
        avg_edge = np.mean([t.edge for t in self.trades])
        # Edge realization = actual edge captured
        edge_realization = total_return / (avg_edge * total_trades) if total_trades > 0 else 0

        return BacktestResults(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            total_return=total_return,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            avg_edge=avg_edge,
            edge_realization=edge_realization,
            trades=self.trades,
            equity_curve=equity_curve
        )
