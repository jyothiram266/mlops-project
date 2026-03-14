"""
One-time training script for the Iris classifier.

Trains a RandomForestClassifier on the Iris dataset and saves
the model artifact to disk. Used during Docker image build.
"""

import os
import logging

import joblib
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def train_and_save(output_dir: str = "/app/models") -> str:
    """
    Train an Iris RandomForestClassifier and persist to disk.

    Args:
        output_dir: Directory to save the model artifact.

    Returns:
        Path to the saved model file.
    """
    logger.info("Loading Iris dataset...")
    data = load_iris()
    X_train, X_test, y_train, y_test = train_test_split(
        data.data, data.target, test_size=0.2, random_state=42
    )

    logger.info("Training RandomForestClassifier (n_estimators=100)...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    accuracy = accuracy_score(y_test, model.predict(X_test))
    logger.info("Model accuracy on test set: %.4f", accuracy)

    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, "model.joblib")
    joblib.dump(model, model_path)
    logger.info("Model saved to %s", model_path)

    return model_path


if __name__ == "__main__":
    train_and_save()
