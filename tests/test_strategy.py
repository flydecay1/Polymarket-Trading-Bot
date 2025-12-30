"""Tests for arbitrage strategy."""
import pytest
from datetime import datetime

from src.arbitrage.strategy import ArbitrageStrategy
from src.data_ingestion.game_state import GameState, TeamState
from src.polymarket.orderbook import OrderBook


def create_test_game_state():
    """Create a test game state."""
    team1 = TeamState(gold=15000, kills=10, towers=3, dragons=2)
    team2 = TeamState(gold=12000, kills=7, towers=2, dragons=1)

    return GameState(
        match_id="test_123",
        game_number=1,
        game_time_seconds=1200,
        team1_name="T1",
        team2_name="GenG",
        team1=team1,
        team2=team2
    )


def create_test_orderbook(midpoint=0.5):
    """Create a test orderbook."""
    bid_price = midpoint - 0.01
    ask_price = midpoint + 0.01

    orderbook_data = {
        'bids': [
            {'price': bid_price, 'size': 1000},
            {'price': bid_price - 0.02, 'size': 500}
        ],
        'asks': [
            {'price': ask_price, 'size': 1000},
            {'price': ask_price + 0.02, 'size': 500}
        ]
    }

    return OrderBook(orderbook_data)


def test_strategy_initialization():
    """Test strategy initialization."""
    strategy = ArbitrageStrategy(
        min_edge=0.05,
        max_position_size=100.0
    )

    assert strategy.min_edge == 0.05
    assert strategy.max_position_size == 100.0


def test_positive_edge_buy_signal():
    """Test buy signal on positive edge."""
    strategy = ArbitrageStrategy(min_edge=0.05)
    game_state = create_test_game_state()

    # Model prob 0.6, market prob 0.5 → edge = 0.1 (>0.05) → BUY
    model_prob = 0.6
    orderbook = create_test_orderbook(midpoint=0.5)

    signal = strategy.evaluate(
        game_state=game_state,
        model_prob=model_prob,
        orderbook=orderbook,
        token_id="test_token"
    )

    assert signal is not None
    assert signal.side == "BUY"
    assert signal.edge == 0.1
    assert signal.model_prob == 0.6
    assert signal.market_prob == 0.5


def test_negative_edge_sell_signal():
    """Test sell signal on negative edge."""
    strategy = ArbitrageStrategy(min_edge=0.05)
    game_state = create_test_game_state()

    # Model prob 0.3, market prob 0.5 → edge = -0.2 → SELL
    model_prob = 0.3
    orderbook = create_test_orderbook(midpoint=0.5)

    signal = strategy.evaluate(
        game_state=game_state,
        model_prob=model_prob,
        orderbook=orderbook,
        token_id="test_token"
    )

    assert signal is not None
    assert signal.side == "SELL"
    assert signal.edge == -0.2


def test_insufficient_edge_no_signal():
    """Test no signal when edge is too small."""
    strategy = ArbitrageStrategy(min_edge=0.05)
    game_state = create_test_game_state()

    # Edge only 0.02 < 0.05 threshold
    model_prob = 0.52
    orderbook = create_test_orderbook(midpoint=0.5)

    signal = strategy.evaluate(
        game_state=game_state,
        model_prob=model_prob,
        orderbook=orderbook,
        token_id="test_token"
    )

    assert signal is None


def test_wide_spread_no_signal():
    """Test no signal when spread is too wide."""
    strategy = ArbitrageStrategy(min_edge=0.05, max_spread=0.02)
    game_state = create_test_game_state()

    # Create orderbook with wide spread
    orderbook_data = {
        'bids': [{'price': 0.45, 'size': 1000}],
        'asks': [{'price': 0.55, 'size': 1000}]  # Spread = 0.10
    }
    orderbook = OrderBook(orderbook_data)

    model_prob = 0.7  # Good edge
    signal = strategy.evaluate(
        game_state=game_state,
        model_prob=model_prob,
        orderbook=orderbook,
        token_id="test_token"
    )

    assert signal is None


def test_low_liquidity_no_signal():
    """Test no signal when liquidity is too low."""
    strategy = ArbitrageStrategy(min_edge=0.05, min_liquidity=500.0)
    game_state = create_test_game_state()

    # Create orderbook with low liquidity
    orderbook_data = {
        'bids': [{'price': 0.49, 'size': 100}],  # Only 100
        'asks': [{'price': 0.51, 'size': 100}]
    }
    orderbook = OrderBook(orderbook_data)

    model_prob = 0.7
    signal = strategy.evaluate(
        game_state=game_state,
        model_prob=model_prob,
        orderbook=orderbook,
        token_id="test_token"
    )

    assert signal is None
