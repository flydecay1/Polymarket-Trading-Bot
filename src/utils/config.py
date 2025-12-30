"""Configuration management for the arbitrage bot."""
import os
import yaml
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv


class Config:
    """Central configuration manager."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize configuration.

        Args:
            config_path: Path to YAML config file
        """
        # Load environment variables
        env_path = Path("config/.env")
        if env_path.exists():
            load_dotenv(env_path)

        # Load YAML config
        self.config_path = Path(config_path)
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self._config: Dict[str, Any] = yaml.safe_load(f)
        else:
            self._config = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation key.

        Args:
            key: Config key in dot notation (e.g., 'data_ingestion.poll_interval')
            default: Default value if key not found

        Returns:
            Config value
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_env(self, key: str, default: Any = None) -> Any:
        """Get environment variable.

        Args:
            key: Environment variable name
            default: Default value if not found

        Returns:
            Environment variable value
        """
        return os.getenv(key, default)

    @property
    def pandascore_api_key(self) -> str:
        """Get PandaScore API key."""
        return self.get_env("PANDASCORE_API_KEY", "")

    @property
    def polymarket_api_key(self) -> str:
        """Get Polymarket API key."""
        return self.get_env("POLYMARKET_API_KEY", "")

    @property
    def polymarket_secret(self) -> str:
        """Get Polymarket secret."""
        return self.get_env("POLYMARKET_SECRET", "")

    @property
    def polymarket_passphrase(self) -> str:
        """Get Polymarket passphrase."""
        return self.get_env("POLYMARKET_PASSPHRASE", "")

    @property
    def wallet_private_key(self) -> str:
        """Get wallet private key."""
        return self.get_env("WALLET_PRIVATE_KEY", "")

    @property
    def chain_id(self) -> int:
        """Get blockchain chain ID."""
        return int(self.get_env("CHAIN_ID", "137"))

    @property
    def min_edge_threshold(self) -> float:
        """Get minimum edge threshold for trading."""
        return float(self.get_env("MIN_EDGE_THRESHOLD", "0.05"))

    @property
    def max_position_size(self) -> float:
        """Get max position size in USD."""
        return float(self.get_env("MAX_POSITION_SIZE", "100.0"))

    @property
    def poll_interval(self) -> int:
        """Get poll interval in seconds."""
        return int(self.get_env("POLL_INTERVAL_SECONDS", "2"))

    @property
    def model_path(self) -> str:
        """Get model file path."""
        return self.get_env("MODEL_PATH", "src/probability_model/models/win_probability_model.pkl")

    @property
    def feature_scaler_path(self) -> str:
        """Get feature scaler file path."""
        return self.get_env("FEATURE_SCALER_PATH", "src/probability_model/models/feature_scaler.pkl")
