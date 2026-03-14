"""
ML Model module — loads and serves predictions from a pre-trained sklearn model.

The model path is configurable via the MODEL_PATH environment variable,
enabling Kubernetes PersistentVolume mounts for model artifact storage.
"""

import os
import logging
from typing import Optional

import joblib
import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = os.getenv("MODEL_PATH", "/app/models/model.joblib")

_model = None


class ModelNotLoadedError(Exception):
    """Raised when prediction is attempted before model is loaded."""
    pass


def load_model(path: Optional[str] = None) -> None:
    """Load the ML model from disk into memory."""
    global _model
    model_path = path or MODEL_PATH
    try:
        _model = joblib.load(model_path)
        logger.info("Model loaded successfully from %s", model_path)
    except FileNotFoundError:
        logger.error("Model file not found at %s", model_path)
        raise
    except Exception as e:
        logger.error("Failed to load model from %s: %s", model_path, e)
        raise


def predict(features: list[float]) -> dict:
    """
    Run inference on the loaded model.

    Args:
        features: List of numeric feature values matching model input shape.

    Returns:
        Dictionary with 'prediction' (int) and 'probabilities' (list of floats).
    """
    if _model is None:
        raise ModelNotLoadedError("Model has not been loaded. Call load_model() first.")

    input_array = np.array(features).reshape(1, -1)
    prediction = int(_model.predict(input_array)[0])
    probabilities = _model.predict_proba(input_array)[0].tolist()

    return {
        "prediction": prediction,
        "prediction_label": _get_label(prediction),
        "probabilities": {
            _get_label(i): round(p, 4) for i, p in enumerate(probabilities)
        },
    }


def is_model_loaded() -> bool:
    """Check if the model is currently loaded in memory."""
    return _model is not None


def _get_label(class_id: int) -> str:
    """Map Iris class ID to its human-readable label."""
    labels = {0: "setosa", 1: "versicolor", 2: "virginica"}
    return labels.get(class_id, f"class_{class_id}")
