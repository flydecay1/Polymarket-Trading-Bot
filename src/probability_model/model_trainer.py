"""Model training for win probability prediction."""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import joblib
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
import structlog

logger = structlog.get_logger(__name__)


class WinProbabilityTrainer:
    """Train win probability prediction model."""

    def __init__(
        self,
        model_type: str = "logistic_regression",
        test_size: float = 0.2,
        random_state: int = 42
    ):
        """Initialize trainer.

        Args:
            model_type: "logistic_regression" or "gradient_boosting"
            test_size: Proportion of data for testing
            random_state: Random seed
        """
        self.model_type = model_type
        self.test_size = test_size
        self.random_state = random_state

        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = [
            'gold_diff',
            'kill_diff',
            'tower_diff',
            'dragon_diff',
            'baron_diff',
            'inhib_diff',
            'game_time_minutes'
        ]

    def prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features and labels.

        Args:
            df: Training data

        Returns:
            Tuple of (features, labels)
        """
        # Filter out very early game (< 10 minutes) as too volatile
        df = df[df['game_time_minutes'] >= 10].copy()

        # Extract features
        X = df[self.feature_names].values

        # Extract labels
        y = df['did_team1_win'].values

        logger.info("prepared_features", samples=len(X), features=len(self.feature_names))
        return X, y

    def train(
        self,
        df: pd.DataFrame,
        model_path: Optional[str] = None,
        scaler_path: Optional[str] = None
    ) -> Tuple[float, float]:
        """Train the model.

        Args:
            df: Training data
            model_path: Path to save model
            scaler_path: Path to save scaler

        Returns:
            Tuple of (accuracy, roc_auc)
        """
        logger.info("starting_training", model_type=self.model_type)

        # Prepare data
        X, y = self.prepare_features(df)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=y
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train model
        if self.model_type == "logistic_regression":
            self.model = LogisticRegression(
                random_state=self.random_state,
                max_iter=1000
            )
        elif self.model_type == "gradient_boosting":
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=self.random_state
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]

        accuracy = accuracy_score(y_test, y_pred)
        roc_auc = roc_auc_score(y_test, y_pred_proba)

        logger.info(
            "training_complete",
            accuracy=accuracy,
            roc_auc=roc_auc,
            train_samples=len(X_train),
            test_samples=len(X_test)
        )

        # Print classification report
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred))

        # Feature importance (for gradient boosting)
        if self.model_type == "gradient_boosting" and hasattr(self.model, 'feature_importances_'):
            print("\nFeature Importances:")
            for name, importance in zip(self.feature_names, self.model.feature_importances_):
                print(f"  {name}: {importance:.4f}")

        # Save model and scaler
        if model_path:
            model_dir = Path(model_path).parent
            model_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, model_path)
            logger.info("saved_model", path=model_path)

        if scaler_path:
            scaler_dir = Path(scaler_path).parent
            scaler_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.scaler, scaler_path)
            logger.info("saved_scaler", path=scaler_path)

        return accuracy, roc_auc

    def load(self, model_path: str, scaler_path: str) -> None:
        """Load trained model and scaler.

        Args:
            model_path: Path to model file
            scaler_path: Path to scaler file
        """
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        logger.info("loaded_model", model_path=model_path, scaler_path=scaler_path)
