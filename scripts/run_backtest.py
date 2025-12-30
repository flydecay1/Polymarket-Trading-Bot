#!/usr/bin/env python3
"""Run backtest on historical data."""
import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import Config, setup_logger
from src.probability_model import WinProbabilityPredictor
from src.arbitrage.strategy import ArbitrageStrategy
from src.backtesting import Backtester, BacktestDataLoader


def main():
    """Run backtest."""
    config = Config()
    logger = setup_logger("backtester", level="INFO", console=True)

    logger.info("starting_backtest")

    # Check if model exists
    model_path = Path(config.model_path)
    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}")
        print("Please run 'python scripts/train_model.py' first")
        sys.exit(1)

    # Load model
    print("\n📊 Loading model...")
    predictor = WinProbabilityPredictor(
        model_path=config.model_path,
        scaler_path=config.feature_scaler_path
    )

    # Create strategy
    print("⚙️  Configuring strategy...")
    strategy = ArbitrageStrategy(
        min_edge=config.get("arbitrage.strategy.min_edge", 0.05),
        max_position_size=config.get("arbitrage.strategy.max_position_size", 100.0),
        min_liquidity=config.get("arbitrage.strategy.min_liquidity", 500.0),
        max_spread=config.get("arbitrage.strategy.max_spread", 0.02),
        use_kelly_criterion=True,
        kelly_fraction=0.25
    )

    # Load backtest data
    print("📥 Loading backtest data...")
    data_loader = BacktestDataLoader()

    # Check if backtest data exists
    matches_file = Path("data/backtest/matches.csv")
    markets_file = Path("data/backtest/markets.csv")

    if not matches_file.exists() or not markets_file.exists():
        print(f"\n⚠️  Backtest data not found!")
        print(f"Expected files:")
        print(f"  - {matches_file}")
        print(f"  - {markets_file}")
        print(f"\nPlease prepare backtest data with historical match states and market prices.")
        print(f"See docs for format requirements.")
        sys.exit(1)

    matches_df = data_loader.load_historical_matches(str(matches_file))
    markets_df = data_loader.load_market_prices(str(markets_file))

    print(f"✅ Loaded {len(matches_df)} match snapshots")
    print(f"✅ Loaded {len(markets_df)} market price snapshots")

    # Merge data
    print("\n🔗 Merging match and market data...")
    merged_df = data_loader.merge_match_and_market_data(matches_df, markets_df)
    print(f"✅ Merged {len(merged_df)} snapshots")

    # Create backtester
    backtester = Backtester(
        predictor=predictor,
        strategy=strategy,
        initial_capital=10000.0,
        commission=0.001,  # 0.1%
        slippage=0.002  # 0.2%
    )

    # Run backtest
    print("\n🚀 Running backtest...\n")
    results = backtester.run(merged_df)

    # Print results
    print(results)

    # Save results
    output_file = Path("data/backtest/results.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    trades_df = pd.DataFrame([
        {
            'timestamp': t.timestamp,
            'match_id': t.match_id,
            'side': t.side,
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'size': t.size,
            'pnl': t.pnl,
            'edge': t.edge
        }
        for t in results.trades
    ])

    trades_df.to_csv(output_file, index=False)
    print(f"💾 Saved detailed results to {output_file}")


if __name__ == "__main__":
    main()
