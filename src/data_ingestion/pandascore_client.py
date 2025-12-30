"""PandaScore API client for fetching live LoL match data."""
import time
from typing import List, Dict, Any, Optional
import requests
import structlog

from .game_state import GameState, TeamState


logger = structlog.get_logger(__name__)


class PandaScoreClient:
    """Client for PandaScore API."""

    def __init__(self, api_key: str, base_url: str = "https://api.pandascore.co"):
        """Initialize PandaScore client.

        Args:
            api_key: PandaScore API key
            base_url: Base URL for API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        })

    def get_live_matches(self) -> List[Dict[str, Any]]:
        """Get currently live LoL matches.

        Returns:
            List of live match data
        """
        try:
            url = f"{self.base_url}/lol/matches/running"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            matches = response.json()
            logger.info("fetched_live_matches", count=len(matches))
            return matches

        except requests.RequestException as e:
            logger.error("failed_to_fetch_live_matches", error=str(e))
            return []

    def get_match_details(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed match data.

        Args:
            match_id: PandaScore match ID

        Returns:
            Match details or None if error
        """
        try:
            url = f"{self.base_url}/lol/matches/{match_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            logger.error("failed_to_fetch_match_details", match_id=match_id, error=str(e))
            return None

    def get_game_stats(self, game_id: int) -> Optional[Dict[str, Any]]:
        """Get live game statistics.

        Args:
            game_id: PandaScore game ID

        Returns:
            Game stats or None if error
        """
        try:
            url = f"{self.base_url}/lol/games/{game_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            logger.error("failed_to_fetch_game_stats", game_id=game_id, error=str(e))
            return None

    def parse_game_state(self, match_data: Dict[str, Any], game_data: Dict[str, Any]) -> Optional[GameState]:
        """Parse PandaScore data into GameState.

        Args:
            match_data: Match metadata
            game_data: Live game data

        Returns:
            GameState object or None if parsing fails
        """
        try:
            # Extract team names
            opponents = match_data.get('opponents', [])
            if len(opponents) < 2:
                logger.warning("insufficient_opponents", match_id=match_data.get('id'))
                return None

            team1_name = opponents[0].get('opponent', {}).get('name', 'Team1')
            team2_name = opponents[1].get('opponent', {}).get('name', 'Team2')

            # Extract game stats
            game_id = game_data.get('id', 0)
            game_time = game_data.get('length', 0) or 0  # in seconds
            is_finished = game_data.get('finished', False)
            winner_id = game_data.get('winner', {}).get('id') if is_finished else None

            # Extract team stats from game data
            teams = game_data.get('teams', [])

            team1_stats = TeamState()
            team2_stats = TeamState()

            if len(teams) >= 2:
                # Team 1 stats
                team1_stats = self._parse_team_stats(teams[0])
                # Team 2 stats
                team2_stats = self._parse_team_stats(teams[1])

            # Determine winner (1 or 2, 0 if ongoing)
            winner = 0
            if is_finished and winner_id:
                winner = 1 if winner_id == opponents[0].get('opponent', {}).get('id') else 2

            game_state = GameState(
                match_id=str(match_data.get('id', 0)),
                game_number=game_data.get('position', 1),
                game_time_seconds=game_time,
                team1_name=team1_name,
                team2_name=team2_name,
                team1=team1_stats,
                team2=team2_stats,
                is_finished=is_finished,
                winner=winner
            )

            return game_state

        except Exception as e:
            logger.error("failed_to_parse_game_state", error=str(e))
            return None

    def _parse_team_stats(self, team_data: Dict[str, Any]) -> TeamState:
        """Parse team statistics from PandaScore data.

        Args:
            team_data: Team data from API

        Returns:
            TeamState object
        """
        # PandaScore returns stats in various formats, adapt as needed
        # This is a simplified version - actual API structure may vary
        return TeamState(
            gold=team_data.get('gold', 0),
            kills=team_data.get('kills', 0),
            towers=team_data.get('towers', 0),
            dragons=team_data.get('dragons', 0),
            barons=team_data.get('barons', 0),
            inhibs=team_data.get('inhibitors', 0)
        )

    def get_live_game_states(self) -> List[GameState]:
        """Get current game states for all live matches.

        Returns:
            List of GameState objects
        """
        game_states = []

        live_matches = self.get_live_matches()

        for match in live_matches:
            match_id = match.get('id')
            games = match.get('games', [])

            # Find the currently running game
            running_game = None
            for game in games:
                if game.get('status') == 'running' or (not game.get('finished') and game.get('begin_at')):
                    running_game = game
                    break

            if running_game:
                game_id = running_game.get('id')
                # Fetch detailed game stats
                game_data = self.get_game_stats(game_id)

                if game_data:
                    game_state = self.parse_game_state(match, game_data)
                    if game_state:
                        game_states.append(game_state)

        logger.info("parsed_game_states", count=len(game_states))
        return game_states
