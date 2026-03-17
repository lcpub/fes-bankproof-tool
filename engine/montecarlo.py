# engine/montecarlo.py

import numpy as np


class MonteCarloEngine:
    """
    Monte Carlo simulation engine (bank‑grade).

    No causal inference.
    No econometrics.
    """

    def __init__(self, business_model):
        self.business_model = business_model
        self.n_runs = 20000
        self.random_seed = 42

    def run(self, scenario: str, parameters: dict):
        np.random.seed(self.random_seed)

        # Placeholder: real drivers to be injected later
        simulated_npvs = np.zeros(self.n_runs)

        return {
            "mean_npv": None,
            "p05": None,
            "p50": None,
            "p95": None,
            "prob_negative": None,
            "cvar_5": None,
            "raw": simulated_npvs,
        }