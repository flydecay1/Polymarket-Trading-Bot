#!/usr/bin/env python3
"""Main entry point for the Polymarket LoL arbitrage bot."""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import Config, setup_logger
from src.data_ingestion import PandaScoreClient
from src.probability_model import WinProbabilityPredictor
from src.polymarket import PolymarketClient, MarketMatcher
from src.arbitrage import ArbitrageEngine, ArbitrageStrategy


def main():
    """Run the arbitrage bot."""
    # Load configuration
    config = Config()

    # Setup logging
    logger = setup_logger(
        name="arbitrage_bot",
        level=config.get("logging.level", "INFO"),
        log_file=config.get("logging.file", "logs/arbitrage_bot.log"),
        console=config.get("logging.console", True)
    )

    logger.info("starting_polymarket_arbitrage_bot", version="0.1.0")

    # Validate configuration
    if not config.pandascore_api_key:
        logger.error("missing_pandascore_api_key")
        print("ERROR: PANDASCORE_API_KEY not set in config/.env")
        print("Please copy config/.env.example to config/.env and add your API keys")
        sys.exit(1)

    if not config.wallet_private_key:
        logger.error("missing_wallet_private_key")
        print("ERROR: WALLET_PRIVATE_KEY not set in config/.env")
        print("Please copy config/.env.example to config/.env and add your credentials")
        sys.exit(1)

    # Check if model exists
    model_path = Path(config.model_path)
    if not model_path.exists():
        logger.error("model_not_found", path=str(model_path))
        print(f"ERROR: Model not found at {model_path}")
        print("Please run 'python scripts/train_model.py' first to train the model")
        sys.exit(1)

    try:
        # Initialize components
        logger.info("initializing_components")

        # Data ingestion
        pandascore_client = PandaScoreClient(
            api_key=config.pandascore_api_key,
            base_url=config.get("data_ingestion.pandascore.base_url", "https://api.pandascore.co")
        )

        # Win probability model
        predictor = WinProbabilityPredictor(
            model_path=config.model_path,
            scaler_path=config.feature_scaler_path
        )

        # Polymarket client
        polymarket_client = PolymarketClient(
            api_key=config.polymarket_api_key,
            api_secret=config.polymarket_secret,
            api_passphrase=config.polymarket_passphrase,
            private_key=config.wallet_private_key,
            chain_id=config.chain_id
        )

        # Market matcher
        team_aliases = config.get("polymarket.market_matching.team_aliases", {})
        market_matcher = MarketMatcher(team_aliases=team_aliases)

        # Trading strategy
        strategy = ArbitrageStrategy(
            min_edge=config.get("arbitrage.strategy.min_edge", 0.05),
            max_position_size=config.get("arbitrage.strategy.max_position_size", 100.0),
            min_liquidity=config.get("arbitrage.strategy.min_liquidity", 500.0),
            max_spread=config.get("arbitrage.strategy.max_spread", 0.02),
            slippage_tolerance=config.get("arbitrage.execution.slippage_tolerance", 0.01)
        )

        # Arbitrage engine
        engine = ArbitrageEngine(
            pandascore_client=pandascore_client,
            polymarket_client=polymarket_client,
            predictor=predictor,
            strategy=strategy,
            market_matcher=market_matcher
        )

        # Set up live feed
        poll_interval = config.get("data_ingestion.pandascore.poll_interval", 2)
        engine.setup_live_feed(poll_interval=poll_interval)

        # Set risk limits
        engine.max_total_exposure = config.get("arbitrage.risk_management.max_total_exposure", 1000.0)

        logger.info("components_initialized")
        logger.info("engine_configuration", status=engine.get_status())

        # Run the engine
        logger.info("starting_engine")
        print("\n" + "="*60)
        print("🚀 Polymarket LoL Arbitrage Bot Started")
        print("="*60)
        print(f"Min Edge: {strategy.min_edge * 100:.1f}%")
        print(f"Max Position Size: ${strategy.max_position_size:.2f}")
        print(f"Max Total Exposure: ${engine.max_total_exposure:.2f}")
        print(f"Poll Interval: {poll_interval}s")
        print("="*60)
        print("\nMonitoring live matches for arbitrage opportunities...")
        print("Press Ctrl+C to stop\n")

        # Run forever
        asyncio.run(engine.run_forever())

    except KeyboardInterrupt:
        logger.info("shutdown_requested")
        print("\n\nShutting down gracefully...")

    except Exception as e:
        logger.error("fatal_error", error=str(e), exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)

    finally:
        logger.info("bot_stopped")
        print("Bot stopped.")


if __name__ == "__main__":
    main()
