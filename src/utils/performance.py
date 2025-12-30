"""Performance tracking and metrics."""
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    timestamp: datetime
    match_id: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    edge: float
    model_prob: float
    market_prob: float
    duration_seconds: float


class PerformanceTracker:
    """Track bot performance and calculate metrics."""

    def __init__(self):
        """Initialize performance tracker."""
        self.trades: List[TradeRecord] = []
        self.start_time = time.time()
        self.initial_capital = 0.0

    def record_trade(
        self,
        match_id: str,
        side: str,
        entry_price: float,
        exit_price: float,
        size: float,
        edge: float,
        model_prob: float,
        market_prob: float,
        entry_time: datetime,
        exit_time: datetime
    ) -> None:
        """Record a completed trade.

        Args:
            match_id: Match identifier
            side: BUY or SELL
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
            edge: Predicted edge
            model_prob: Model probability
            market_prob: Market probability
            entry_time: Entry timestamp
            exit_time: Exit timestamp
        """
        # Calculate P&L
        if side == "BUY":
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

        duration = (exit_time - entry_time).total_seconds()

        trade = TradeRecord(
            timestamp=exit_time,
            match_id=match_id,
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            pnl=pnl,
            edge=edge,
            model_prob=model_prob,
            market_prob=market_prob,
            duration_seconds=duration
        )

        self.trades.append(trade)

        logger.info(
            "trade_recorded",
            match_id=match_id,
            pnl=pnl,
            total_trades=len(self.trades)
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics.

        Returns:
            Dictionary of metrics
        """
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "sharpe_ratio": 0.0,
                "profit_factor": 0.0
            }

        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl <= 0)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # P&L metrics
        total_pnl = sum(t.pnl for t in self.trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [abs(t.pnl) for t in self.trades if t.pnl <= 0]

        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        max_win = max(wins) if wins else 0
        max_loss = max(losses) if losses else 0

        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = sum(losses) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Sharpe ratio (annualized)
        pnls = [t.pnl for t in self.trades]
        sharpe_ratio = 0.0
        if len(pnls) > 1:
            returns = np.array(pnls)
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

        # Edge realization
        avg_predicted_edge = np.mean([t.edge for t in self.trades])
        avg_realized_edge = avg_pnl / np.mean([t.size for t in self.trades]) if total_trades > 0 else 0
        edge_realization = avg_realized_edge / avg_predicted_edge if avg_predicted_edge != 0 else 0

        # Time metrics
        uptime_seconds = time.time() - self.start_time
        trades_per_hour = total_trades / (uptime_seconds / 3600) if uptime_seconds > 0 else 0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_win": max_win,
            "max_loss": max_loss,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "avg_predicted_edge": avg_predicted_edge,
            "avg_realized_edge": avg_realized_edge,
            "edge_realization": edge_realization,
            "uptime_hours": uptime_seconds / 3600,
            "trades_per_hour": trades_per_hour
        }

    def get_recent_performance(self, n: int = 10) -> Dict[str, Any]:
        """Get metrics for most recent N trades.

        Args:
            n: Number of recent trades

        Returns:
            Metrics dictionary
        """
        if not self.trades:
            return self.get_metrics()

        recent_trades = self.trades[-n:]

        winning = sum(1 for t in recent_trades if t.pnl > 0)
        total_pnl = sum(t.pnl for t in recent_trades)

        return {
            "recent_trades": len(recent_trades),
            "recent_wins": winning,
            "recent_win_rate": winning / len(recent_trades) if recent_trades else 0,
            "recent_pnl": total_pnl,
            "recent_avg_pnl": total_pnl / len(recent_trades) if recent_trades else 0
        }

    def print_summary(self) -> None:
        """Print performance summary to console."""
        metrics = self.get_metrics()

        print("\n" + "="*60)
        print("Performance Summary")
        print("="*60)
        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Win Rate: {metrics['win_rate']:.2%}")
        print(f"Total P&L: ${metrics['total_pnl']:+.2f}")
        print(f"\nPerformance Metrics:")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"\nTrade Analysis:")
        print(f"  Avg Win: ${metrics['avg_win']:.2f}")
        print(f"  Avg Loss: ${metrics['avg_loss']:.2f}")
        print(f"  Max Win: ${metrics['max_win']:.2f}")
        print(f"  Max Loss: ${metrics['max_loss']:.2f}")
        print(f"\nEdge Analysis:")
        print(f"  Predicted: {metrics['avg_predicted_edge']:.2%}")
        print(f"  Realized: {metrics['avg_realized_edge']:.2%}")
        print(f"  Realization: {metrics['edge_realization']:.2%}")
        print(f"\nOperational:")
        print(f"  Uptime: {metrics['uptime_hours']:.1f} hours")
        print(f"  Trade Rate: {metrics['trades_per_hour']:.1f}/hour")
        print("="*60 + "\n")
