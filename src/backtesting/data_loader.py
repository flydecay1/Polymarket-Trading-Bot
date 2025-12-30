"""Historical data loader for backtesting."""
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from ..data_ingestion.game_state import GameState

logger = structlog.get_logger(__name__)


class BacktestDataLoader:
    """Load historical match and market data for backtesting."""

    def __init__(self, data_dir: str = "data/backtest"):
        """Initialize data loader.

        Args:
            data_dir: Directory containing backtest data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_historical_matches(self, filepath: str) -> pd.DataFrame:
        """Load historical match data.

        Expected columns:
        - match_id, game_number, timestamp, game_time_seconds
        - team1_name, team2_name
        - team1_gold, team1_kills, team1_towers, etc.
        - team2_gold, team2_kills, team2_towers, etc.
        - is_finished, winner

        Args:
            filepath: Path to CSV file

        Returns:
            DataFrame with match data
        """
        df = pd.read_csv(filepath)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        logger.info("loaded_historical_matches", rows=len(df), file=filepath)
        return df

    def load_market_prices(self, filepath: str) -> pd.DataFrame:
        """Load historical market prices.

        Expected columns:
        - match_id, timestamp, market_prob_team1, best_bid, best_ask

        Args:
            filepath: Path to CSV file

        Returns:
            DataFrame with market prices
        """
        df = pd.read_csv(filepath)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        logger.info("loaded_market_prices", rows=len(df), file=filepath)
        return df

    def create_game_states_from_df(self, df: pd.DataFrame) -> List[GameState]:
        """Convert DataFrame rows to GameState objects.

        Args:
            df: Match data DataFrame

        Returns:
            List of GameState objects
        """
        game_states = []

        for _, row in df.iterrows():
            try:
                game_state = GameState.from_dict({
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
                game_states.append(game_state)

            except Exception as e:
                logger.error("failed_to_parse_game_state", error=str(e), row=row.to_dict())

        logger.info("created_game_states", count=len(game_states))
        return game_states

    def merge_match_and_market_data(
        self,
        matches_df: pd.DataFrame,
        markets_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Merge match data with market prices.

        Args:
            matches_df: Match data
            markets_df: Market prices

        Returns:
            Merged DataFrame
        """
        # Merge on match_id and nearest timestamp
        merged = pd.merge_asof(
            matches_df.sort_values('timestamp'),
            markets_df.sort_values('timestamp'),
            on='timestamp',
            by='match_id',
            direction='nearest',
            tolerance=pd.Timedelta('10s')  # Max 10s difference
        )

        logger.info("merged_data", rows=len(merged))
        return merged
