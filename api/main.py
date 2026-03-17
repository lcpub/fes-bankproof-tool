# api/main.py

from fastapi import FastAPI
from engine.core import Engine
from engine.business_models import BUSINESS_MODELS

app = FastAPI(title="FES Bank‑Proof Evaluation Tool")


@app.post("/run/{model_id}")
def run_model(model_id: str, parameters: dict):
    if model_id not in BUSINESS_MODELS:
        return {"error": "Unknown business model"}

    engine = Engine(BUSINESS_MODELS[model_id])
    return engine.run(parameters)