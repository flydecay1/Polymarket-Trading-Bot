"""Historical data collection for model training."""
import requests
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


class HistoricalDataCollector:
    """Collect historical LoL match data for training."""

    def __init__(self, api_key: str, output_dir: str = "data/historical"):
        """Initialize data collector.

        Args:
            api_key: PandaScore API key
            output_dir: Directory to save data
        """
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        })
        self.base_url = "https://api.pandascore.co"

    def fetch_past_matches(
        self,
        leagues: Optional[List[str]] = None,
        max_matches: int = 1000,
        per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch past matches from PandaScore.

        Args:
            leagues: List of league names to filter (e.g., ['LCK', 'LPL'])
            max_matches: Maximum number of matches to fetch
            per_page: Results per page

        Returns:
            List of match data
        """
        matches = []
        page = 1

        try:
            while len(matches) < max_matches:
                url = f"{self.base_url}/lol/matches/past"
                params = {
                    'page': page,
                    'per_page': min(per_page, 100)  # API limit
                }

                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                page_matches = response.json()

                if not page_matches:
                    break

                # Filter by league if specified
                if leagues:
                    page_matches = [
                        m for m in page_matches
                        if m.get('league', {}).get('name') in leagues
                    ]

                matches.extend(page_matches)
                logger.info("fetched_matches_page", page=page, count=len(page_matches))

                page += 1

                if len(page_matches) < per_page:
                    break

            logger.info("total_matches_fetched", count=len(matches))
            return matches[:max_matches]

        except requests.RequestException as e:
            logger.error("failed_to_fetch_matches", error=str(e))
            return matches

    def fetch_game_details(self, game_id: int) -> Optional[Dict[str, Any]]:
        """Fetch detailed game statistics.

        Args:
            game_id: Game ID

        Returns:
            Game details or None
        """
        try:
            url = f"{self.base_url}/lol/games/{game_id}"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error("failed_to_fetch_game", game_id=game_id, error=str(e))
            return None

    def process_game_snapshots(
        self,
        game_data: Dict[str, Any],
        match_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Process game data into training snapshots.

        For real-time prediction, we need snapshots at different game times.
        Since PandaScore may not provide minute-by-minute data, we create
        snapshots from final game state.

        Args:
            game_data: Game details
            match_data: Match metadata

        Returns:
            List of snapshot data points
        """
        snapshots = []

        try:
            # Extract final game state
            teams = game_data.get('teams', [])
            if len(teams) < 2:
                return snapshots

            team1 = teams[0]
            team2 = teams[1]

            # Determine winner
            winner_id = game_data.get('winner', {}).get('id')
            if not winner_id:
                return snapshots

            opponents = match_data.get('opponents', [])
            if len(opponents) < 2:
                return snapshots

            team1_id = opponents[0].get('opponent', {}).get('id')
            did_team1_win = 1 if winner_id == team1_id else 0

            # Create snapshot from final state
            # In production, you'd want game state at multiple timestamps
            snapshot = {
                'match_id': match_data.get('id'),
                'game_id': game_data.get('id'),
                'league': match_data.get('league', {}).get('name'),
                'game_time_minutes': (game_data.get('length', 0) or 0) / 60.0,
                'gold_diff': team1.get('gold', 0) - team2.get('gold', 0),
                'kill_diff': team1.get('kills', 0) - team2.get('kills', 0),
                'tower_diff': team1.get('towers', 0) - team2.get('towers', 0),
                'dragon_diff': team1.get('dragons', 0) - team2.get('dragons', 0),
                'baron_diff': team1.get('barons', 0) - team2.get('barons', 0),
                'inhib_diff': team1.get('inhibitors', 0) - team2.get('inhibitors', 0),
                'did_team1_win': did_team1_win
            }

            snapshots.append(snapshot)

        except Exception as e:
            logger.error("failed_to_process_snapshot", error=str(e))

        return snapshots

    def collect_training_data(
        self,
        max_games: int = 1000,
        leagues: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Collect and process training data.

        Args:
            max_games: Maximum games to collect
            leagues: League filter

        Returns:
            DataFrame with training data
        """
        logger.info("starting_data_collection", max_games=max_games)

        # Fetch matches
        matches = self.fetch_past_matches(leagues=leagues, max_matches=max_games)

        all_snapshots = []

        for i, match in enumerate(matches):
            if i % 50 == 0:
                logger.info("processing_matches", progress=f"{i}/{len(matches)}")

            games = match.get('games', [])

            for game in games:
                if not game.get('finished'):
                    continue

                game_id = game.get('id')
                if not game_id:
                    continue

                # Fetch detailed game data
                game_details = self.fetch_game_details(game_id)
                if not game_details:
                    continue

                # Process snapshots
                snapshots = self.process_game_snapshots(game_details, match)
                all_snapshots.extend(snapshots)

                # Stop if we have enough data
                if len(all_snapshots) >= max_games:
                    break

            if len(all_snapshots) >= max_games:
                break

        # Convert to DataFrame
        df = pd.DataFrame(all_snapshots)
        logger.info("data_collection_complete", rows=len(df))

        # Save to CSV
        output_file = self.output_dir / "training_data.csv"
        df.to_csv(output_file, index=False)
        logger.info("saved_training_data", file=str(output_file))

        return df

    def load_from_csv(self, filepath: str) -> pd.DataFrame:
        """Load training data from CSV.

        Args:
            filepath: Path to CSV file

        Returns:
            DataFrame with training data
        """
        df = pd.read_csv(filepath)
        logger.info("loaded_training_data", rows=len(df))
        return df
