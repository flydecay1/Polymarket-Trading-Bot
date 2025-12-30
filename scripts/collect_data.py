#!/usr/bin/env python3
"""Script to collect historical training data."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import Config, setup_logger
from src.probability_model import HistoricalDataCollector


def main():
    """Collect historical match data."""
    config = Config()
    logger = setup_logger("data_collector", level="INFO", console=True)

    logger.info("starting_data_collection")

    if not config.pandascore_api_key:
        print("ERROR: PANDASCORE_API_KEY not set in config/.env")
        sys.exit(1)

    # Initialize collector
    collector = HistoricalDataCollector(
        api_key=config.pandascore_api_key,
        output_dir="data/historical"
    )

    # Collect data
    leagues = config.get("probability_model.data_collection.leagues", ["LCK", "LPL", "LEC", "LCS"])
    max_games = config.get("probability_model.data_collection.max_games", 1000)

    print(f"\nCollecting up to {max_games} games from leagues: {', '.join(leagues)}")
    print("This may take a while...\n")

    df = collector.collect_training_data(
        max_games=max_games,
        leagues=leagues
    )

    print(f"\n✅ Collected {len(df)} game snapshots")
    print(f"📁 Saved to: data/historical/training_data.csv")

    # Show sample statistics
    if len(df) > 0:
        print("\nDataset Statistics:")
        print(f"  Total games: {len(df)}")
        print(f"  Average gold diff: {df['gold_diff'].mean():.0f}")
        print(f"  Average kill diff: {df['kill_diff'].mean():.1f}")
        print(f"  Team1 win rate: {df['did_team1_win'].mean():.1%}")


if __name__ == "__main__":
    main()
