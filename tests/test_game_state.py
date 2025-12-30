"""Tests for GameState models."""
import pytest
from datetime import datetime

from src.data_ingestion.game_state import GameState, TeamState


def test_team_state_creation():
    """Test TeamState creation and methods."""
    team = TeamState(
        gold=15000,
        kills=10,
        towers=3,
        dragons=2,
        barons=1,
        inhibs=1
    )

    assert team.gold == 15000
    assert team.kills == 10
    assert team.towers == 3


def test_team_state_to_dict():
    """Test TeamState serialization."""
    team = TeamState(gold=10000, kills=5)
    data = team.to_dict()

    assert data['gold'] == 10000
    assert data['kills'] == 5
    assert data['towers'] == 0  # default


def test_team_state_from_dict():
    """Test TeamState deserialization."""
    data = {'gold': 12000, 'kills': 8, 'towers': 2}
    team = TeamState.from_dict(data)

    assert team.gold == 12000
    assert team.kills == 8
    assert team.towers == 2


def test_game_state_creation():
    """Test GameState creation."""
    team1 = TeamState(gold=15000, kills=10, towers=3)
    team2 = TeamState(gold=12000, kills=7, towers=2)

    game = GameState(
        match_id="12345",
        game_number=1,
        game_time_seconds=1200,
        team1_name="T1",
        team2_name="GenG",
        team1=team1,
        team2=team2
    )

    assert game.match_id == "12345"
    assert game.team1_name == "T1"
    assert game.game_time_minutes == 20.0


def test_game_state_diffs():
    """Test differential calculations."""
    team1 = TeamState(gold=15000, kills=10, towers=3, dragons=2)
    team2 = TeamState(gold=12000, kills=7, towers=2, dragons=1)

    game = GameState(
        match_id="12345",
        game_number=1,
        game_time_seconds=1200,
        team1_name="T1",
        team2_name="GenG",
        team1=team1,
        team2=team2
    )

    assert game.gold_diff == 3000
    assert game.kill_diff == 3
    assert game.tower_diff == 1
    assert game.dragon_diff == 1


def test_material_change_detection():
    """Test material change detection."""
    team1 = TeamState(gold=15000, kills=10, towers=3)
    team2 = TeamState(gold=12000, kills=7, towers=2)

    game1 = GameState(
        match_id="12345",
        game_number=1,
        game_time_seconds=1200,
        team1_name="T1",
        team2_name="GenG",
        team1=team1,
        team2=team2
    )

    # Small gold change - not material
    team1_new = TeamState(gold=15200, kills=10, towers=3)
    game2 = GameState(
        match_id="12345",
        game_number=1,
        game_time_seconds=1210,
        team1_name="T1",
        team2_name="GenG",
        team1=team1_new,
        team2=team2
    )

    thresholds = {'gold_diff': 500, 'kills': 1, 'towers': 1}
    assert not game2.has_material_change(game1, thresholds)

    # Kill change - material
    team1_kill = TeamState(gold=15000, kills=11, towers=3)
    game3 = GameState(
        match_id="12345",
        game_number=1,
        game_time_seconds=1220,
        team1_name="T1",
        team2_name="GenG",
        team1=team1_kill,
        team2=team2
    )

    assert game3.has_material_change(game1, thresholds)


def test_game_state_serialization():
    """Test GameState serialization roundtrip."""
    team1 = TeamState(gold=15000, kills=10, towers=3)
    team2 = TeamState(gold=12000, kills=7, towers=2)

    game1 = GameState(
        match_id="12345",
        game_number=1,
        game_time_seconds=1200,
        team1_name="T1",
        team2_name="GenG",
        team1=team1,
        team2=team2,
        is_finished=False,
        winner=0
    )

    # Serialize
    data = game1.to_dict()

    # Deserialize
    game2 = GameState.from_dict(data)

    assert game1.match_id == game2.match_id
    assert game1.gold_diff == game2.gold_diff
    assert game1.team1.kills == game2.team1.kills
