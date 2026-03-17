"""
engine/core.py – Main FES Bank-Proof Engine Orchestrator

Responsibilities:
- Coordinate deterministic and Monte Carlo runs
- Manage scenario execution (Baseline, Moderate, Stress)
- Enforce stress-scenario dominance in output structure
- Assemble results in common output space
- Delegate to business models (LAYER A) and bankability layer (LAYER B)

Does NOT implement:
- Business model economics (LAYER A responsibility)
- Bankability index calculation (LAYER B responsibility)
- Stochastic driver sampling (delegated to simulation.distributions)
"""

import numpy as np
from typing import Dict, Any, Optional


class Engine:
    """
    Core FES Bank-Proof Evaluation Engine.
    
    Orchestrates deterministic and Monte Carlo analysis across three scenarios:
    Baseline, Moderate, Stress.
    
    STRESS SCENARIO IS BINDING: Bankability classification = stress scenario result.
    """
    
    def __init__(
        self,
        business_model,
        scenario_config: Dict[str, Dict[str, Any]],
        user_calibration: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the Engine.
        
        Args:
            business_model: Instance of a business model class (e.g., AustriaReverseAuction).
                           Must implement:
                           - calculate_annual_cash_flows(scenario_params: Dict) -> np.ndarray
                           - get_stochastic_drivers() -> Dict[driver_name, dist_spec]
            scenario_config: Dict with keys 'baseline', 'moderate', 'stress'.
                            Each maps to scenario-specific parameters.
                            Source: config/scenarios.yaml
            user_calibration: Optional user adjustments. Allowed keys:
                             {'prices', 'volumes', 'costs', 'discount_rate', 'duration'}
                            Forbidden: {'revenue_structure', 'cost_structure', 'scenario_dominance'}
        
        Raises:
            ValueError: On configuration violations.
        """
        self.business_model = business_model
        self.scenario_config = scenario_config
        self.user_calibration = user_calibration or {}
        
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """
        Validate business model, scenarios, and calibration structure.
        
        Raises:
            ValueError: If structural requirements not met.
        """
        # Check scenario keys
        required_scenarios = {'baseline', 'moderate', 'stress'}
        if not required_scenarios.issubset(self.scenario_config.keys()):
            raise ValueError(
                f"scenario_config missing required keys: {required_scenarios}. "
                f"Got: {set(self.scenario_config.keys())}"
            )
        
        # Check business model interface
        required_methods = ['calculate_annual_cash_flows', 'get_stochastic_drivers']
        for method in required_methods:
            if not hasattr(self.business_model, method) or not callable(getattr(self.business_model, method)):
                raise ValueError(
                    f"business_model must implement {method}(). "
                    f"Class: {self.business_model.__class__.__name__}"
                )
        
        # Check calibration constraints: no structure modifications allowed
        forbidden_keys = {'revenue_structure', 'cost_structure', 'scenario_dominance', 'bankability_formula'}
        if forbidden_keys.intersection(self.user_calibration.keys()):
            raise ValueError(
                f"User calibration cannot modify {forbidden_keys}. "
                f"Attempted: {forbidden_keys.intersection(self.user_calibration.keys())}"
            )
    
    def run_deterministic_analysis(self, scenario: str) -> Dict[str, Any]:
        """
        Run deterministic analysis for a single scenario.
        
        Args:
            scenario: str – 'baseline', 'moderate', or 'stress'
        
        Returns:
            Dict with keys:
            - scenario: str
            - annual_cash_flows: np.ndarray, shape (duration,)
            - cumulative_cash_flows: np.ndarray, shape (duration,)
            - npv: float
            - discount_rate: float
            - irr: Optional[float]
            - payback_years: Optional[float]
            - duration_years: int
        
        Raises:
            ValueError: If scenario not in {'baseline', 'moderate', 'stress'}
        """
        if scenario not in {'baseline', 'moderate', 'stress'}:
            raise ValueError(f"scenario must be one of {{'baseline', 'moderate', 'stress'}}. Got: {scenario}")
        
        # Merge scenario config with user overrides
        params = self._merge_scenario_with_calibration(scenario)
        
        # Delegate to business model: calculate annual cash flows
        annual_cf = self.business_model.calculate_annual_cash_flows(params)
        
        if not isinstance(annual_cf, np.ndarray):
            raise TypeError(
                f"business_model.calculate_annual_cash_flows() must return np.ndarray. "
                f"Got: {type(annual_cf)}"
            )
        
        discount_rate = params.get('discount_rate', 0.05)
        duration = len(annual_cf)
        
        # Compute NPV
        discount_factors = np.array([(1 + discount_rate) ** (-t) for t in range(duration)])
        npv = np.sum(annual_cf * discount_factors)
        
        # Compute cumulative (for payback analysis)
        cumulative_cf = np.cumsum(annual_cf)
        
        # IRR and payback only if meaningful for this BM
        from ..utils.metrics import compute_irr, compute_payback
        irr = compute_irr(annual_cf) if self._irr_meaningful(annual_cf) else None
        payback = compute_payback(cumulative_cf) if self._payback_meaningful(cumulative_cf) else None
        
        return {
            'scenario': scenario,
            'annual_cash_flows': annual_cf,
            'cumulative_cash_flows': cumulative_cf,
            'npv': npv,
            'discount_rate': discount_rate,
            'irr': irr,
            'payback_years': payback,
            'duration_years': duration
        }
    
    def run_monte_carlo_analysis(
        self,
        scenario: str,
        n_runs: int = 20000,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation for a single scenario.
        
        MANDATORY BANK-GRADE STANDARD:
        - n_runs ≥ 20,000
        - Fixed random seed for reproducibility
        - Vectorized NumPy computation
        - Stochastic drivers from business model
        
        Args:
            scenario: str – 'baseline', 'moderate', or 'stress'
            n_runs: int – Monte Carlo runs (default 20,000, minimum enforced)
            seed: int – fixed random seed
        
        Returns:
            Dict with keys:
            - scenario: str
            - n_runs: int
            - npv_distribution: np.ndarray, shape (n_runs,)
            - mean_npv: float
            - median_npv: float
            - std_npv: float
            - p5_npv: float
            - p50_npv: float
            - p95_npv: float
            - prob_negative_npv: float (P(NPV < 0))
            - cvar5_npv: float (Conditional Value at Risk, 5% tail)
            - volatility_dcf: float
            - driver_importance: Dict[str, float] (Tornado ranking)
            - discount_rate: float
            - duration_years: int
        
        Raises:
            ValueError: If scenario invalid or n_runs < 20000
        """
        if scenario not in {'baseline', 'moderate', 'stress'}:
            raise ValueError(f"scenario must be one of {{'baseline', 'moderate', 'stress'}}. Got: {scenario}")
        
        if n_runs < 20000:
            raise ValueError(
                f"Monte Carlo requires n_runs ≥ 20,000 (bank-grade standard). Got: {n_runs}"
            )
        
        # Fix random seed
        np.random.seed(seed)
        
        # Merge parameters
        params = self._merge_scenario_with_calibration(scenario)
        discount_rate = params.get('discount_rate', 0.05)
        duration = params.get('duration_years')
        
        # Get stochastic drivers from business model
        stochastic_drivers = self.business_model.get_stochastic_drivers()
        
        # Sample drivers (vectorized)
        from ..simulation.distributions import sample_driver_ensemble
        driver_samples = sample_driver_ensemble(stochastic_drivers, n_runs)
        
        # Compute NPV for each run
        npv_distribution = np.zeros(n_runs)
        
        for i in range(n_runs):
            run_params = params.copy()
            for driver_name, samples_array in driver_samples.items():
                run_params[driver_name] = samples_array[i]
            
            annual_cf = self.business_model.calculate_annual_cash_flows(run_params)
            discount_factors = np.array([(1 + discount_rate) ** (-t) for t in range(duration)])
            npv_distribution[i] = np.sum(annual_cf * discount_factors)
        
        # Compute risk metrics
        mean_npv = np.mean(npv_distribution)
        median_npv = np.median(npv_distribution)
        std_npv = np.std(npv_distribution)
        p5_npv = np.percentile(npv_distribution, 5)
        p50_npv = np.percentile(npv_distribution, 50)
        p95_npv = np.percentile(npv_distribution, 95)
        prob_negative = np.mean(npv_distribution < 0)
        
        # CVaR5: mean of worst 5%
        var_5 = np.percentile(npv_distribution, 5)
        cvar5 = np.mean(npv_distribution[npv_distribution <= var_5])
        
        # Volatility and driver importance
        from ..utils.metrics import compute_volatility_dcf, compute_driver_importance
        volatility_dcf = compute_volatility_dcf(self.business_model, params, driver_samples, n_runs)
        driver_importance = compute_driver_importance(
            self.business_model, params, driver_samples, stochastic_drivers, n_runs
        )
        
        return {
            'scenario': scenario,
            'n_runs': n_runs,
            'random_seed': seed,
            'npv_distribution': npv_distribution,
            'mean_npv': mean_npv,
            'median_npv': median_npv,
            'std_npv': std_npv,
            'p5_npv': p5_npv,
            'p50_npv': p50_npv,
            'p95_npv': p95_npv,
            'prob_negative_npv': prob_negative,
            'cvar5_npv': cvar5,
            'volatility_dcf': volatility_dcf,
            'driver_importance': driver_importance,
            'discount_rate': discount_rate,
            'duration_years': duration
        }
    
    def evaluate_all_scenarios(self, n_runs: int = 20000) -> Dict[str, Any]:
        """
        Evaluate all three scenarios: Baseline, Moderate, Stress.
        
        CRITICAL STRESS-SCENARIO DOMINANCE:
        Stress scenario determines bankability classification.
        Overall bankability = min(BI_baseline, BI_moderate, BI_stress)
        
        This is enforced at the bankability layer, but communicated here.
        
        Args:
            n_runs: int – Monte Carlo runs per scenario
        
        Returns:
            Dict with structure:
            {
                'baseline': {
                    'deterministic': {...},
                    'monte_carlo': {...}
                },
                'moderate': {...},
                'stress': {...},
                'business_model_id': str,
                'business_model_name': str,
                'user_calibration_applied': Dict,
                'stress_scenario_note': str,
                'disclaimer': str
            }
        
        Note: Bankability index calculation is LAYER B responsibility.
              Call bankability.compute_bankability_index() separately.
        """
        results = {}
        
        # Execute all three scenarios
        for scenario in ['baseline', 'moderate', 'stress']:
            det = self.run_deterministic_analysis(scenario)
            mc = self.run_monte_carlo_analysis(scenario, n_runs=n_runs)
            
            results[scenario] = {
                'deterministic': det,
                'monte_carlo': mc
            }
        
        # Assemble metadata
        results['business_model_id'] = self.business_model.id
        results['business_model_name'] = self.business_model.name
        results['user_calibration_applied'] = self.user_calibration
        
        # STRESS DOMINANCE (non-negotiable)
        results['stress_scenario_note'] = (
            "STRESS SCENARIO IS BINDING. "
            "Bankability classification determined by stress scenario. "
            "Overall Bankability Index = min(BI_baseline, BI_moderate, BI_stress). "
            "This ensures downside-risk visibility over apparent optimism."
        )
        
        # Mandatory disclaimer
        results['disclaimer'] = (
            "This tool provides scenario-based decision support only. "
            "Results depend on assumptions, parameter calibration, and model structure. "
            "It does not constitute an investment recommendation or funding commitment."
        )
        
        return results
    
    # ---------- Private Helpers ----------
    
    def _merge_scenario_with_calibration(self, scenario: str) -> Dict[str, Any]:
        """
        Merge scenario-specific parameters with user calibration overrides.
        
        User may override:
        - prices (carbon_price, tourism_fee, etc.)
        - volumes (eligible_area, visitor_count, etc.)
        - costs (efficiency factors)
        - discount_rate
        - duration
        
        Args:
            scenario: str – 'baseline', 'moderate', or 'stress'
        
        Returns:
            Merged params dict
        """
        merged = self.scenario_config[scenario].copy()
        
        # Apply user calibration (overrides scenario defaults)
        calibration_allowed = {'prices', 'volumes', 'costs', 'discount_rate', 'duration'}
        for key, value in self.user_calibration.items():
            if key in calibration_allowed:
                merged[key] = value
        
        return merged
    
    def _irr_meaningful(self, annual_cash_flows: np.ndarray) -> bool:
        """
        Check if IRR computation is meaningful for this business model.
        
        (Not all BMs have meaningful IRR; some may be perpetual-service models.)
        """
        from ..utils.metrics import is_irr_meaningful
        return is_irr_meaningful(annual_cash_flows)
    
    def _payback_meaningful(self, cumulative_cash_flows: np.ndarray) -> bool:
        """
        Check if payback period is meaningful.
        
        (Some models with perpetual revenue may not break even in finite time.)
        """
        from ..utils.metrics import is_payback_meaningful
        return is_payback_meaningful(cumulative_cash_flows)