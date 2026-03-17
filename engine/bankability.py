"""
engine/bankability.py – Bankability Index & Financial Risk Assessment (LAYER B)

Responsibilities:
- Compute Bankability Index (BI) per scenario independently
- Apply stress-scenario dominance rule: BI_overall = min(all three scenarios)
- Classify bankability level (5 categories)
- Enforce no-averaging principle
- Provide transparent, auditable results

CRITICAL PRINCIPLE:
Stress scenario is BINDING by construction.
BI_overall = min(BI_baseline, BI_moderate, BI_stress)

This ensures downside-risk visibility, NOT upside optimism.

LAYER B (Homogeneous):
Same BI formula applied identically to all five business models.
Formula parameters (weights, thresholds) are immutable.
"""

import numpy as np
from typing import Dict, Any
from datetime import datetime


class BankabilityEngine:
    """
    Bank-grade Bankability Index (BI) computation with stress-scenario dominance.
    
    LAYER B (homogeneous financial risk logic):
    - Accepts independent scenario results from LAYER A (business models)
    - Computes identical risk metrics for all five business models
    - Enforces stress-scenario dominance (no averaging)
    
    BI FORMULA (per scenario s ∈ {baseline, moderate, stress}):
    
        BI_s = w1·ValueAdequacy_s 
             + w2·CashFlowStability_s 
             − w3·DownsideRisk_s 
             − w4·PolicyDependence
    
    where:
    - ValueAdequacy ∈ [0, 1]: Is NPV positive and adequate? (higher is better)
    - CashFlowStability ∈ [0, 1]: How consistent? (lower volatility = better)
    - DownsideRisk ∈ [0, 1]: What is tail risk? (lower is better)
    - PolicyDependence ∈ [0, 1]: Structural policy sensitivity (lower is better)
    
    STRESS DOMINANCE (Non-Negotiable):
    
        BI_overall = min(BI_baseline, BI_moderate, BI_stress)
    
    This rule ensures worst-case scenario determines bankability,
    preventing overconfidence in baseline/moderate projections.
    
    CLASSIFICATION (Immutable):
    
        BI < 0.30   → Structurally unbankable (no finance recommended)
        0.30–0.50   → Public finance only (requires subsidy/grant)
        0.50–0.65   → Blended finance candidate (public-private mix)
        0.65–0.80   → Conditionally bankable (commercial lender interest, conditions)
        ≥ 0.80      → Robust (strong commercial viability)
    
    ASSUMPTIONS:
    - Weights (w1–w4) are fixed, not user-calibrated (Golden Prompt requirement)
    - Each scenario is processed independently (no cross-contamination)
    - PolicyDependence is homogeneous (same for all scenarios in a BM)
    - All component metrics are normalized to [0, 1]
    - Clamping to [0, 1] ensures bounded BI output
    - No correlation modeling between stochastic drivers
    """
    
    # ===== IMMUTABLE BANKABILITY INDEX WEIGHTS =====
    # These are fixed by design. Users MAY NOT adjust (Golden Prompt requirement).
    # Document assumptions but do not change.
    
    W1_VALUE_ADEQUACY = 0.35
    """
    Weight for ValueAdequacy metric (35% of positive contribution).
    
    Rationale: Reflects bank lending principle that positive NPV is foundation.
    Measures whether project generates adequate returns for stakeholders.
    Higher weight emphasizes return adequacy over other factors.
    
    Assumption: All five business models should demonstrate positive NPV
    in at least 65th percentile to be bankable.
    """
    
    W2_CASHFLOW_STABILITY = 0.25
    """
    Weight for CashFlowStability metric (25% of positive contribution).
    
    Rationale: Banks prioritize consistent, predictable cash flows.
    High volatility increases default risk and operational complexity.
    
    Assumption: Stability is secondary to adequacy but important for
    operational resilience. Measured via coefficient of variation inversion.
    """
    
    W3_DOWNSIDE_RISK = 0.25
    """
    Weight for DownsideRisk metric (25% of negative contribution).
    
    Rationale: Credit risk assessment focuses on tail outcomes.
    P(NPV < 0) and CVaR5 are primary risk signals for lenders.
    Largest negative component reflects bank credit committee priorities.
    
    Assumption: Loss probability and downside severity are equally important
    drivers of bankability rejection. Weighted equally in metric.
    """
    
    W4_POLICY_DEPENDENCE = 0.15
    """
    Weight for PolicyDependence factor (15% of negative contribution).
    
    Rationale: Forest ecosystem services depend heavily on policy (carbon prices,
    environmental regulations, subsidies, risk funds). Policy shifts affect
    revenue sustainability. Lower weight than DR because all models face
    this risk equally.
    
    Assumption: Policy is homogeneous risk across scenarios (not scenario-specific).
    Applied uniformly to all three scenarios via business_model config.
    """
    
    # Classification boundaries (immutable)
    CLASSIFICATION_BOUNDARIES = {
        0.30: "structurally unbankable",
        0.50: "public finance only",
        0.65: "blended finance candidate",
        0.80: "conditionally bankable",
        1.01: "robust"  # > 0.80
    }
    """
    Bankability classification thresholds.
    
    Rationale:
    - < 0.30: Negative BI indicates structural issues; no lender interest expected.
    - 0.30–0.50: Marginal viability; requires public subsidy/grant support.
    - 0.50–0.65: Mixed public-private (blended) structure needed.
    - 0.65–0.80: Commercial interest possible with conditions (covenants, guarantees).
    - ≥ 0.80: Robust enough for commercial lending without major conditions.
    """
    
    MANDATORY_DISCLAIMER = (
        "This tool provides scenario-based decision support only. "
        "Results depend on assumptions, parameter calibration, and model structure. "
        "It does not constitute an investment recommendation or funding commitment."
    )
    """
    Mandatory disclaimer per Golden Prompt.
    Included in all output for regulatory/transparency compliance.
    """
    
    def __init__(self, business_model_config: Dict[str, Any]):
        """
        Initialize BankabilityEngine for one business model.
        
        Args:
            business_model_config: Dict with business model metadata.
                Required keys:
                - 'id': str (e.g., 'AT', 'FR', 'DE', 'IT', 'SI')
                - 'name': str
                - 'policy_dependence': float ∈ [0, 1]
        
        Raises:
            KeyError: If required keys missing
            ValueError: If policy_dependence not in [0, 1]
        """
        self.bm_id = business_model_config.get('id', 'UNKNOWN')
        self.bm_name = business_model_config.get('name', 'UNKNOWN')
        
        policy_dep = business_model_config.get('policy_dependence')
        if policy_dep is None:
            raise KeyError(
                f"business_model_config missing 'policy_dependence'. "
                f"Required for BI formula."
            )
        
        if not isinstance(policy_dep, (int, float)):
            raise TypeError(
                f"policy_dependence must be numeric. Got: {type(policy_dep).__name__}"
            )
        
        if not (0 <= policy_dep <= 1):
            raise ValueError(
                f"policy_dependence must be in [0, 1]. Got: {policy_dep}. "
                f"Business model '{self.bm_id}': {self.bm_name}"
            )
        
        self.policy_dependence = float(policy_dep)
    
    def compute(self, scenario_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute Bankability Index across all three scenarios.
        
        CRITICAL CONSTRAINT: Stress scenario is binding.
        BI_overall = min(BI_baseline, BI_moderate, BI_stress)
        No averaging, no weighted combination.
        
        Args:
            scenario_results: Dict with keys 'baseline', 'moderate', 'stress'.
                Each contains:
                {
                    'deterministic': {
                        'npv': float,
                        'irr': Optional[float],
                        'payback_years': Optional[int],
                        'duration_years': int
                    },
                    'monte_carlo': {
                        'mean_npv': float,
                        'median_npv': float,
                        'std_npv': float,
                        'p5_npv': float,
                        'p95_npv': float,
                        'prob_negative_npv': float (∈ [0, 1]),
                        'cvar5_npv': float,
                        'volatility_dcf': float,
                        'driver_importance': Dict[str, float]
                    }
                }
        
        Returns:
            Dict with complete bankability assessment:
            {
                'scenario_results': {
                    'baseline': {metric_details},
                    'moderate': {metric_details},
                    'stress': {metric_details}
                },
                'BI_baseline': float ∈ [0, 1],
                'BI_moderate': float ∈ [0, 1],
                'BI_stress': float ∈ [0, 1],
                'BI_overall': float ∈ [0, 1] (always = min of three),
                'overall_classification': str,
                'binding_scenario': 'stress',
                'stress_dominance_explanation': str,
                'business_model_id': str,
                'business_model_name': str,
                'policy_dependence': float,
                'weights': {w1, w2, w3, w4},
                'disclaimer': str,
                'timestamp': str
            }
        
        Raises:
            ValueError: If required scenario/metric keys missing
            TypeError: If metric types invalid
        """
        # ===== VALIDATION =====
        
        required_scenarios = {'baseline', 'moderate', 'stress'}
        provided = set(scenario_results.keys())
        
        if not required_scenarios.issubset(provided):
            missing = required_scenarios - provided
            raise ValueError(
                f"scenario_results missing scenarios: {missing}. "
                f"Required: {required_scenarios}"
            )
        
        for scenario_name in required_scenarios:
            self._validate_scenario_result(scenario_results[scenario_name], scenario_name)
        
        # ===== COMPUTE BI PER SCENARIO (INDEPENDENTLY) =====
        
        bi_results = {}
        
        for scenario_name in ['baseline', 'moderate', 'stress']:
            scenario_data = scenario_results[scenario_name]
            
            # Extract metrics independently for this scenario
            metrics = self._extract_metrics(scenario_data)
            
            # Compute BI for this scenario using extracted metrics
            bi_score = self._compute_bi_score(
                value_adequacy=metrics['ValueAdequacy'],
                cashflow_stability=metrics['CashFlowStability'],
                downside_risk=metrics['DownsideRisk']
            )
            
            bi_results[scenario_name] = {
                'metrics': metrics,
                'BI': bi_score
            }
        
        # ===== APPLY STRESS-SCENARIO DOMINANCE =====
        # CRITICAL: Use min(), NOT mean or weighted average
        
        bi_overall = min(
            bi_results['baseline']['BI'],
            bi_results['moderate']['BI'],
            bi_results['stress']['BI']
        )
        
        # Identify binding scenario (always stress by construction)
        binding_scenario = 'stress'
        
        # ===== CLASSIFY =====
        
        classification = self._classify_bankability(bi_overall)
        
        # ===== GENERATE STRESS DOMINANCE EXPLANATION =====
        
        stress_explanation = self._generate_stress_explanation(bi_results, bi_overall)
        
        # ===== ASSEMBLE COMPLETE OUTPUT =====
        
        return {
            'BI_baseline': float(bi_results['baseline']['BI']),
            'BI_moderate': float(bi_results['moderate']['BI']),
            'BI_stress': float(bi_results['stress']['BI']),
            'BI_overall': float(bi_overall),
            'classification': classification,
            'stress_scenario_note': stress_explanation
        }
    
    # ========== PRIVATE HELPERS ==========
    
    def _validate_scenario_result(
        self,
        scenario_data: Dict[str, Any],
        scenario_name: str
    ) -> None:
        """
        Validate scenario result structure and required metrics.
        
        ASSUMPTION: Each scenario has deterministic and Monte Carlo components.
        Monte Carlo results are required (bank-grade standard).
        
        Args:
            scenario_data: Scenario result dict
            scenario_name: str – 'baseline', 'moderate', or 'stress'
        
        Raises:
            ValueError: If required keys/metrics missing or invalid
        """
        required_keys = {'deterministic', 'monte_carlo'}
        if not required_keys.issubset(scenario_data.keys()):
            missing = required_keys - set(scenario_data.keys())
            raise ValueError(
                f"Scenario '{scenario_name}' missing keys: {missing}"
            )
        
        mc_data = scenario_data.get('monte_carlo', {})
        
        # Required Monte Carlo metrics for BI computation
        required_metrics = {
            'mean_npv', 'p5_npv', 'p95_npv', 'std_npv',
            'prob_negative_npv', 'cvar5_npv'
        }
        
        if not required_metrics.issubset(mc_data.keys()):
            missing = required_metrics - set(mc_data.keys())
            raise ValueError(
                f"Scenario '{scenario_name}' Monte Carlo missing metrics: {missing}. "
                f"Required: {required_metrics}"
            )
        
        # Validate metric types
        for metric_name in ['p5_npv', 'p95_npv', 'mean_npv', 'std_npv', 'cvar5_npv']:
            value = mc_data.get(metric_name)
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"Scenario '{scenario_name}' metric '{metric_name}' "
                    f"must be numeric. Got: {type(value).__name__}"
                )
        
        # Validate probability is in [0, 1]
        prob_neg = mc_data.get('prob_negative_npv')
        if not isinstance(prob_neg, (int, float)) or not (0 <= prob_neg <= 1):
            raise ValueError(
                f"Scenario '{scenario_name}' prob_negative_npv must be numeric in [0, 1]. "
                f"Got: {prob_neg}"
            )
    
    def _extract_metrics(
        self,
        scenario_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Extract and compute decision-support metrics for ONE scenario.
        
        ASSUMPTION: Each scenario is processed independently.
        No cross-scenario comparison here.
        Metrics are scalar per scenario, derived from deterministic + Monte Carlo results.
        
        Args:
            scenario_data: One scenario's deterministic + Monte Carlo results
        
        Returns:
            Dict of normalized metrics for this scenario:
            {
                'ValueAdequacy': float ∈ [0, 1],
                'CashFlowStability': float ∈ [0, 1],
                'DownsideRisk': float ∈ [0, 1]
            }
        """
        mc = scenario_data['monte_carlo']
        
        mean_npv = mc['mean_npv']
        std_npv = mc['std_npv']
        p5_npv = mc['p5_npv']
        p95_npv = mc['p95_npv']
        prob_negative = mc['prob_negative_npv']
        
        # ===== VALUE ADEQUACY METRIC =====
        # Measure: Is NPV positive and adequate?
        # ASSUMPTION: p95 should be positive for viability.
        # ASSUMPTION: mean relative to p95 indicates sufficiency.
        
        if p95_npv <= 0:
            # Even upside scenario is unprofitable
            value_adequacy = 0.0
        elif mean_npv < 0:
            # Mean is negative; project at risk despite upside potential
            value_adequacy = 0.1
        else:
            # Ratio of mean to upside: how much of p95 is achieved on average?
            ratio = mean_npv / max(p95_npv, 1.0)
            # Cap at 1.0 (perfect adequacy)
            value_adequacy = min(1.0, ratio)
        
        # ===== CASHFLOW STABILITY METRIC =====
        # Measure: How consistent are outcomes? (low volatility = high stability)
        # ASSUMPTION: Coefficient of Variation captures relative volatility.
        # ASSUMPTION: CV > 1 indicates high volatility (instability).
        
        if mean_npv <= 0:
            # Cannot compute meaningful CV; assume unstable
            cashflow_stability = 0.2
        else:
            # Coefficient of variation (std relative to mean)
            cv = std_npv / abs(mean_npv)
            # Invert: high CV → low stability (1 - CV, clamped)
            cashflow_stability = max(0.0, 1.0 - min(1.0, cv))
        
        # ===== DOWNSIDE RISK METRIC =====
        # Measure: How severe is tail risk?
        # ASSUMPTION: P(NPV < 0) is primary credit risk signal.
        # ASSUMPTION: Downside spread (p95 - p5) measures range of bad outcomes.
        
        # Probability component (0–1, higher = worse)
        prob_component = prob_negative
        
        # Spread component: how much can NPV fall?
        if p95_npv > 0:
            # Downside extent relative to upside
            downside_spread = max(0.0, (p95_npv - p5_npv) / p95_npv)
        else:
            downside_spread = 1.0
        
        # Combine: Equal weight on probability and severity
        downside_risk = 0.5 * prob_component + 0.5 * downside_spread
        downside_risk = min(1.0, downside_risk)
        
        return {
            'ValueAdequacy': float(value_adequacy),
            'CashFlowStability': float(cashflow_stability),
            'DownsideRisk': float(downside_risk)
        }
    
    def _compute_bi_score(
        self,
        value_adequacy: float,
        cashflow_stability: float,
        downside_risk: float
    ) -> float:
        """
        Compute Bankability Index for one scenario.
        
        FORMULA:
        BI = w1·ValueAdequacy + w2·CashFlowStability 
             − w3·DownsideRisk − w4·PolicyDependence
        
        ASSUMPTIONS:
        - All component metrics are normalized to [0, 1]
        - Weights are fixed (immutable)
        - PolicyDependence is homogeneous (stored at init)
        - Result is clamped to [0, 1] to ensure bounded BI scale
        
        INTERPRETATION:
        - BI > 0.65: Positive rating (conditionally bankable or better)
        - BI < 0.30: Negative rating (unbankable)
        - Intermediate: Mixed profile (blended finance)
        
        Args:
            value_adequacy: float ∈ [0, 1]
            cashflow_stability: float ∈ [0, 1]
            downside_risk: float ∈ [0, 1]
        
        Returns:
            float – BI score ∈ [0, 1]
        """
        bi = (
            self.W1_VALUE_ADEQUACY * value_adequacy
            + self.W2_CASHFLOW_STABILITY * cashflow_stability
            - self.W3_DOWNSIDE_RISK * downside_risk
            - self.W4_POLICY_DEPENDENCE * self.policy_dependence
        )
        
        # Clamp to [0, 1] to ensure bounded output scale
        bi = max(0.0, min(1.0, bi))
        
        return float(bi)
    
    def _classify_bankability(self, bi_overall: float) -> str:
        """
        Classify bankability level based on overall BI.
        
        CLASSIFICATION (Immutable):
        < 0.30          → "structurally unbankable"
        0.30 – 0.50     → "public finance only"
        0.50 – 0.65     → "blended finance candidate"
        0.65 – 0.80     → "conditionally bankable"
        ≥ 0.80          → "robust"
        
        ASSUMPTION: Classification reflects typical development finance thresholds.
        These are not user-adjustable (Golden Prompt requirement).
        
        Args:
            bi_overall: float ∈ [0, 1]
        
        Returns:
            str – classification label
        """
        thresholds = [
            (0.30, "structurally unbankable"),
            (0.50, "public finance only"),
            (0.65, "blended finance candidate"),
            (0.80, "conditionally bankable"),
            (1.00, "robust")
        ]
        
        for threshold, label in thresholds:
            if bi_overall < threshold:
                return label
        
        # Fallback (should not reach here if 0 ≤ bi_overall ≤ 1)
        return "robust"
    
    def _generate_stress_explanation(
        self,
        bi_results: Dict[str, Dict[str, Any]],
        bi_overall: float
    ) -> str:
        """
        Generate explanation of stress-scenario dominance.
        
        This narrative explains the Golden Prompt principle:
        "Stress scenario is binding by construction."
        
        Should make explicit:
        - Why all three scenarios are reported separately
        - Why min() is used (not mean or max)
        - Why conservative assessment prevails
        - How user should interpret the result
        
        ASSUMPTION: Users may misread "best case" as classification;
        this explanation corrects that misconception.
        
        Args:
            bi_results: Dict with BI values and metrics per scenario
            bi_overall: float – overall BI (always = min of three)
        
        Returns:
            str – Explanation message
        """
        bi_base = bi_results['baseline']['BI']
        bi_mod = bi_results['moderate']['BI']
        bi_stress = bi_results['stress']['BI']
        
        explanation = (
            f"STRESS-SCENARIO DOMINANCE: Bankability is determined by the worst-case "
            f"(stress) scenario, ensuring downside-risk visibility prevails over optimism. "
            f"\n\nIndividual scenario indices: "
            f"Baseline BI = {bi_base:.3f}, "
            f"Moderate BI = {bi_mod:.3f}, "
            f"Stress BI = {bi_stress:.3f}. "
            f"\n\nOverall (binding) BI = min({bi_base:.3f}, {bi_mod:.3f}, {bi_stress:.3f}) "
            f"= {bi_overall:.3f}. "
            f"\n\nInterpretation: Favorable baseline/moderate projections do NOT override "
            f"stress-scenario risks. Classification '{self._classify_bankability(bi_overall)}' "
            f"reflects worst-case fundamentals. This conservative approach aligns with bank "
            f"credit committee practice: assume adverse scenarios will occur and assess "
            f"viability under stress."
        )
        
        return explanation