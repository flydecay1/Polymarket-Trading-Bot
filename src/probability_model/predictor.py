"""Win probability prediction from game state."""
import numpy as np
from pathlib import Path
import joblib
from typing import Optional
import structlog

from ..data_ingestion.game_state import GameState

logger = structlog.get_logger(__name__)


class WinProbabilityPredictor:
    """Predict win probability from game state."""

    def __init__(self, model_path: Optional[str] = None, scaler_path: Optional[str] = None):
        """Initialize predictor.

        Args:
            model_path: Path to trained model
            scaler_path: Path to feature scaler
        """
        self.model = None
        self.scaler = None
        self.feature_names = [
            'gold_diff',
            'kill_diff',
            'tower_diff',
            'dragon_diff',
            'baron_diff',
            'inhib_diff',
            'game_time_minutes'
        ]

        if model_path and scaler_path:
            self.load(model_path, scaler_path)

    def load(self, model_path: str, scaler_path: str) -> None:
        """Load trained model and scaler.

        Args:
            model_path: Path to model file
            scaler_path: Path to scaler file
        """
        model_file = Path(model_path)
        scaler_file = Path(scaler_path)

        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        if not scaler_file.exists():
            raise FileNotFoundError(f"Scaler file not found: {scaler_path}")

        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        logger.info("loaded_model", model_path=model_path, scaler_path=scaler_path)

    def calculate_win_probability(self, game_state: GameState) -> float:
        """Calculate win probability for team1.

        Args:
            game_state: Current game state

        Returns:
            Probability that team1 wins (0.0 to 1.0)
        """
        if not self.model or not self.scaler:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Extract features
        features = np.array([[
            game_state.gold_diff,
            game_state.kill_diff,
            game_state.tower_diff,
            game_state.dragon_diff,
            game_state.baron_diff,
            game_state.inhib_diff,
            game_state.game_time_minutes
        ]])

        # Scale features
        features_scaled = self.scaler.transform(features)

        # Predict probability
        prob_team1_wins = self.model.predict_proba(features_scaled)[0][1]

        logger.debug(
            "predicted_probability",
            match_id=game_state.match_id,
            prob_team1_wins=prob_team1_wins,
            gold_diff=game_state.gold_diff,
            kill_diff=game_state.kill_diff
        )

        return float(prob_team1_wins)

    def get_edge(self, game_state: GameState, market_prob_team1: float) -> float:
        """Calculate edge between model and market.

        Args:
            game_state: Current game state
            market_prob_team1: Market's implied probability for team1

        Returns:
            Edge (positive means model favors team1 more than market)
        """
        model_prob = self.calculate_win_probability(game_state)
        edge = model_prob - market_prob_team1

        logger.info(
            "calculated_edge",
            match_id=game_state.match_id,
            model_prob=model_prob,
            market_prob=market_prob_team1,
            edge=edge
        )

        return edge
