"""
engine/core.py – Main FES Bank‑Proof Engine Orchestrator

This module performs PURE ORCHESTRATION.

Responsibilities:
- Enforce scenario separation (baseline, moderate, stress)
- Coordinate deterministic and Monte Carlo runs
- Assemble results in a common output space
- Enforce stress‑scenario dominance (structural, not numerical)
- Delegate ALL economics and risk math to dedicated layers

Explicitly DOES NOT:
- Implement business model economics
- Sample stochastic drivers
- Compute risk statistics (CVaR, percentiles, volatility)
- Compute Bankability Index
"""

from typing import Dict, Any, Optional

from engine.montecarlo import MonteCarloEngine
from engine.bankability import BankabilityEngine


REQUIRED_SCENARIOS = ("baseline", "moderate", "stress")


class Engine:
    """
    Unified FES Bank‑Proof Evaluation Engine.

    Architecture:
    - LAYER A: Business models (heterogeneous economics)
    - LAYER B: Monte Carlo + Bankability (homogeneous finance logic)
    - THIS CLASS: Orchestration only
    """

    def __init__(
        self,
        business_model,
        scenario_config: Optional[Dict[str, Dict[str, Any]]] = None,
        user_calibration: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the engine.

        Parameters
        ----------
        business_model
            Executable business model instance (Layer A)

        scenario_config
            Dict with keys: baseline, moderate, stress
            OPTIONAL at this stage – defaults handled safely

        user_calibration
            Optional global calibration applied equally to all scenarios
        """
        self.business_model = business_model
        self.scenario_config = scenario_config or {}
        self.user_calibration = user_calibration or {}

        self._validate_structure()

        self.mc_engine = MonteCarloEngine(business_model)
        self.bankability_engine = BankabilityEngine(business_model)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_structure(self) -> None:
        """Validate engine‑level structural constraints."""

        # Business model interface
        for attr in ("id", "name"):
            if not hasattr(self.business_model, attr):
                raise AttributeError(
                    f"Business model missing required attribute '{attr}'."
                )

        for method in (
            "calculate_annual_cash_flows",
            "get_stochastic_drivers",
            "get_policy_dependence",
        ):
            if not callable(getattr(self.business_model, method, None)):
                raise AttributeError(
                    f"Business model missing required method '{method}()'."
                )

        # Scenario configuration (if provided)
        if self.scenario_config:
            missing = set(REQUIRED_SCENARIOS) - set(self.scenario_config.keys())
            if missing:
                raise ValueError(
                    f"scenario_config missing required scenarios: {missing}."
                )

        # User calibration constraints
        forbidden = {
            "revenue_structure",
            "cost_structure",
            "scenario_dominance",
            "bankability_formula",
            "stochastic_drivers",
        }
        overlap = forbidden.intersection(self.user_calibration.keys())
        if overlap:
            raise ValueError(
                f"User calibration cannot modify immutable keys: {overlap}."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, n_runs: int = 20000) -> Dict[str, Any]:
        """
        Run full evaluation for all scenarios.

        Returns results suitable for Bankability evaluation.
        """
        results: Dict[str, Any] = {}

        for scenario in REQUIRED_SCENARIOS:
            params = self._assemble_parameters(scenario)

            deterministic = self._run_deterministic(scenario, params)
            monte_carlo = self.mc_engine.run(
                scenario=scenario,
                params=params,
                n_runs=n_runs,
            )

            results[scenario] = {
                "deterministic": deterministic,
                "monte_carlo": monte_carlo,
            }

        bankability = self.bankability_engine.evaluate(results)

        return {
            "results": results,
            "bankability": bankability,
            "business_model_id": self.business_model.id,
            "business_model_name": self.business_model.name,
            "policy_dependence": self.business_model.get_policy_dependence(),
            "user_calibration_applied": self.user_calibration,
            "stress_scenario_note": (
                "Stress scenario is binding. Overall bankability is determined "
                "by the worst (stress) scenario outcome."
            ),
            "disclaimer": (
                "This tool provides scenario‑based decision support only. "
                "It does not constitute an investment recommendation."
            ),
        }

    # ------------------------------------------------------------------
    # Deterministic execution
    # ------------------------------------------------------------------

    def _run_deterministic(
        self, scenario: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run deterministic cash‑flow analysis for ONE scenario."""
        annual_cf = self.business_model.calculate_annual_cash_flows(params)

        return {
            "scenario": scenario,
            "annual_cash_flows": annual_cf,
            "duration_years": len(annual_cf),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _assemble_parameters(self, scenario: str) -> Dict[str, Any]:
        """
        Merge scenario defaults with global user calibration.
        """
        base = self.scenario_config.get(scenario, {}).copy()
        base.update(self.user_calibration)
        return base