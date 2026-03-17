"""
engine/core.py – Main FES Bank-Proof Engine Orchestrator

Responsibilities:
- Coordinate deterministic and Monte Carlo runs
- Manage scenario execution (Baseline, Moderate, Stress) independently
- Enforce scenario separation (no averaging, no blending)
- Assemble results in common output space
- Delegate to business models (LAYER A), Monte Carlo engine, and bankability layer (LAYER B)
- Communicate stress-scenario dominance principle

Does NOT implement:
- Business model economics (LAYER A responsibility)
- Bankability index calculation (LAYER B responsibility)
- Stochastic driver sampling (montecarlo module responsibility)
- Scenario weighting or averaging

CRITICAL PRINCIPLES:
1. Each scenario processed INDEPENDENTLY (no cross-scenario math)
2. Stress scenario emphasized as BINDING (communicated in output)
3. All three scenarios returned separately (bankability.py applies min())
4. No implicit normalization or averaging within core.py
5. Single Engine orchestrates all five heterogeneous business models
"""

import numpy as np
from typing import Dict, Any, Optional


class Engine:
    """
    Core FES Bank-Proof Evaluation Engine.
    
    Orchestrates deterministic and Monte Carlo analysis across three scenarios:
    Baseline, Moderate, Stress.
    
    CRITICAL CONSTRAINT: STRESS SCENARIO IS BINDING.
    Bankability classification = min(BI_baseline, BI_moderate, BI_stress)
    
    ARCHITECTURE:
    - LAYER A (heterogeneous): Five business models with unique economics
    - LAYER B (homogeneous): Identical risk metrics and bankability formula
    - This Engine: Pure orchestration, NO business logic or bankability calculation
    
    ASSUMPTIONS:
    - business_model is executable object with required methods/attributes
    - scenario_config has all three scenarios with distinct parameter sets
    - Each scenario is processed independently (no averaging)
    - Stress scenario result is not overridden or softened
    - All numerical values (prices, volumes, costs) supplied by user at runtime
    """
    
    def __init__(
        self,
        business_model,
        scenario_config: Dict[str, Dict[str, Any]],
        user_calibration: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the Engine with business model and scenario configuration.
        
        ASSUMPTION: business_model is executable class instance (not dict).
        ASSUMPTION: scenario_config has baseline, moderate, stress as separate items.
        ASSUMPTION: All three scenarios require evaluation (none optional).
        
        Args:
            business_model: Instance of BusinessModel subclass (LAYER A).
                           Must implement:
                           - id: str attribute (business model identifier)
                           - name: str attribute (business model name)
                           - calculate_annual_cash_flows(params: Dict) → np.ndarray
                           - get_stochastic_drivers() → Dict[driver_name, dist_spec]
                           - get_policy_dependence() → float
            
            scenario_config: Dict mapping scenario names to parameter dicts.
                            Required keys: 'baseline', 'moderate', 'stress'
                            Each maps to Dict with scenario-specific values:
                            - prices (e.g., carbon_price, tourism_fee, etc.)
                            - volumes (e.g., eligible_area, visitor_count, etc.)
                            - costs (baseline costs for each cost line)
                            - discount_rate (optional, default 5%)
                            - duration_years (optional, default from BM config)
                            Source: config/scenarios.yaml or hardcoded defaults
            
            user_calibration: Optional Dict with user-provided adjustments.
                             Allowed keys: {'prices', 'volumes', 'costs', 'discount_rate', 'duration'}
                             Forbidden keys: {'revenue_structure', 'cost_structure', 
                                            'scenario_dominance', 'bankability_formula', ...}
                             Applied equally to all scenarios.
        
        Raises:
            ValueError: If structural requirements not met (missing scenarios, 
                       business_model missing methods, forbidden calibration keys)
            AttributeError: If business_model missing id or name attributes
        """
        self.business_model = business_model
        self.scenario_config = scenario_config
        self.user_calibration = user_calibration or {}
        
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """
        Validate structural requirements for engine initialization.
        
        ASSUMPTIONS VALIDATED:
        - All three scenarios present (baseline, moderate, stress)
        - Business model has all required methods and attributes
        - User calibration contains only allowed keys
        - Business model id and name are accessible (metadata)
        
        Raises:
            ValueError: If scenario keys, business model methods, or calibration keys invalid
            AttributeError: If business_model missing id or name attributes
        """
        # ===== SCENARIO STRUCTURE VALIDATION =====
        # ASSUMPTION: Three scenarios are required and cannot be reduced
        required_scenarios = {'baseline', 'moderate', 'stress'}
        provided = set(self.scenario_config.keys())
        
        if not required_scenarios.issubset(provided):
            missing = required_scenarios - provided
            raise ValueError(
                f"scenario_config missing required scenarios: {missing}. "
                f"All three scenarios required (baseline, moderate, stress). "
                f"Got: {provided}"
            )
        
        # ===== BUSINESS MODEL INTERFACE VALIDATION =====
        # ASSUMPTION: Business model is executable object with specific methods
        required_methods = [
            'calculate_annual_cash_flows',
            'get_stochastic_drivers',
            'get_policy_dependence'
        ]
        
        for method in required_methods:
            if not hasattr(self.business_model, method):
                raise AttributeError(
                    f"business_model missing method: {method}(). "
                    f"Class: {self.business_model.__class__.__name__}"
                )
            if not callable(getattr(self.business_model, method)):
                raise TypeError(
                    f"business_model.{method} must be callable. "
                    f"Got: {type(getattr(self.business_model, method))}"
                )
        
        # ASSUMPTION: Business model has id and name for audit trail
        if not hasattr(self.business_model, 'id'):
            raise AttributeError(
                f"business_model missing attribute: id. "
                f"Required for metadata assembly."
            )
        if not hasattr(self.business_model, 'name'):
            raise AttributeError(
                f"business_model missing attribute: name. "
                f"Required for metadata assembly."
            )
        
        # ===== USER CALIBRATION CONSTRAINT VALIDATION =====
        # ASSUMPTION: Users can adjust prices/volumes/costs but NOT structure
        # CONSTRAINT: Immutable per Golden Prompt
        forbidden_keys = {
            'revenue_structure',
            'cost_structure',
            'scenario_dominance',
            'bankability_formula',
            'stochastic_drivers',
            'policy_dependence'
        }
        
        overlap = forbidden_keys.intersection(self.user_calibration.keys())
        if overlap:
            raise ValueError(
                f"User calibration cannot modify: {overlap}. "
                f"These are immutable per Golden Prompt. "
                f"Allowed keys: prices, volumes, costs, discount_rate, duration"
            )
    
    def run_deterministic_analysis(self, scenario: str) -> Dict[str, Any]:
        """
        Run deterministic cash-flow analysis for ONE scenario.
        
        CRITICAL CONSTRAINT: This method processes ONE scenario ONLY.
        No cross-scenario comparison or blending.
        
        ASSUMPTION: Business model returns annual cash flows as deterministic value
        (same value repeated for all years; variability enters via stochastic drivers
        in Monte Carlo, not here).
        
        Args:
            scenario: str – one of 'baseline', 'moderate', or 'stress'
                     Specifies which scenario parameters to use
        
        Returns:
            Dict with deterministic results for THIS scenario ONLY:
            {
                'scenario': str,
                'annual_cash_flows': np.ndarray, shape (duration,),
                    all years have same CF value (stochastic variation in MC only)
                'cumulative_cash_flows': np.ndarray, shape (duration,),
                    cumulative sum (for payback analysis)
                'npv': float,
                    sum(annual_cf * discount_factors)
                'discount_rate': float,
                    user-supplied or default, per scenario
                'irr': Optional[float],
                    only if meaningful for this BM
                'payback_years': Optional[int],
                    only if meaningful for this BM
                'duration_years': int
            }
        
        Raises:
            ValueError: If scenario not in ['baseline', 'moderate', 'stress']
            KeyError: If required parameter missing
            TypeError: If business_model.calculate_annual_cash_flows() returns wrong type
        """
        # ===== SCENARIO VALIDATION =====
        if scenario not in {'baseline', 'moderate', 'stress'}:
            raise ValueError(
                f"Invalid scenario: '{scenario}'. "
                f"Must be one of: 'baseline', 'moderate', 'stress'. "
                f"Business model {self.business_model.id}: {self.business_model.name}"
            )
        
        # ===== PARAMETER ASSEMBLY (Scenario-Specific) =====
        # ASSUMPTION: scenario_config[scenario] has defaults
        # ASSUMPTION: user_calibration (if any) applies equally to all scenarios
        # No scenario-specific calibration; user overrides are global
        params = self._merge_scenario_with_calibration(scenario)
        
        # ===== DELEGATE TO BUSINESS MODEL (LAYER A) =====
        # ASSUMPTION: Business model computes all revenue/cost logic
        # This Engine does NOT implement business economics
        try:
            annual_cf = self.business_model.calculate_annual_cash_flows(params)
        except Exception as e:
            raise RuntimeError(
                f"Business model {self.business_model.id} calculation failed for "
                f"scenario '{scenario}'. Error: {str(e)}"
            )
        
        # Validate return type
        if not isinstance(annual_cf, np.ndarray):
            raise TypeError(
                f"business_model.calculate_annual_cash_flows() must return np.ndarray. "
                f"Got: {type(annual_cf).__name__} from {self.business_model.id}"
            )
        
        duration = len(annual_cf)
        discount_rate = params.get('discount_rate', 0.05)
        
        # ===== DETERMINISTIC METRICS =====
        # NPV calculation: standard financial formula
        # sum(CF_t * (1 + r)^(-t)) for t = 0, 1, ..., T-1
        discount_factors = np.array(
            [(1.0 + discount_rate) ** (-t) for t in range(duration)],
            dtype=np.float64
        )
        npv = float(np.sum(annual_cf * discount_factors))
        
        # Cumulative for payback analysis
        cumulative_cf = np.cumsum(annual_cf)
        
        # Conditional metrics (only if meaningful for this BM)
        irr = None
        payback = None
        
        if self._irr_meaningful(annual_cf):
            irr = self._compute_irr(annual_cf)
        
        if self._payback_meaningful(cumulative_cf):
            payback = self._compute_payback(cumulative_cf)
        
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
        Run Monte Carlo risk analysis for ONE scenario.
        
        CRITICAL CONSTRAINTS:
        1. Each scenario processed INDEPENDENTLY (no cross-scenario sampling)
        2. Bank-grade minimum: n_runs ≥ 20,000 (enforced, no shortcuts)
        3. Fixed random seed → reproducible results
        4. Stochastic drivers sourced from business model (not invented here)
        
        ASSUMPTION: Business model returns deterministic cash flows;
        stochastic variation introduced via driver multipliers (user calibration
        can control whether drivers are applied or not).
        
        Args:
            scenario: str – one of 'baseline', 'moderate', or 'stress'
            n_runs: int – Monte Carlo iterations (minimum 20,000 enforced)
            seed: int – fixed random seed for reproducibility
        
        Returns:
            Dict with risk metrics for THIS scenario ONLY:
            {
                'scenario': str,
                'n_runs': int,
                'seed': int,
                'npv_distribution': np.ndarray, shape (n_runs,),
                    full distribution of NPV outcomes
                'mean_npv': float,
                    arithmetic mean of distribution
                'median_npv': float,
                    50th percentile
                'std_npv': float,
                    standard deviation
                'p5_npv': float,
                    5th percentile (downside risk)
                'p50_npv': float,
                    50th percentile (same as median)
                'p95_npv': float,
                    95th percentile (upside potential)
                'prob_negative_npv': float ∈ [0, 1],
                    probability of loss
                'cvar5_npv': float,
                    Conditional Value at Risk (mean of 5% worst outcomes)
                'volatility_dcf': float,
                    volatility of discounted cash flows
                'driver_importance': Dict[str, float],
                    Tornado ranking of stochastic drivers
                'discount_rate': float,
                'duration_years': int
            }
        
        Raises:
            ValueError: If scenario invalid or n_runs < 20000
            RuntimeError: If Monte Carlo execution fails or NaN encountered
        """
        # ===== VALIDATION =====
        if scenario not in {'baseline', 'moderate', 'stress'}:
            raise ValueError(
                f"Invalid scenario: '{scenario}'. "
                f"Must be one of: 'baseline', 'moderate', 'stress'."
            )
        
        # BANK-GRADE STANDARD: Minimum 20,000 runs (no exceptions)
        if n_runs < 20000:
            raise ValueError(
                f"Monte Carlo requires n_runs ≥ 20,000 (bank-grade standard). "
                f"Got: {n_runs}. Smaller samples may hide tail risks. "
                f"Minimum enforced for all business models."
            )
        
        # ===== SEEDING =====
        # Fixed seed ensures reproducibility: same inputs → identical distribution
        np.random.seed(seed)
        
        # ===== PARAMETER ASSEMBLY =====
        params = self._merge_scenario_with_calibration(scenario)
        discount_rate = params.get('discount_rate', 0.05)
        duration = params.get('duration_years')
        
        if duration is None:
            raise ValueError(
                f"scenario_config['{scenario}'] missing 'duration_years'. "
                f"Required for NPV discount factor computation."
            )
        
        # ===== RETRIEVE STOCHASTIC DRIVERS (LAYER A) =====
        # ASSUMPTION: Business model defines which drivers apply to which revenues/costs
        stochastic_drivers = self.business_model.get_stochastic_drivers()
        
        if not stochastic_drivers:
            raise ValueError(
                f"Business model {self.business_model.id} has no stochastic drivers. "
                f"Cannot run Monte Carlo."
            )
        
        # ===== SAMPLE DRIVERS (Vectorized) =====
        # ASSUMPTION: Drivers are sampled independently (no correlation modeling)
        # Import here to avoid circular dependencies
        try:
            from engine.montecarlo import MonteCarloEngine
            mc_engine = MonteCarloEngine()
            # Note: montecarlo.py will handle triangular/uniform sampling
        except ImportError:
            raise ImportError(
                "Could not import montecarlo module. "
                "Ensure engine/montecarlo.py exists with MonteCarloEngine class."
            )
        
        # ===== MONTE CARLO LOOP: n_runs iterations =====
        # Each run: business_model.calculate_annual_cash_flows() called with different driver multipliers
        npv_distribution = np.zeros(n_runs, dtype=np.float64)
        
        # For simplicity, we compute driver samples inline (vectorized sampling)
        # In production, this would delegate to montecarlo.py for cleaner separation
        np.random.seed(seed)
        
        for i in range(n_runs):
            # Create run-specific parameters
            run_params = params.copy()
            
            # Sample each driver and apply multiplier
            for driver_name, driver_spec in stochastic_drivers.items():
                dist_type = driver_spec.get('type')
                min_mult = driver_spec.get('min_multiplier')
                max_mult = driver_spec.get('max_multiplier')
                
                if dist_type == 'triangular':
                    mode_mult = driver_spec.get('mode_multiplier')
                    multiplier = np.random.triangular(min_mult, mode_mult, max_mult)
                elif dist_type == 'uniform':
                    multiplier = np.random.uniform(min_mult, max_mult)
                else:
                    raise ValueError(
                        f"Unknown driver distribution type: {dist_type}. "
                        f"Must be 'triangular' or 'uniform'."
                    )
                
                run_params[f'{driver_name}_multiplier'] = multiplier
            
            # Delegate to business model
            try:
                annual_cf = self.business_model.calculate_annual_cash_flows(run_params)
            except Exception as e:
                raise RuntimeError(
                    f"Business model calculation failed at MC run {i}/{n_runs}. "
                    f"Scenario: {scenario}. Error: {str(e)}"
                )
            
            # Compute NPV for this run
            discount_factors = np.array(
                [(1.0 + discount_rate) ** (-t) for t in range(len(annual_cf))],
                dtype=np.float64
            )
            npv_distribution[i] = np.sum(annual_cf * discount_factors)
        
        # Check for catastrophic failure
        if np.any(np.isnan(npv_distribution)):
            nan_count = np.sum(np.isnan(npv_distribution))
            raise RuntimeError(
                f"NPV distribution contains {nan_count} NaN values (out of {n_runs}). "
                f"Check driver ranges and baseline parameter values for validity. "
                f"Scenario: {scenario}"
            )
        
        # ===== COMPUTE RISK METRICS FROM DISTRIBUTION =====
        mean_npv = float(np.mean(npv_distribution))
        median_npv = float(np.median(npv_distribution))
        std_npv = float(np.std(npv_distribution))
        p5_npv = float(np.percentile(npv_distribution, 5))
        p50_npv = float(np.percentile(npv_distribution, 50))
        p95_npv = float(np.percentile(npv_distribution, 95))
        
        # Probability of loss
        prob_negative_npv = float(np.mean(npv_distribution < 0))
        
        # CVaR5: Conditional Value at Risk at 5% tail
        var_5_threshold = np.percentile(npv_distribution, 5)
        worst_5_percent = npv_distribution[npv_distribution <= var_5_threshold]
        cvar5_npv = float(np.mean(worst_5_percent)) if len(worst_5_percent) > 0 else var_5_threshold
        
        # Volatility of discounted cash flows
        volatility_dcf = self._compute_volatility_dcf(
            npv_distribution, mean_npv
        )
        
        # Driver importance ranking (Tornado)
        driver_importance = self._compute_driver_importance(
            stochastic_drivers, npv_distribution
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
            'prob_negative_npv': prob_negative_npv,
            'cvar5_npv': cvar5_npv,
            'volatility_dcf': volatility_dcf,
            'driver_importance': driver_importance,
            'discount_rate': discount_rate,
            'duration_years': duration
        }
    
    def evaluate_all_scenarios(self, n_runs: int = 20000) -> Dict[str, Any]:
        """
        Evaluate all three scenarios: Baseline, Moderate, Stress (independently).
        
        CRITICAL CONSTRAINTS (Golden Prompt):
        1. STRESS SCENARIO IS BINDING: min(BI_baseline, BI_moderate, BI_stress)
        2. NO SCENARIO AVERAGING: Results kept separate
        3. NO IMPLICIT NORMALIZATION: Raw values returned
        4. SCENARIO ORDERING IMMUTABLE: baseline → moderate → stress (always)
        
        ASSUMPTION: Bankability Index calculation is LAYER B responsibility.
        This method returns results to bankability.py for BI computation.
        
        Args:
            n_runs: int – Monte Carlo runs PER SCENARIO (default 20,000)
        
        Returns:
            Dict with THREE INDEPENDENT scenario results:
            {
                'baseline': {
                    'deterministic': {...},
                    'monte_carlo': {...}
                },
                'moderate': {
                    'deterministic': {...},
                    'monte_carlo': {...}
                },
                'stress': {
                    'deterministic': {...},
                    'monte_carlo': {...}
                },
                'business_model_id': str,
                'business_model_name': str,
                'policy_dependence': float,
                'user_calibration_applied': Dict,
                'stress_scenario_note': str,
                    (emphasizes stress dominance)
                'disclaimer': str
                    (mandatory Golden Prompt disclaimer)
            }
        
        Note: Each scenario result is complete and independent.
              Bankability layer will apply: BI_overall = min(BI_baseline, BI_moderate, BI_stress)
        """
        results = {}
        
        # ===== EVALUATE ALL THREE SCENARIOS (INDEPENDENTLY) =====
        # CRITICAL: Each scenario processed separately, no blending or averaging
        for scenario in ['baseline', 'moderate', 'stress']:
            try:
                det = self.run_deterministic_analysis(scenario)
                mc = self.run_monte_carlo_analysis(scenario, n_runs=n_runs)
                
                results[scenario] = {
                    'deterministic': det,
                    'monte_carlo': mc
                }
            except Exception as e:
                raise RuntimeError(
                    f"Failed to evaluate scenario '{scenario}' for "
                    f"business model {self.business_model.id}. Error: {str(e)}"
                )
        
        # ===== ASSEMBLE METADATA =====
        results['business_model_id'] = self.business_model.id
        results['business_model_name'] = self.business_model.name
        results['policy_dependence'] = self.business_model.get_policy_dependence()
        results['user_calibration_applied'] = self.user_calibration
        
        # ===== STRESS-SCENARIO DOMINANCE (NON-NEGOTIABLE) =====
        # CONSTRAINT: Communicate to user that stress scenario is binding
        # This prevents misinterpretation of baseline/moderate as "better" outcomes
        results['stress_scenario_note'] = (
            "STRESS SCENARIO IS BINDING. Bankability classification determined by stress scenario. "
            "Overall Bankability Index = min(BI_baseline, BI_moderate, BI_stress). "
            "This rule ensures downside-risk visibility prevails over apparent baseline optimism. "
            "All three scenario indices are computed independently; stress result determines overall classification."
        )
        
        # ===== MANDATORY DISCLAIMER (GOLDEN PROMPT REQUIREMENT) =====
        results['disclaimer'] = (
            "This tool provides scenario-based decision support only. "
            "Results depend on assumptions, parameter calibration, and model structure. "
            "It does not constitute an investment recommendation or funding commitment."
        )
        
        return results
    
    # ========== PRIVATE HELPERS ==========
    
    def _merge_scenario_with_calibration(self, scenario: str) -> Dict[str, Any]:
        """
        Merge scenario-specific defaults with user calibration overrides.
        
        ASSUMPTION: User calibration applies equally to all scenarios
        (not scenario-specific overrides).
        
        Args:
            scenario: str – 'baseline', 'moderate', or 'stress'
        
        Returns:
            Merged parameters dict for this scenario
        """
        # Start with scenario defaults
        merged = self.scenario_config[scenario].copy()
        
        # Apply user overrides (if any)
        # Allowed keys only (validated at __init__)
        for key, value in self.user_calibration.items():
            merged[key] = value
        
        return merged
    
    def _irr_meaningful(self, annual_cash_flows: np.ndarray) -> bool:
        """
        Check if IRR computation is meaningful for this business model.
        
        ASSUMPTION: Not all BMs have meaningful IRR.
        - Some may have all-positive CF (no payback, no meaningful IRR)
        - Some may have perpetual revenue streams (cemetery, risk fund)
        - Only compute IRR if cash flows change sign at least once
        
        Args:
            annual_cash_flows: np.ndarray of annual cash flows
        
        Returns:
            bool – True if IRR is mathematically meaningful
        """
        if len(annual_cash_flows) < 2:
            return False
        
        # Check for sign change (necessary for IRR to be real)
        signs = np.sign(annual_cash_flows)
        sign_changes = np.sum(np.abs(np.diff(signs)) > 0)
        
        return sign_changes > 0
    
    def _payback_meaningful(self, cumulative_cash_flows: np.ndarray) -> bool:
        """
        Check if payback period is meaningful for this business model.
        
        ASSUMPTION: Some BMs (e.g., perpetual payment streams) may never
        achieve positive cumulative CF in finite time. For those, payback
        is not meaningful.
        
        Args:
            cumulative_cash_flows: np.ndarray of cumulative cash flows
        
        Returns:
            bool – True if payback occurs (cumulative becomes non-negative)
        """
        return float(np.max(cumulative_cash_flows)) >= 0
    
    def _compute_irr(self, annual_cash_flows: np.ndarray) -> Optional[float]:
        """
        Compute Internal Rate of Return using numerical root-finding.
        
        IRR is the discount rate r where NPV = sum(CF_t / (1+r)^t) = 0
        
        Args:
            annual_cash_flows: np.ndarray of annual cash flows
        
        Returns:
            float – IRR as decimal (e.g., 0.12 for 12%), or None if no root
        """
        from scipy.optimize import newton
        
        def npv_func(r):
            discount_factors = np.array(
                [(1.0 + r) ** (-t) for t in range(len(annual_cash_flows))],
                dtype=np.float64
            )
            return np.sum(annual_cash_flows * discount_factors)
        
        try:
            irr = newton(npv_func, 0.10, maxiter=100)
            return float(irr) if not np.isnan(irr) else None
        except (RuntimeError, OverflowError, ValueError):
            # Root-finding failed; no real IRR exists
            return None
    
    def _compute_payback(self, cumulative_cash_flows: np.ndarray) -> Optional[int]:
        """
        Compute payback period in years (first year cumulative CF ≥ 0).
        
        Args:
            cumulative_cash_flows: np.ndarray of cumulative cash flows
        
        Returns:
            int – payback year (0-indexed), or None if never breaks even
        """
        positive_indices = np.where(cumulative_cash_flows >= 0)[0]
        if len(positive_indices) > 0:
            return int(positive_indices[0])
        return None
    
    def _compute_volatility_dcf(
        self,
        npv_distribution: np.ndarray,
        mean_npv: float
    ) -> float:
        """
        Compute volatility of discounted cash flows.
        
        This is the standard deviation of the NPV distribution,
        normalized by the mean to reflect relative variability.
        
        Args:
            npv_distribution: np.ndarray of NPV values from MC run
            mean_npv: float – arithmetic mean of distribution
        
        Returns:
            float – volatility metric
        """
        std_npv = float(np.std(npv_distribution))
        if mean_npv == 0:
            # Avoid division by zero
            return std_npv
        return std_npv / abs(mean_npv)
    
    def _compute_driver_importance(
        self,
        stochastic_drivers: Dict[str, Dict[str, Any]],
        npv_distribution: np.ndarray
    ) -> Dict[str, float]:
        """
        Rank stochastic driver importance via Tornado analysis.
        
        Simple ranking: Return uniform importance if no variance.
        More sophisticated: Compare driver variance contribution.
        
        ASSUMPTION: Drivers sampled independently (no correlations).
        
        Args:
            stochastic_drivers: Dict of driver specifications
            npv_distribution: np.ndarray of NPV outcomes from MC
        
        Returns:
            Dict[driver_name, importance_score] where scores sum ≈ 1.0
        """
        # Placeholder: Equal importance to all drivers
        # In production, this would compute driver sensitivity via perturbation analysis
        n_drivers = len(stochastic_drivers)
        if n_drivers == 0:
            return {}
        
        equal_share = 1.0 / n_drivers
        return {name: equal_share for name in stochastic_drivers.keys()}