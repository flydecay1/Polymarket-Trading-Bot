"""Match live LoL matches to Polymarket markets."""
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher
import structlog

from ..data_ingestion.game_state import GameState

logger = structlog.get_logger(__name__)


class MarketMatcher:
    """Match live games to Polymarket markets."""

    def __init__(self, team_aliases: Optional[Dict[str, List[str]]] = None):
        """Initialize market matcher.

        Args:
            team_aliases: Dictionary mapping canonical names to aliases
        """
        self.team_aliases = team_aliases or {
            "T1": ["T1", "SKT", "SK Telecom", "SKT T1"],
            "Gen.G": ["GenG", "Gen.G", "Gen. G", "GEN"],
            "DRX": ["DRX", "DragonX", "Dragon X"],
            "Dplus KIA": ["DK", "DAMWON", "DWG", "Dplus", "Dplus KIA"],
            "KT Rolster": ["KT", "KTR", "KT Rolster"],
            "Hanwha Life": ["HLE", "Hanwha", "Hanwha Life Esports"],
            "JD Gaming": ["JDG", "JD Gaming", "JD"],
            "BiliBili Gaming": ["BLG", "BiliBili", "BiliBili Gaming"],
            "LNG Esports": ["LNG", "LNG Esports"],
            "Top Esports": ["TES", "Top Esports", "Top"],
            "G2 Esports": ["G2", "G2 Esports"],
            "Fnatic": ["FNC", "Fnatic"],
            "Cloud9": ["C9", "Cloud9", "Cloud 9"],
            "Team Liquid": ["TL", "Team Liquid", "Liquid"],
        }

    def normalize_team_name(self, team_name: str) -> str:
        """Normalize team name using aliases.

        Args:
            team_name: Team name to normalize

        Returns:
            Normalized team name
        """
        team_lower = team_name.lower().strip()

        # Check if it matches any alias
        for canonical, aliases in self.team_aliases.items():
            for alias in aliases:
                if alias.lower() == team_lower:
                    return canonical

        # Return original if no match
        return team_name

    def fuzzy_match(self, str1: str, str2: str, threshold: float = 0.8) -> bool:
        """Check if two strings match using fuzzy matching.

        Args:
            str1: First string
            str2: Second string
            threshold: Similarity threshold (0.0 to 1.0)

        Returns:
            True if strings match above threshold
        """
        similarity = SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
        return similarity >= threshold

    def extract_teams_from_market(self, market: Dict[str, Any]) -> Optional[tuple[str, str]]:
        """Extract team names from market question.

        Args:
            market: Market data

        Returns:
            Tuple of (team1, team2) or None
        """
        question = market.get('question', '')
        description = market.get('description', '')

        # Common patterns in Polymarket questions:
        # "Will T1 beat Gen.G?"
        # "T1 vs Gen.G - Winner?"
        # "Who will win: T1 or Gen.G?"

        # Try to extract teams
        text = question + " " + description

        # Pattern: "X vs Y"
        if " vs " in text.lower() or " vs. " in text.lower():
            parts = text.lower().replace(" vs. ", " vs ").split(" vs ")
            if len(parts) >= 2:
                team1 = parts[0].strip().split()[-1]  # Last word before "vs"
                team2 = parts[1].strip().split()[0]   # First word after "vs"
                return (team1, team2)

        # Pattern: "Will X beat Y"
        if " beat " in text.lower():
            parts = text.lower().split(" beat ")
            if len(parts) >= 2:
                # Extract team names
                team1_words = parts[0].strip().split()
                team2_words = parts[1].strip().split()

                if team1_words and team2_words:
                    team1 = team1_words[-1]  # Last word before "beat"
                    team2 = team2_words[0]   # First word after "beat"
                    return (team1, team2)

        return None

    def find_matching_market(
        self,
        game_state: GameState,
        markets: List[Dict[str, Any]],
        fuzzy_threshold: float = 0.85
    ) -> Optional[Dict[str, Any]]:
        """Find Polymarket market matching a live game.

        Args:
            game_state: Live game state
            markets: List of available markets
            fuzzy_threshold: Similarity threshold for fuzzy matching

        Returns:
            Matching market or None
        """
        # Normalize team names from game state
        team1_normalized = self.normalize_team_name(game_state.team1_name)
        team2_normalized = self.normalize_team_name(game_state.team2_name)

        logger.debug(
            "matching_market",
            game_team1=game_state.team1_name,
            game_team2=game_state.team2_name,
            norm_team1=team1_normalized,
            norm_team2=team2_normalized
        )

        for market in markets:
            extracted_teams = self.extract_teams_from_market(market)

            if not extracted_teams:
                continue

            market_team1, market_team2 = extracted_teams

            # Normalize market team names
            market_team1_norm = self.normalize_team_name(market_team1)
            market_team2_norm = self.normalize_team_name(market_team2)

            # Check for exact match (either order)
            if (team1_normalized == market_team1_norm and team2_normalized == market_team2_norm) or \
               (team1_normalized == market_team2_norm and team2_normalized == market_team1_norm):
                logger.info("found_matching_market", market_id=market.get('condition_id'), question=market.get('question'))
                return market

            # Check for fuzzy match
            if (self.fuzzy_match(team1_normalized, market_team1_norm, fuzzy_threshold) and
                self.fuzzy_match(team2_normalized, market_team2_norm, fuzzy_threshold)) or \
               (self.fuzzy_match(team1_normalized, market_team2_norm, fuzzy_threshold) and
                self.fuzzy_match(team2_normalized, market_team1_norm, fuzzy_threshold)):
                logger.info("found_fuzzy_matching_market", market_id=market.get('condition_id'), question=market.get('question'))
                return market

        logger.warning("no_matching_market_found", team1=game_state.team1_name, team2=game_state.team2_name)
        return None

    def get_team1_token_id(self, market: Dict[str, Any], game_state: GameState) -> Optional[str]:
        """Get token ID for team1 in the market.

        Args:
            market: Matched market
            game_state: Game state

        Returns:
            Token ID for team1 or None
        """
        # This depends on how Polymarket structures their markets
        # Typically there are two outcome tokens per market

        tokens = market.get('tokens', [])
        if len(tokens) < 2:
            return None

        # Need to determine which token represents team1
        # This may require parsing token descriptions
        # For now, assume first token is "YES" (team1 wins)

        return tokens[0].get('token_id')
