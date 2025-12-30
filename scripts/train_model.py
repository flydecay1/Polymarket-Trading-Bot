#!/usr/bin/env python3
"""Script to train the win probability model."""
import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import Config, setup_logger
from src.probability_model import WinProbabilityTrainer


def main():
    """Train the win probability model."""
    config = Config()
    logger = setup_logger("model_trainer", level="INFO", console=True)

    logger.info("starting_model_training")

    # Check if training data exists
    data_path = Path("data/historical/training_data.csv")

    if not data_path.exists():
        print(f"ERROR: Training data not found at {data_path}")
        print("Please run 'python scripts/collect_data.py' first")
        sys.exit(1)

    # Load training data
    print(f"\n📊 Loading training data from {data_path}...")
    df = pd.read_csv(data_path)
    print(f"✅ Loaded {len(df)} samples")

    # Initialize trainer
    model_type = config.get("probability_model.training.model_type", "logistic_regression")
    test_size = config.get("probability_model.training.test_size", 0.2)
    random_state = config.get("probability_model.training.random_state", 42)

    print(f"\n🤖 Training {model_type} model...")

    trainer = WinProbabilityTrainer(
        model_type=model_type,
        test_size=test_size,
        random_state=random_state
    )

    # Train model
    model_path = config.model_path
    scaler_path = config.feature_scaler_path

    accuracy, roc_auc = trainer.train(
        df=df,
        model_path=model_path,
        scaler_path=scaler_path
    )

    print(f"\n✅ Model Training Complete!")
    print(f"   Accuracy: {accuracy:.2%}")
    print(f"   ROC AUC: {roc_auc:.3f}")
    print(f"\n💾 Model saved to: {model_path}")
    print(f"💾 Scaler saved to: {scaler_path}")

    print("\n🚀 You can now run the bot with: python main.py")


if __name__ == "__main__":
    main()
