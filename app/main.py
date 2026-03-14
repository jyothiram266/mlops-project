"""
Cloud-Native ML Inference Platform — FastAPI Application

Serves predictions from a pre-trained sklearn Iris classifier with
Prometheus metrics, health/readiness probes, and structured logging.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator

from app.model import load_model, predict, is_model_loaded

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application lifespan (model loading)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the ML model on startup."""
    logger.info("Starting ML Inference Platform...")
    try:
        load_model()
        logger.info("Model loaded — server is ready.")
    except Exception as e:
        logger.error("Failed to load model on startup: %s", e)
        # Allow the server to start so readiness probe can report NOT ready
    yield
    logger.info("Shutting down ML Inference Platform.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ML Inference Platform",
    description="Cloud-native ML model serving with Kubernetes, Prometheus, and DevSecOps automation.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class PredictionRequest(BaseModel):
    """Input schema for the /predict endpoint."""
    features: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Four numeric features: sepal_length, sepal_width, petal_length, petal_width",
        examples=[[5.1, 3.5, 1.4, 0.2]],
    )


class PredictionResponse(BaseModel):
    """Output schema for the /predict endpoint."""
    prediction: int
    prediction_label: str
    probabilities: dict[str, float]
    inference_time_ms: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["probes"])
async def health():
    """Liveness probe — returns 200 if the server process is running."""
    return {"status": "healthy"}


@app.get("/ready", tags=["probes"])
async def ready():
    """Readiness probe — returns 200 only when the model is loaded."""
    if not is_model_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}


@app.post("/predict", response_model=PredictionResponse, tags=["inference"])
async def run_prediction(request: PredictionRequest):
    """Run inference on the loaded ML model."""
    if not is_model_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded — service not ready")

    start = time.perf_counter()
    try:
        result = predict(request.features)
    except Exception as e:
        logger.error("Prediction failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)

    return PredictionResponse(
        prediction=result["prediction"],
        prediction_label=result["prediction_label"],
        probabilities=result["probabilities"],
        inference_time_ms=elapsed_ms,
    )


@app.get("/", tags=["info"])
async def root():
    """Platform info endpoint."""
    return {
        "service": "ML Inference Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }
