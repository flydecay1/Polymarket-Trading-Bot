"""Game state models for League of Legends matches."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any


@dataclass
class TeamState:
    """State of a single team in a LoL match."""

    gold: int = 0
    kills: int = 0
    towers: int = 0
    dragons: int = 0
    barons: int = 0
    inhibs: int = 0

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            'gold': self.gold,
            'kills': self.kills,
            'towers': self.towers,
            'dragons': self.dragons,
            'barons': self.barons,
            'inhibs': self.inhibs
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TeamState':
        """Create from dictionary."""
        return cls(
            gold=data.get('gold', 0),
            kills=data.get('kills', 0),
            towers=data.get('towers', 0),
            dragons=data.get('dragons', 0),
            barons=data.get('barons', 0),
            inhibs=data.get('inhibs', 0)
        )


@dataclass
class GameState:
    """Complete game state for a LoL match."""

    match_id: str
    game_number: int
    game_time_seconds: int
    team1_name: str
    team2_name: str
    team1: TeamState = field(default_factory=TeamState)
    team2: TeamState = field(default_factory=TeamState)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    is_finished: bool = False
    winner: int = 0  # 0 = ongoing, 1 = team1, 2 = team2

    @property
    def game_time_minutes(self) -> float:
        """Get game time in minutes."""
        return self.game_time_seconds / 60.0

    @property
    def gold_diff(self) -> int:
        """Get gold differential (team1 - team2)."""
        return self.team1.gold - self.team2.gold

    @property
    def kill_diff(self) -> int:
        """Get kill differential (team1 - team2)."""
        return self.team1.kills - self.team2.kills

    @property
    def tower_diff(self) -> int:
        """Get tower differential (team1 - team2)."""
        return self.team1.towers - self.team2.towers

    @property
    def dragon_diff(self) -> int:
        """Get dragon differential (team1 - team2)."""
        return self.team1.dragons - self.team2.dragons

    @property
    def baron_diff(self) -> int:
        """Get baron differential (team1 - team2)."""
        return self.team1.barons - self.team2.barons

    @property
    def inhib_diff(self) -> int:
        """Get inhibitor differential (team1 - team2)."""
        return self.team1.inhibs - self.team2.inhibs

    def has_material_change(self, other: 'GameState', thresholds: Dict[str, int]) -> bool:
        """Check if game state has materially changed.

        Args:
            other: Previous game state
            thresholds: Dictionary of thresholds for each metric

        Returns:
            True if material change detected
        """
        if abs(self.gold_diff - other.gold_diff) >= thresholds.get('gold_diff', 500):
            return True
        if abs(self.kill_diff - other.kill_diff) >= thresholds.get('kills', 1):
            return True
        if abs(self.tower_diff - other.tower_diff) >= thresholds.get('towers', 1):
            return True
        if abs(self.dragon_diff - other.dragon_diff) >= thresholds.get('dragons', 1):
            return True
        if abs(self.baron_diff - other.baron_diff) >= thresholds.get('barons', 1):
            return True
        if abs(self.inhib_diff - other.inhib_diff) >= thresholds.get('inhibitors', 1):
            return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'match_id': self.match_id,
            'game_number': self.game_number,
            'game_time_seconds': self.game_time_seconds,
            'team1_name': self.team1_name,
            'team2_name': self.team2_name,
            'team1': self.team1.to_dict(),
            'team2': self.team2.to_dict(),
            'timestamp': self.timestamp.isoformat(),
            'is_finished': self.is_finished,
            'winner': self.winner
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameState':
        """Create from dictionary."""
        return cls(
            match_id=data['match_id'],
            game_number=data.get('game_number', 1),
            game_time_seconds=data['game_time_seconds'],
            team1_name=data['team1_name'],
            team2_name=data['team2_name'],
            team1=TeamState.from_dict(data.get('team1', {})),
            team2=TeamState.from_dict(data.get('team2', {})),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat())),
            is_finished=data.get('is_finished', False),
            winner=data.get('winner', 0)
        )
