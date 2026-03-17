# engine/bankability.py

class BankabilityEngine:
    """
    Computes Bankability Index with stress‑scenario dominance.
    """

    def __init__(self, business_model):
        self.policy_dependence = business_model["policy_dependence"]

    def evaluate(self, scenario_results: dict):
        """
        Bankability is driven by the WORST scenario.
        """

        stress = scenario_results["stress"]

        # Placeholder: real math added later
        bankability_index = None

        return {
            "index": bankability_index,
            "binding_scenario": "stress",
            "classification": None,
        }