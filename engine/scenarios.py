"""
engine/scenarios.py – Scenario Manager & Deterministic Cash Flow Engine

Responsibilities:
- Manage three scenarios: Baseline, Moderate, Stress (ordering, structure)
- Compute deterministic cash flows for each scenario independently
- No scenario averaging
- No scenario mixing
- Delegate to business model for cash flow generation

LAYER A (heterogeneous): Business model generates cash flows
LAYER B (homogeneous): [Bankability handles risk metrics, not here]
"""

import numpy as np
from typing import Dict, Any, Optional
from scipy.optimize import newton


SCENARIO_ORDER = ["baseline", "moderate", "stress"]
"""
Immutable scenario ordering. Cannot be changed by user.
Stress scenario will always be binding (handled at LAYER B).
"""


class ScenarioManager:
    """
    Manages deterministic evaluation across three scenarios.
    
    Each scenario is computed INDEPENDENTLY:
    - No averaging
    - No blending
    - Results are separate
    
    Stress-scenario dominance is enforced at LAYER B (bankability), not here.
    """
    
    def __init__(
        self,
        scenario_config: Optional[Dict[str, Dict[str, Any]]] = None
    ):
        """
        Initialize ScenarioManager.
        
        Args:
            scenario_config: Dict with keys 'baseline', 'moderate', 'stress'.
                            Each maps to scenario parameters (prices, volumes, etc.).
                            Source: config/scenarios.yaml or user-provided.
                            If None, defaults are used (minimal fallback).
        
        Raises:
            ValueError: If scenario_config is provided but missing required keys.
        """
        self.scenario_config = scenario_config or {}
        
        # Validate: if config provided, must have all three scenarios
        if scenario_config:
            required_scenarios = set(SCENARIO_ORDER)
            provided_scenarios = set(scenario_config.keys())
            if not required_scenarios.issubset(provided_scenarios):
                missing = required_scenarios - provided_scenarios
                raise ValueError(
                    f"scenario_config missing required scenarios: {missing}. "
                    f"Must contain: {required_scenarios}"
                )
    
    def get_ordered_scenarios(self) -> list:
        """
        Return scenario ordering (immutable).
        
        Returns:
            List: ['baseline', 'moderate', 'stress']
        """
        return SCENARIO_ORDER.copy()
    
    def run_deterministic(
        self,
        business_model,
        scenario: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run deterministic cash-flow analysis for a single scenario.
        
        CRITICAL REQUIREMENTS:
        - business_model MUST implement calculate_annual_cash_flows(params) → np.ndarray
        - annual_cf[t] = net cash flow in year t (can be negative)
        - Each scenario is computed INDEPENDENTLY (no averaging with other scenarios)
        - No mixing of scenario parameters
        
        Args:
            business_model: Instance with method:
                           calculate_annual_cash_flows(params: Dict) -> np.ndarray
            scenario: str – one of 'baseline', 'moderate', 'stress'
            parameters: Optional user-provided parameters (override scenario defaults)
        
        Returns:
            Dict with deterministic results:
            {
                'scenario': str,
                'annual_cash_flows': np.ndarray, shape (duration,),
                'cumulative_cash_flows': np.ndarray, shape (duration,),
                'npv': float,
                'discount_rate': float,
                'irr': Optional[float],
                'payback_years': Optional[int],
                'duration_years': int
            }
        
        Raises:
            ValueError: If scenario not in ['baseline', 'moderate', 'stress']
            TypeError: If business_model.calculate_annual_cash_flows() doesn't return np.ndarray
            AttributeError: If business_model missing required method
        """
        # Validate scenario
        if scenario not in SCENARIO_ORDER:
            raise ValueError(
                f"scenario must be one of {SCENARIO_ORDER}. Got: {scenario}"
            )
        
        # Validate business model interface
        if not hasattr(business_model, 'calculate_annual_cash_flows'):
            raise AttributeError(
                f"business_model must implement calculate_annual_cash_flows(). "
                f"Class: {business_model.__class__.__name__}"
            )
        
        # Merge parameters: scenario default + user override
        merged_params = self._merge_scenario_params(scenario, parameters)
        
        # Get discount rate (user override or default)
        discount_rate = merged_params.get('discount_rate', 0.05)
        
        # DELEGATE TO BUSINESS MODEL: calculate annual cash flows
        annual_cf = business_model.calculate_annual_cash_flows(merged_params)
        
        # Validate return type
        if not isinstance(annual_cf, np.ndarray):
            raise TypeError(
                f"business_model.calculate_annual_cash_flows() must return np.ndarray. "
                f"Got: {type(annual_cf).__name__}"
            )
        
        duration = len(annual_cf)
        
        # Compute NPV
        npv = self._compute_npv(annual_cf, discount_rate)
        
        # Compute cumulative cash flows (for payback, visualization)
        cumulative_cf = np.cumsum(annual_cf)
        
        # Compute payback (only if meaningful)
        payback = None
        if self._is_payback_meaningful(cumulative_cf):
            payback = self._compute_payback(cumulative_cf)
        
        # Compute IRR (only if meaningful)
        irr = None
        if self._is_irr_meaningful(annual_cf):
            irr = self._compute_irr(annual_cf)
        
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
    
    # ---------- Private Helpers ----------
    
    def _merge_scenario_params(
        self,
        scenario: str,
        user_params: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge scenario-specific defaults with user overrides.
        
        Precedence: user_params > scenario_config[scenario] > global defaults
        
        Args:
            scenario: str – 'baseline', 'moderate', or 'stress'
            user_params: Optional user-provided overrides
        
        Returns:
            Merged parameter dict
        """
        # Start with scenario-specific config (if available)
        merged = {}
        if scenario in self.scenario_config:
            merged = self.scenario_config[scenario].copy()
        
        # Apply user overrides
        if user_params:
            merged.update(user_params)
        
        return merged
    
    def _compute_npv(
        self,
        annual_cf: np.ndarray,
        discount_rate: float
    ) -> float:
        """
        Compute Net Present Value.
        
        NPV = sum(CF_t / (1 + r)^t) for t = 0, 1, ..., T-1
        
        Args:
            annual_cf: np.ndarray of annual cash flows
            discount_rate: float, e.g., 0.05 for 5%
        
        Returns:
            NPV as float
        """
        duration = len(annual_cf)
        discount_factors = np.array(
            [(1.0 + discount_rate) ** (-t) for t in range(duration)]
        )
        npv = np.sum(annual_cf * discount_factors)
        return float(npv)
    
    def _compute_payback(
        self,
        cumulative_cf: np.ndarray
    ) -> Optional[int]:
        """
        Compute payback period (in years).
        
        Payback is the first year where cumulative CF becomes non-negative.
        
        Args:
            cumulative_cf: np.ndarray of cumulative cash flows
        
        Returns:
            int: payback year (0-indexed), or None if never becomes positive
        """
        positive_indices = np.where(cumulative_cf >= 0)[0]
        if len(positive_indices) > 0:
            return int(positive_indices[0])
        return None
    
    def _compute_irr(
        self,
        annual_cf: np.ndarray,
        initial_guess: float = 0.10
    ) -> Optional[float]:
        """
        Compute Internal Rate of Return via numerical root-finding.
        
        IRR is the discount rate r where NPV = 0:
        sum(CF_t / (1 + r)^t) = 0
        
        Uses Newton-Raphson method via scipy.optimize.newton.
        
        Args:
            annual_cf: np.ndarray of annual cash flows
            initial_guess: float, starting point for root-finding (default 10%)
        
        Returns:
            float: IRR as decimal (e.g., 0.15 for 15%), or None if no root found
        """
        def npv_func(r):
            """NPV as function of discount rate r."""
            discount_factors = np.array(
                [(1.0 + r) ** (-t) for t in range(len(annual_cf))]
            )
            return np.sum(annual_cf * discount_factors)
        
        def npv_derivative(r):
            """Derivative of NPV w.r.t. r (for Newton-Raphson)."""
            discount_factors = np.array(
                [(1.0 + r) ** (-t - 1) for t in range(len(annual_cf))]
            )
            return np.sum(-t * annual_cf * discount_factors)
        
        try:
            # Newton-Raphson to find IRR
            irr = newton(npv_func, initial_guess, fprime=npv_derivative, maxiter=100)
            return float(irr)
        except (RuntimeError, OverflowError, ZeroDivisionError):
            # Root-finding failed (e.g., no real root exists)
            return None
    
    def _is_irr_meaningful(self, annual_cf: np.ndarray) -> bool:
        """
        Check if IRR computation is meaningful.
        
        IRR is only meaningful if cash flows change sign at least once
        (e.g., initial investment followed by positive returns).
        
        Args:
            annual_cf: np.ndarray of annual cash flows
        
        Returns:
            bool: True if IRR is meaningful, False otherwise
        """
        if len(annual_cf) < 2:
            return False
        
        # Check for sign change
        signs = np.sign(annual_cf)
        sign_changes = np.sum(np.abs(np.diff(signs)) > 0)
        
        return sign_changes > 0
    
    def _is_payback_meaningful(self, cumulative_cf: np.ndarray) -> bool:
        """
        Check if payback period is meaningful.
        
        Payback is only meaningful if cumulative cash flows eventually become positive
        (i.e., the project breaks even).
        
        Some projects (e.g., perpetual payment-for-services) may never break even
        but still be bankable.
        
        Args:
            cumulative_cf: np.ndarray of cumulative cash flows
        
        Returns:
            bool: True if payback occurs, False otherwise
        """
        return np.max(cumulative_cf) >= 0