# engine/scenarios.py

SCENARIO_ORDER = ["baseline", "moderate", "stress"]


class ScenarioManager:
    """
    Handles scenario ordering and deterministic execution.
    """

    def __init__(self, business_model):
        self.business_model = business_model

    def get_ordered_scenarios(self):
        return SCENARIO_ORDER

    def run_deterministic(self, scenario: str, parameters: dict):
        """
        Placeholder for deterministic cash‑flow logic.

        No averaging.
        No scenario mixing.
        """
        return {
            "scenario": scenario,
            "npv": None,
            "irr": None,
            "payback": None,
        }