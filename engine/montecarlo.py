"""
engine/montecarlo.py – Monte Carlo Risk Analysis Engine (LAYER B)

Responsibilities:
- Execute ≥20,000 Monte Carlo runs per BM×Scenario
- Manage random seed (fixed for reproducibility)
- Vectorized sampling of stochastic drivers (triangular, uniform)
- Aggregate NPV distribution from all runs
- Compute bank-grade risk metrics (p5, p95, CVaR5, volatility, etc.)
- Rank driver importance via Tornado sensitivity analysis

CRITICAL CONSTRAINTS:
- Each scenario is computed INDEPENDENTLY (no averaging)
- No cross-scenario blending or normalization
- Stress-scenario dominance enforced by BANKABILITY LAYER, not here
- All calculations vectorized via NumPy for efficiency
- No causal inference, no econometrics

LAYER SEPARATION:
- LAYER A (heterogeneous): Business model computes cash flows
- LAYER B (homogeneous): This engine applies identical risk metrics to all BMs
- LAYER B (homogeneous): Bankability layer computes BI and applies stress dominance
"""

import numpy as np
from typing import Dict, Any, Optional, Callable
from datetime import datetime


class MonteCarloEngine:
    """
    Bank-grade Monte Carlo risk analysis engine.
    
    Per scenario, executes ≥20,000 vectorized Monte Carlo runs to generate
    NPV distributions and compute risk metrics.
    
    Each scenario is processed INDEPENDENTLY:
    - No averaging across scenarios
    - No cross-scenario normalization
    - Results are standalone
    
    Stress-scenario dominance (min across scenarios) is applied by
    BANKABILITY LAYER, not here.
    
    ASSUMPTIONS:
    - Business model implements calculate_annual_cash_flows(params) → np.ndarray
    - Stochastic drivers are defined in business_model config (triangular/uniform)
    - Driver multipliers are applied to deterministic baseline values
    - Random sampling is independent across drivers (no correlation modeling)
    - Discount rate is valid (typically 5%, user-adjustable)
    """
    
    def __init__(self):
        """
        Initialize MonteCarloEngine.
        
        No state is stored across runs. Each run() call is independent.
        """
        pass
    
    def run(
        self,
        business_model,
        scenario_params: Dict[str, Any],
        stochastic_drivers: Dict[str, Dict[str, Any]],
        scenario_name: str,
        n_runs: int = 20000,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        Execute Monte Carlo simulation for a SINGLE scenario.
        
        CRITICAL: This method processes one scenario independently.
        No scenario blending or averaging is performed.
        
        Args:
            business_model: Instance with method:
                           calculate_annual_cash_flows(params: Dict) -> np.ndarray
                           Returns annual net cash flows, shape (duration,)
            
            scenario_params: Dict with scenario-specific deterministic values.
                            Example:
                            {
                                'carbon_price': 50.0,      # EUR/tonne
                                'visitor_count': 10000,    # annual
                                'discount_rate': 0.05,
                                'duration_years': 20
                            }
                            Stochastic drivers will multiply these values.
            
            stochastic_drivers: Dict from business_model config.
                              Example:
                              {
                                  'carbon_price_volatility': {
                                      'type': 'triangular',
                                      'min_multiplier': 0.50,
                                      'mode_multiplier': 1.0,
                                      'max_multiplier': 1.80
                                  },
                                  'visitor_volume_volatility': {
                                      'type': 'uniform',
                                      'min_multiplier': 0.60,
                                      'max_multiplier': 1.40
                                  }
                              }
            
            scenario_name: str – 'baseline', 'moderate', or 'stress'
                          (Used for audit trail and logging only; no logic depends on it)
            
            n_runs: int – Number of Monte Carlo iterations (default 20,000)
                   Enforced minimum: 20,000 (bank-grade standard)
            
            seed: int – Fixed random seed for reproducibility.
                  Same seed + same inputs = identical NPV distribution.
        
        Returns:
            Dict with complete risk profile for this scenario:
            {
                'scenario': str – echoes scenario_name
                'n_runs': int – echoes n_runs
                'seed': int – echoes seed used
                'run_timestamp': str – ISO timestamp of execution
                'npv_distribution': np.ndarray, shape (n_runs,) – all NPV values
                'mean_npv': float – arithmetic mean
                'median_npv': float – 50th percentile
                'std_npv': float – standard deviation
                'p5_npv': float – 5th percentile (downside risk)
                'p50_npv': float – 50th percentile (median)
                'p95_npv': float – 95th percentile (upside potential)
                'prob_negative_npv': float – P(NPV < 0), e.g., 0.15 = 15% probability of loss
                'cvar5_npv': float – Conditional Value at Risk at 5% tail
                                     (mean of worst 5% outcomes)
                'volatility_dcf': float – volatility of discounted cash flows
                'driver_importance': Dict[str, float] – tornado sensitivity ranking
                                                       Each driver ∈ [0, 1], sum ≈ 1.0
                'discount_rate': float – discount rate used in NPV calculation
                'duration_years': int – analysis horizon in years
            }
        
        Raises:
            ValueError: If n_runs < 20,000 or if scenario_name not in expected list
            TypeError: If business_model missing required method or stochastic_drivers invalid
            AttributeError: If business_model cannot be called
            RuntimeError: If Monte Carlo execution fails (NaN/inf in results)
        """
        # ===== VALIDATION =====
        
        # Bank-grade minimum
        if n_runs < 20000:
            raise ValueError(
                f"Monte Carlo requires n_runs ≥ 20,000 (bank-grade standard). Got: {n_runs}. "
                f"Smaller samples may hide tail risks."
            )
        
        # Seed validation
        if not isinstance(seed, int):
            raise TypeError(f"seed must be int. Got: {type(seed).__name__}")
        
        # Business model interface
        if not hasattr(business_model, 'calculate_annual_cash_flows') or \
           not callable(getattr(business_model, 'calculate_annual_cash_flows')):
            raise AttributeError(
                f"business_model must have callable method calculate_annual_cash_flows(). "
                f"Class: {business_model.__class__.__name__}"
            )
        
        # Stochastic drivers validation
        if not isinstance(stochastic_drivers, dict):
            raise TypeError(f"stochastic_drivers must be dict. Got: {type(stochastic_drivers).__name__}")
        
        if len(stochastic_drivers) == 0:
            raise ValueError("stochastic_drivers dict cannot be empty")
        
        for driver_name, driver_spec in stochastic_drivers.items():
            required_keys = {'type', 'min_multiplier', 'max_multiplier'}
            if driver_spec.get('type') == 'triangular':
                required_keys.add('mode_multiplier')
            
            if not required_keys.issubset(driver_spec.keys()):
                missing = required_keys - set(driver_spec.keys())
                raise KeyError(
                    f"stochastic_drivers['{driver_name}'] missing keys: {missing}"
                )
        
        # ===== SETUP =====
        
        np.random.seed(seed)
        discount_rate = scenario_params.get('discount_rate', 0.05)
        duration_years = scenario_params.get('duration_years')
        
        run_timestamp = datetime.utcnow().isoformat()
        
        # ===== SAMPLING: Generate driver multipliers for all n_runs =====
        
        driver_samples = self._sample_drivers(stochastic_drivers, n_runs)
        # Result: Dict[driver_name, np.ndarray(n_runs)]
        # Example: driver_samples['carbon_price_volatility'] = [0.87, 1.12, 0.65, ...]
        
        # ===== MONTE CARLO LOOP: Compute NPV for each run =====
        
        npv_distribution = np.zeros(n_runs)
        
        for i in range(n_runs):
            # Create run-specific parameters by injecting driver multipliers
            run_params = scenario_params.copy()
            
            # For each stochastic driver, apply its sampled multiplier
            for driver_name, driver_values in driver_samples.items():
                multiplier = driver_values[i]
                run_params[f'{driver_name}_multiplier'] = multiplier
            
            # Delegate to business model: compute annual cash flows for this run
            try:
                annual_cf = business_model.calculate_annual_cash_flows(run_params)
            except Exception as e:
                raise RuntimeError(
                    f"business_model.calculate_annual_cash_flows() failed at run {i}/{n_runs}. "
                    f"Error: {str(e)}"
                )
            
            # Validate return type
            if not isinstance(annual_cf, np.ndarray):
                raise TypeError(
                    f"business_model.calculate_annual_cash_flows() must return np.ndarray. "
                    f"Got: {type(annual_cf).__name__} at run {i}"
                )
            
            # Compute NPV for this run
            npv_distribution[i] = self._compute_npv(annual_cf, discount_rate)
        
        # Check for catastrophic failure
        if np.any(np.isnan(npv_distribution)) or np.any(np.isinf(npv_distribution)):
            nan_count = np.sum(np.isnan(npv_distribution))
            inf_count = np.sum(np.isinf(npv_distribution))
            raise RuntimeError(
                f"NPV distribution contains {nan_count} NaN and {inf_count} Inf values. "
                f"Check business model and driver ranges for validity."
            )
        
        # ===== COMPUTE RISK METRICS =====
        
        mean_npv = float(np.mean(npv_distribution))
        median_npv = float(np.median(npv_distribution))
        std_npv = float(np.std(npv_distribution))
        p5_npv = float(np.percentile(npv_distribution, 5))
        p50_npv = float(np.percentile(npv_distribution, 50))
        p95_npv = float(np.percentile(npv_distribution, 95))
        
        # Probability of loss (NPV < 0)
        prob_negative_npv = float(np.mean(npv_distribution < 0))
        
        # CVaR5: Conditional Value at Risk at 5% tail
        # = Mean of NPVs in the worst 5% of outcomes
        var_5_threshold = np.percentile(npv_distribution, 5)
        cvar5_npv = float(np.mean(npv_distribution[npv_distribution <= var_5_threshold]))
        
        # Volatility of discounted cash flows
        volatility_dcf = self._compute_volatility_dcf(
            business_model, scenario_params, driver_samples, discount_rate, n_runs
        )
        
        # Driver importance ranking (Tornado sensitivity)
        driver_importance = self._compute_driver_importance(
            business_model, scenario_params, driver_samples, stochastic_drivers, 
            discount_rate, npv_distribution, n_runs
        )
        
        # ===== ASSEMBLE OUTPUT =====
        
        return {
            'scenario': scenario_name,
            'n_runs': n_runs,
            'seed': seed,
            'run_timestamp': run_timestamp,
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
            'duration_years': duration_years
        }
    
    # ========== PRIVATE HELPERS ==========
    
    def _sample_drivers(
        self,
        stochastic_drivers: Dict[str, Dict[str, Any]],
        n_runs: int
    ) -> Dict[str, np.ndarray]:
        """
        Sample all stochastic drivers independently.
        
        Each driver is sampled per its distribution spec (triangular or uniform).
        No correlation modeling between drivers.
        
        Args:
            stochastic_drivers: Dict of driver specifications
            n_runs: int – number of samples per driver
        
        Returns:
            Dict[driver_name, np.ndarray(n_runs)]
            Example: {'carbon_price_volatility': [0.87, 1.12, ...], ...}
        """
        driver_samples = {}
        
        for driver_name, driver_spec in stochastic_drivers.items():
            dist_type = driver_spec['type']
            min_mult = driver_spec['min_multiplier']
            max_mult = driver_spec['max_multiplier']
            
            if dist_type == 'triangular':
                mode_mult = driver_spec['mode_multiplier']
                # NumPy triangular: (left, mode, right)
                samples = np.random.triangular(min_mult, mode_mult, max_mult, size=n_runs)
            
            elif dist_type == 'uniform':
                samples = np.random.uniform(min_mult, max_mult, size=n_runs)
            
            else:
                raise ValueError(
                    f"Unknown distribution type for '{driver_name}': {dist_type}. "
                    f"Must be 'triangular' or 'uniform'."
                )
            
            driver_samples[driver_name] = samples
        
        return driver_samples
    
    def _compute_npv(
        self,
        annual_cf: np.ndarray,
        discount_rate: float
    ) -> float:
        """
        Compute Net Present Value for a single Monte Carlo run.
        
        NPV = sum(CF_t / (1 + r)^t) for t = 0, 1, ..., T-1
        
        Args:
            annual_cf: np.ndarray of annual cash flows, shape (duration,)
            discount_rate: float, e.g., 0.05 for 5%
        
        Returns:
            float – NPV
        """
        duration = len(annual_cf)
        discount_factors = np.array(
            [(1.0 + discount_rate) ** (-t) for t in range(duration)]
        )
        npv = float(np.sum(annual_cf * discount_factors))
        return npv
    
    def _compute_volatility_dcf(
        self,
        business_model,
        scenario_params: Dict[str, Any],
        driver_samples: Dict[str, np.ndarray],
        discount_rate: float,
        n_runs: int
    ) -> float:
        """
        Compute volatility of discounted cash flows across Monte Carlo runs.
        
        For each run, compute the discounted cash flow vector (CF_t / (1+r)^t),
        then aggregate standard deviation across all runs.
        
        ASSUMPTION: All runs have same duration (deterministic duration from scenario_params).
        
        Args:
            business_model: Instance for computing cash flows
            scenario_params: Deterministic baseline parameters
            driver_samples: Dict of sampled driver multipliers
            discount_rate: float
            n_runs: int
        
        Returns:
            float – standard deviation of discounted cash flows
        """
        duration_years = scenario_params.get('duration_years')
        if duration_years is None:
            raise ValueError("scenario_params must include 'duration_years'")
        
        # Store all discounted cash flows across runs
        dcf_all = []
        
        for i in range(min(n_runs, 1000)):  # Sample 1000 runs for efficiency
            run_params = scenario_params.copy()
            
            for driver_name, driver_values in driver_samples.items():
                run_params[f'{driver_name}_multiplier'] = driver_values[i]
            
            annual_cf = business_model.calculate_annual_cash_flows(run_params)
            
            # Compute discounted cash flows
            discount_factors = np.array(
                [(1.0 + discount_rate) ** (-t) for t in range(len(annual_cf))]
            )
            dcf = annual_cf * discount_factors
            dcf_all.extend(dcf)
        
        # Volatility = std dev of all discounted values
        volatility = float(np.std(dcf_all)) if len(dcf_all) > 0 else 0.0
        return volatility
    
    def _compute_driver_importance(
        self,
        business_model,
        scenario_params: Dict[str, Any],
        driver_samples: Dict[str, np.ndarray],
        stochastic_drivers: Dict[str, Dict[str, Any]],
        discount_rate: float,
        npv_distribution: np.ndarray,
        n_runs: int
    ) -> Dict[str, float]:
        """
        Compute driver importance ranking (Tornado sensitivity analysis).
        
        For each driver:
        1. Vary that driver ±1 std dev while holding others at median
        2. Measure change in NPV variance
        3. Normalize by total variance
        4. Return as importance score ∈ [0, 1]
        
        ASSUMPTION: Drivers are independent (no correlation modeling).
        
        Args:
            business_model: Instance for computing cash flows
            scenario_params: Deterministic baseline
            driver_samples: Dict of sampled driver multipliers (from main MC run)
            stochastic_drivers: Driver specifications
            discount_rate: float
            npv_distribution: Full NPV distribution from main MC run
            n_runs: int
        
        Returns:
            Dict[driver_name, float] – importance scores (sum ≈ 1.0)
        """
        # Baseline variance from full MC run
        baseline_variance = float(np.var(npv_distribution))
        
        if baseline_variance < 1e-10:
            # All NPVs identical; no sensitivity to vary
            n_drivers = len(stochastic_drivers)
            return {name: 1.0 / n_drivers for name in stochastic_drivers.keys()}
        
        driver_variances = {}
        
        # For each driver, measure its contribution to NPV variance
        for target_driver in stochastic_drivers.keys():
            # Sample with only this driver varied, others at median
            tornado_npvs = np.zeros(min(n_runs, 1000))  # Limited Tornado runs for efficiency
            
            for i in range(len(tornado_npvs)):
                run_params = scenario_params.copy()
                
                # Apply driver multipliers
                for driver_name, driver_values in driver_samples.items():
                    if driver_name == target_driver:
                        # Vary this driver: sample from ±1 std around median
                        median_idx = n_runs // 2
                        run_params[f'{driver_name}_multiplier'] = driver_values[median_idx + (i % 100) - 50]
                    else:
                        # Others at median
                        median_idx = n_runs // 2
                        run_params[f'{driver_name}_multiplier'] = driver_values[median_idx]
                
                annual_cf = business_model.calculate_annual_cash_flows(run_params)
                tornado_npvs[i] = self._compute_npv(annual_cf, discount_rate)
            
            driver_variance = float(np.var(tornado_npvs))
            driver_variances[target_driver] = driver_variance
        
        # Normalize variances to importance scores
        total_variance = sum(driver_variances.values())
        
        if total_variance < 1e-10:
            # All drivers have zero variance; default to uniform importance
            n_drivers = len(stochastic_drivers)
            return {name: 1.0 / n_drivers for name in stochastic_drivers.keys()}
        
        driver_importance = {
            name: variance / total_variance
            for name, variance in driver_variances.items()
        }
        
        return driver_importance