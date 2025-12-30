"""Live match feed that polls for game state updates."""
import asyncio
import time
from typing import Callable, Dict, Optional, List
import structlog

from .pandascore_client import PandaScoreClient
from .game_state import GameState


logger = structlog.get_logger(__name__)


class LiveMatchFeed:
    """Live feed for LoL match data."""

    def __init__(
        self,
        client: PandaScoreClient,
        poll_interval: int = 2,
        material_change_thresholds: Optional[Dict[str, int]] = None
    ):
        """Initialize live match feed.

        Args:
            client: PandaScore client
            poll_interval: Seconds between polls
            material_change_thresholds: Thresholds for material changes
        """
        self.client = client
        self.poll_interval = poll_interval
        self.material_change_thresholds = material_change_thresholds or {
            'gold_diff': 500,
            'kills': 1,
            'towers': 1,
            'dragons': 1,
            'barons': 1,
            'inhibitors': 1
        }

        self.running = False
        self.last_states: Dict[str, GameState] = {}
        self.callbacks: List[Callable[[GameState], None]] = []

    def on_state_change(self, callback: Callable[[GameState], None]) -> None:
        """Register callback for state changes.

        Args:
            callback: Function to call when state changes
        """
        self.callbacks.append(callback)

    def _notify_callbacks(self, game_state: GameState) -> None:
        """Notify all callbacks of state change.

        Args:
            game_state: New game state
        """
        for callback in self.callbacks:
            try:
                callback(game_state)
            except Exception as e:
                logger.error("callback_error", error=str(e))

    async def start(self) -> None:
        """Start the live feed."""
        self.running = True
        logger.info("live_feed_started", poll_interval=self.poll_interval)

        while self.running:
            try:
                await self._poll_and_update()
                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error("poll_error", error=str(e))
                await asyncio.sleep(self.poll_interval)

    async def _poll_and_update(self) -> None:
        """Poll for updates and notify on material changes."""
        # Fetch current game states
        current_states = await asyncio.to_thread(self.client.get_live_game_states)

        for current_state in current_states:
            match_key = f"{current_state.match_id}_{current_state.game_number}"

            # Check if we have previous state
            if match_key in self.last_states:
                last_state = self.last_states[match_key]

                # Check for material change
                if current_state.has_material_change(last_state, self.material_change_thresholds):
                    logger.info(
                        "material_change_detected",
                        match_id=current_state.match_id,
                        game_number=current_state.game_number,
                        gold_diff=current_state.gold_diff,
                        kill_diff=current_state.kill_diff
                    )
                    self._notify_callbacks(current_state)

            else:
                # New match detected
                logger.info(
                    "new_match_detected",
                    match_id=current_state.match_id,
                    team1=current_state.team1_name,
                    team2=current_state.team2_name
                )
                self._notify_callbacks(current_state)

            # Update last state
            self.last_states[match_key] = current_state

        # Clean up finished matches
        self._cleanup_finished_matches(current_states)

    def _cleanup_finished_matches(self, current_states: List[GameState]) -> None:
        """Remove finished matches from tracking.

        Args:
            current_states: Current game states
        """
        current_keys = {f"{s.match_id}_{s.game_number}" for s in current_states}

        # Remove matches no longer in current states
        keys_to_remove = []
        for key in self.last_states:
            if key not in current_keys:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            logger.info("removing_finished_match", match_key=key)
            del self.last_states[key]

    def stop(self) -> None:
        """Stop the live feed."""
        self.running = False
        logger.info("live_feed_stopped")
