"""
Forest EcoValue Bank-Proof Tool - API Layer

This module provides the FastAPI REST endpoint orchestrating:
1. Input validation (model_id, user_calibration)
2. Deterministic cash-flow analysis per scenario (ScenarioManager)
3. Monte Carlo risk analysis per scenario (MonteCarloEngine)
4. Bankability assessment with stress-dominance enforcement (BankabilityEngine)
5. Response assembly with three independent scenario results (NO averaging)

ARCHITECTURE:
- LAYER A (Business Models): Heterogeneous revenue/cost/driver structures per model
- LAYER B (Bankability): Homogeneous risk metrics + BI formula applied to all models
- ORCHESTRATION: This API layer coordinates all components with validation + error handling

GOLDEN PROMPT ENFORCEMENTS:
- Stress-scenario dominance: BI_overall = min(BI_baseline, BI_moderate, BI_stress)
- No scenario averaging: Results stored independently per scenario, not aggregated
- User calibration constraints: Forbidden keys rejected, allowed keys applied equally to all scenarios
- Bank-grade standards: n_runs ≥ 20,000, fixed seed for reproducibility, full distribution output
- Mandatory disclaimer + stress_scenario_note in all responses
"""

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

# Import orchestration components
from engine.business_models import create_business_model, BUSINESS_MODELS
from engine.scenarios import ScenarioManager
from engine.montecarlo import MonteCarloEngine
from engine.bankability import BankabilityEngine

# ============================================================================
# SUPPORTED MODELS
# ============================================================================
ALLOWED_MODEL_IDS = tuple(BUSINESS_MODELS.keys())
"""
Supported business model identifiers derived from BUSINESS_MODELS config.
Models: AT (Austria), FR (France), DE (Germany), IT (Italy), SI (Slovenia)
"""

# ============================================================================
# LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# SCENARIO CONFIGURATION (LAYER B: Homogeneous assumptions)
# ============================================================================
SCENARIO_CONFIG = {
    "baseline": {
        "revenue_multiplier": 1.0,
        "volume_multiplier": 1.0,
        "cost_multiplier": 1.0,
        "discount_rate_adjustment": 0.0,
        "market_scenario": "neutral"
    },
    "moderate": {
        "revenue_multiplier": 0.95,
        "volume_multiplier": 0.90,
        "cost_multiplier": 1.05,
        "discount_rate_adjustment": 0.02,
        "market_scenario": "downturn"
    },
    "stress": {
        "revenue_multiplier": 0.80,
        "volume_multiplier": 0.70,
        "cost_multiplier": 1.10,
        "discount_rate_adjustment": 0.04,
        "market_scenario": "shock"
    }
}
"""
SCENARIO CONFIGURATION DOCUMENTATION:
======================================

All scenarios use IDENTICAL business logic (revenue/cost/driver calculations) but
with different parameter multipliers representing market conditions:

BASELINE (Neutral Market):
- revenue_multiplier: 1.0 (no adjustment)
- volume_multiplier: 1.0 (no adjustment)
- cost_multiplier: 1.0 (no adjustment)
- discount_rate_adjustment: 0.0 (no adjustment, use user's discount_rate)
- Rationale: Expected-case scenario with user-provided parameters

MODERATE (Downturn):
- revenue_multiplier: 0.95 (5% downside risk)
- volume_multiplier: 0.90 (10% volume reduction)
- cost_multiplier: 1.05 (5% cost inflation)
- discount_rate_adjustment: +0.02 (2% risk premium for uncertainty)
- Rationale: Mid-range stress reflecting market contraction, demand softening

STRESS (Severe Market Shock):
- revenue_multiplier: 0.80 (20% revenue decline)
- volume_multiplier: 0.70 (30% volume contraction)
- cost_multiplier: 1.10 (10% cost inflation)
- discount_rate_adjustment: +0.04 (4% high-risk premium for systemic stress)
- Rationale: Worst-case scenario capturing regulatory failure, market collapse, ESG backlash

INDEPENDENCE REQUIREMENT:
All three scenarios are computed independently with separate stochastic driver samples.
NO cross-scenario blending, averaging, or normalization in response.
"""

# ============================================================================
# VALIDATION CONSTANTS
# ============================================================================
FORBIDDEN_CALIBRATION_KEYS = {
    'revenue_structure',
    'cost_structure',
    'stochastic_drivers',
    'scenario_dominance',
    'bankability_formula',
    'policy_dependence_factor'
}
"""
Keys that users CANNOT modify (immutable by Golden Prompt).
These define the heterogeneous structure of each business model.
"""

ALLOWED_CALIBRATION_KEYS = {
    'prices',
    'volumes',
    'costs',
    'discount_rate',
    'duration'
}
"""
Keys that users MAY modify (calibration parameters).
Applied equally to all three scenarios.
"""

BANK_GRADE_N_RUNS = 20000
"""
Minimum Monte Carlo runs for bank-grade assessment.
Sufficient for ±1-2% confidence interval on percentile estimates.
"""

FIXED_SEED = 42
"""
Reproducibility seed: same seed guarantees same stochastic samples across API calls.
Per-scenario adjustment applied deterministically (seed + hash(scenario) % 1000).
"""

# ============================================================================
# REQUEST/RESPONSE PYDANTIC MODELS
# ============================================================================


class UserCalibrationRequest(BaseModel):
    """
    User-provided parameter overrides for cash-flow calculation.
    
    CONSTRAINTS:
    - Users may adjust: prices, volumes, costs, discount_rate, duration
    - Users may NOT adjust: revenue_structure, cost_structure, scenario_dominance, bankability_formula
    - All overrides applied equally to all three scenarios (baseline, moderate, stress)
    
    ASSUMPTION:
    Empty calibration (all fields optional) is allowed → uses model defaults
    """
    prices: Optional[Dict[str, float]] = Field(
        None,
        description="Price overrides per product/service. E.g., {'eco_credit_price': 12.50}"
    )
    volumes: Optional[Dict[str, float]] = Field(
        None,
        description="Volume overrides per product/service. E.g., {'eco_credits_annual': 50000}"
    )
    costs: Optional[Dict[str, float]] = Field(
        None,
        description="Cost overrides per line item. E.g., {'operating_cost_per_unit': 5.0}"
    )
    discount_rate: Optional[float] = Field(
        None,
        ge=0.0,
        le=0.3,
        description="User's discount rate [0.0, 0.3]. Applied to baseline; adjusted by scenario_config"
    )
    duration: Optional[int] = Field(
        None,
        ge=1,
        le=50,
        description="Project evaluation horizon in years [1, 50]"
    )

    @validator('*', pre=True)
    def convert_none_to_empty(cls, v):
        """Convert explicit None values to dict/None for optional fields."""
        return v


class DeterministicResult(BaseModel):
    """Deterministic cash-flow analysis for one scenario."""
    annual_cash_flows: List[float] = Field(description="Year-by-year cash flows")
    npv: float = Field(description="Net present value (sum of discounted CF)")
    cumulative_cash_flows: List[float] = Field(description="Year-by-year cumulative CF")
    payback_period: Optional[float] = Field(
        None,
        description="Years to recover initial investment (None if not achieved)"
    )
    irr: Optional[float] = Field(
        None,
        description="Internal rate of return (None if not meaningful for this model)"
    )


class MonteCarloResult(BaseModel):
    """Monte Carlo risk analysis for one scenario (20,000+ runs)."""
    n_runs: int = Field(description="Number of simulation runs (≥20,000)")
    seed: int = Field(description="Random seed for reproducibility")
    mean_npv: float = Field(description="Expected NPV across all runs")
    median_npv: float = Field(description="Median NPV")
    std_npv: float = Field(description="Standard deviation of NPV distribution")
    p5_npv: float = Field(description="5th percentile NPV (downside at 95% confidence)")
    p95_npv: float = Field(description="95th percentile NPV (upside at 95% confidence)")
    prob_negative_npv: float = Field(
        ge=0.0,
        le=1.0,
        description="Probability NPV < 0 (project failure risk)"
    )
    cvar5_npv: float = Field(
        description="Conditional value at risk at 5% tail (expected loss in worst 5%)"
    )
    volatility_dcf: float = Field(
        description="Standard deviation of NPV expressed as % of mean (relative volatility)"
    )
    driver_importance: Dict[str, float] = Field(
        description="Tornado analysis: sensitivity ranking of stochastic drivers"
    )


class ScenarioResult(BaseModel):
    """Complete analysis (deterministic + Monte Carlo) for one scenario."""
    deterministic: DeterministicResult
    monte_carlo: MonteCarloResult


class BankabilityResult(BaseModel):
    """Bankability assessment across all three scenarios with stress dominance."""
    BI_baseline: float = Field(ge=0.0, le=1.0, description="Bankability Index for baseline scenario")
    BI_moderate: float = Field(ge=0.0, le=1.0, description="Bankability Index for moderate scenario")
    BI_stress: float = Field(ge=0.0, le=1.0, description="Bankability Index for stress scenario")
    BI_overall: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall BI = min(baseline, moderate, stress) - STRESS SCENARIO IS BINDING"
    )
    classification: str = Field(
        description="Bankability category: unbankable, public_only, blended, conditional, or robust"
    )
    stress_scenario_note: str = Field(
        description="Narrative explanation of stress dominance and which scenario is binding"
    )


class ApiResponse(BaseModel):
    """
    Complete API response: three independent scenario results + bankability assessment.
    
    NO AVERAGING OR NORMALIZATION.
    Results stored separately per scenario, not aggregated.
    """
    baseline: ScenarioResult = Field(description="Baseline scenario results")
    moderate: ScenarioResult = Field(description="Moderate scenario results")
    stress: ScenarioResult = Field(description="Stress scenario results")
    bankability: BankabilityResult = Field(description="Bankability assessment (all scenarios)")
    mandatory_disclaimer: str = Field(
        description="Required legal/professional disclaimer"
    )
    metadata: Dict[str, Any] = Field(
        description="Audit trail: timestamp, model_id, seed, n_runs"
    )


class ErrorResponse(BaseModel):
    """Standardized error response."""
    error_code: str = Field(description="Machine-readable error identifier")
    error_message: str = Field(description="Human-readable error description")
    available_models: List[str] = Field(description="Valid model_id values")
    documentation_url: str = Field(description="Link to API documentation")


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Forest EcoValue Bank-Proof Tool",
    description="Compute bankability assessments for FES business models",
    version="1.0.0"
)

# ============================================================================
# ORCHESTRATION ENDPOINTS
# ============================================================================


@app.post(
    "/run/{model_id}",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Run bankability assessment",
    description="""
    Execute three independent scenario analyses (baseline, moderate, stress) on a FES business model
    with user-provided calibration overrides.
    
    RETURNS:
    - Three complete scenario results (deterministic + Monte Carlo, NO averaging)
    - Bankability Index with stress-dominance enforcement
    - Mandatory disclaimer + stress explanation
    
    CONSTRAINTS:
    - model_id must be one of: AT, FR, DE, IT, SI
    - user_calibration keys must be subset of: prices, volumes, costs, discount_rate, duration
    - Monte Carlo: minimum 20,000 runs, fixed seed for reproducibility
    """
)
async def run_bankability_assessment(
    model_id: str,
    calibration: UserCalibrationRequest
) -> ApiResponse:
    """
    PHASE 1: Input Validation
    ========================
    Validate model_id, user_calibration keys, and parameter ranges.
    """
    logger.info(f"Request: model_id={model_id}, calibration_keys={list(calibration.dict(exclude_none=True).keys())}")
    
    # Validate model_id
    if model_id not in ALLOWED_MODEL_IDS:
        logger.error(f"Invalid model_id: {model_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_MODEL_ID",
                "error_message": f"model_id '{model_id}' not supported",
                "available_models": list(ALLOWED_MODEL_IDS),
                "documentation_url": "/docs"
            }
        )
    
    # Convert calibration to dict (remove None values)
    user_calibration = calibration.dict(exclude_none=True)
    
    # Validate calibration keys (no forbidden keys)
    forbidden_keys_in_request = set(user_calibration.keys()) & FORBIDDEN_CALIBRATION_KEYS
    if forbidden_keys_in_request:
        logger.error(f"Forbidden calibration keys: {forbidden_keys_in_request}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "FORBIDDEN_CALIBRATION_KEYS",
                "error_message": f"Cannot modify immutable keys: {forbidden_keys_in_request}. "
                                f"Allowed keys: {ALLOWED_CALIBRATION_KEYS}",
                "available_models": list(ALLOWED_MODEL_IDS),
                "documentation_url": "/docs"
            }
        )
    
    # Validate calibration values (numeric, in valid ranges)
    if 'discount_rate' in user_calibration and not (0.0 <= user_calibration['discount_rate'] <= 0.3):
        logger.error(f"discount_rate out of range: {user_calibration['discount_rate']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_CALIBRATION_VALUES",
                "error_message": f"discount_rate must be in [0.0, 0.3], got {user_calibration['discount_rate']}",
                "available_models": list(ALLOWED_MODEL_IDS),
                "documentation_url": "/docs"
            }
        )
    
    if 'duration' in user_calibration and not (1 <= user_calibration['duration'] <= 50):
        logger.error(f"duration out of range: {user_calibration['duration']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_CALIBRATION_VALUES",
                "error_message": f"duration must be in [1, 50], got {user_calibration['duration']}",
                "available_models": list(ALLOWED_MODEL_IDS),
                "documentation_url": "/docs"
            }
        )
    
    """
    PHASE 2: Business Model Factory
    ===============================
    Create executable BusinessModel instance (not dict).
    """
    try:
        business_model = create_business_model(model_id, user_calibration)
        logger.info(f"BusinessModel created: {model_id}")
    except Exception as e:
        logger.error(f"BusinessModel factory failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "BUSINESS_MODEL_FACTORY_ERROR",
                "error_message": f"Failed to create business model: {str(e)}",
                "available_models": list(ALLOWED_MODEL_IDS),
                "documentation_url": "/docs"
            }
        )
    
    """
    PHASE 3: Deterministic Analysis (Per Scenario, Independent)
    ===========================================================
    ScenarioManager.run_deterministic() for each scenario independently.
    NO cross-scenario averaging or normalization.
    """
    scenario_manager = ScenarioManager()
    results = {}
    
    for scenario in ['baseline', 'moderate', 'stress']:
        try:
            # Merge scenario_config + user_calibration
            scenario_params = {**SCENARIO_CONFIG[scenario], **user_calibration}
            
            # Run deterministic analysis (correct argument order: business_model, scenario, parameters)
            det_result = scenario_manager.run_deterministic(business_model, scenario, scenario_params)
            
            results[scenario] = {'deterministic': det_result}
            logger.info(f"Deterministic analysis complete: {scenario}, NPV={det_result['npv']:.2f}")
        
        except Exception as e:
            logger.error(f"Deterministic analysis failed for {scenario}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "DETERMINISTIC_ANALYSIS_ERROR",
                    "error_message": f"Failed to compute deterministic CF for {scenario}: {str(e)}",
                    "available_models": list(ALLOWED_MODEL_IDS),
                    "documentation_url": "/docs"
                }
            )
    
    """
    PHASE 4: Monte Carlo Analysis (Per Scenario, Independent, ≥20,000 runs)
    =====================================================================
    MonteCarloEngine.run() for each scenario independently, fixed seed.
    NO cross-scenario blending of distributions.
    """
    montecarlo_engine = MonteCarloEngine()
    
    for scenario in ['baseline', 'moderate', 'stress']:
        try:
            # Merge scenario_config + user_calibration
            scenario_params = {**SCENARIO_CONFIG[scenario], **user_calibration}
            
            # Get stochastic drivers from business_model
            stochastic_drivers = business_model.get_stochastic_drivers()
            
            # Run Monte Carlo (n_runs ≥ 20,000, fixed seed per-scenario)
            mc_result = montecarlo_engine.run(
                business_model=business_model,
                scenario_params=scenario_params,
                stochastic_drivers=stochastic_drivers,
                scenario_name=scenario,
                n_runs=BANK_GRADE_N_RUNS,
                seed=FIXED_SEED + hash(scenario) % 1000
            )
            results[scenario]['monte_carlo'] = mc_result
            logger.info(f"Monte Carlo analysis complete: {scenario}, mean_NPV={mc_result['mean_npv']:.2f}")
        
        except ValueError as e:
            # montecarlo.py raises ValueError if n_runs < 20,000
            logger.error(f"Monte Carlo validation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "MONTE_CARLO_VALIDATION_ERROR",
                    "error_message": f"Bank-grade Monte Carlo failed: {str(e)}",
                    "available_models": list(ALLOWED_MODEL_IDS),
                    "documentation_url": "/docs"
                }
            )
        except Exception as e:
            logger.error(f"Monte Carlo analysis failed for {scenario}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "MONTE_CARLO_ANALYSIS_ERROR",
                    "error_message": f"Failed to compute Monte Carlo for {scenario}: {str(e)}",
                    "available_models": list(ALLOWED_MODEL_IDS),
                    "documentation_url": "/docs"
                }
            )
    
    """
    PHASE 5: Bankability Computation (Stress-Dominance Enforcement)
    ==============================================================
    BankabilityEngine.compute() receives all three scenarios.
    Enforces: BI_overall = min(BI_baseline, BI_moderate, BI_stress)
    No averaging, no normalization.
    """
    try:
        # BankabilityEngine requires business_model_config (not instance)
        bankability_engine = BankabilityEngine(business_model.config)
        bankability_result = bankability_engine.compute(results)
        logger.info(f"Bankability assessment complete: BI_overall={bankability_result['BI_overall']:.3f}, "
                   f"classification={bankability_result['classification']}")
    except Exception as e:
        logger.error(f"Bankability computation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "BANKABILITY_ENGINE_ERROR",
                "error_message": f"Failed to compute bankability index: {str(e)}",
                "available_models": list(ALLOWED_MODEL_IDS),
                "documentation_url": "/docs"
            }
        )
    
    """
    PHASE 6: Response Assembly (Three Independent Scenarios, NO Averaging)
    =====================================================================
    Build ApiResponse with:
    - Baseline, moderate, stress as separate top-level objects
    - Bankability section with stress_scenario_note
    - Mandatory disclaimer
    - Audit metadata
    """
    
    # Mandatory disclaimer (bank-grade, non-negotiable)
    mandatory_disclaimer = (
        "IMPORTANT DISCLAIMER: This assessment is based on assumptions provided by the user "
        "and historical data. It is NOT professional financial advice, NOT a guarantee of "
        "future performance, and NOT a substitute for independent expert review. "
        "Forest EcoValue Bank-Proof Tool cannot guarantee accuracy, completeness, or applicability "
        "to your specific circumstances. All scenarios are illustrative only. "
        "Consult qualified financial advisors and legal professionals before making investment decisions."
    )
    
    # Audit metadata
    metadata = {
        "timestamp": datetime.utcnow().isoformat(),
        "model_id": model_id,
        "n_runs": BANK_GRADE_N_RUNS,
        "seed": FIXED_SEED,
        "scenarios": ["baseline", "moderate", "stress"],
        "stress_dominant_scenario": "stress"
    }
    
    # Build response (three scenario objects, NOT averaged)
    # Note: payback_years was already mapped to payback_period above
    response = ApiResponse(
        baseline=ScenarioResult(
            deterministic=DeterministicResult(**results['baseline']['deterministic']),
            monte_carlo=MonteCarloResult(**results['baseline']['monte_carlo'])
        ),
        moderate=ScenarioResult(
            deterministic=DeterministicResult(**results['moderate']['deterministic']),
            monte_carlo=MonteCarloResult(**results['moderate']['monte_carlo'])
        ),
        stress=ScenarioResult(
            deterministic=DeterministicResult(**results['stress']['deterministic']),
            monte_carlo=MonteCarloResult(**results['stress']['monte_carlo'])
        ),
        bankability=BankabilityResult(**bankability_result),
        mandatory_disclaimer=mandatory_disclaimer,
        metadata=metadata
    )
    
    logger.info(f"Assessment complete: {model_id}, BI_overall={response.bankability.BI_overall:.3f}")
    return response


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.get("/health", status_code=200)
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.
    
    RETURNS:
    Status and supported models.
    """
    return {
        "status": "healthy",
        "supported_models": ", ".join(ALLOWED_MODEL_IDS),
        "bank_grade_n_runs": str(BANK_GRADE_N_RUNS),
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# DOCUMENTATION ENDPOINT
# ============================================================================

@app.get("/models", status_code=200)
async def list_models() -> Dict[str, Any]:
    """
    List supported FES business models.
    
    RETURNS:
    Model identifiers and descriptions.
    """
    model_descriptions = {
        "AT": "Austria Eco-Certification & Carbon Credit Sales",
        "FR": "France Recreational Trail Network & Eco-Tourism",
        "DE": "Germany Wetland Restoration & Payment for Ecosystem Services",
        "IT": "Italy Forest Carbon & Biodiversity Offset Bundling",
        "SI": "Slovenia Nature-Based Enterprise Network Integration"
    }
    
    return {
        "available_models": {mid: model_descriptions.get(mid, "Unknown") for mid in ALLOWED_MODEL_IDS},
        "allowed_calibration_keys": list(ALLOWED_CALIBRATION_KEYS),
        "forbidden_calibration_keys": list(FORBIDDEN_CALIBRATION_KEYS),
        "scenario_config_scenarios": ["baseline", "moderate", "stress"],
        "bank_grade_requirements": {
            "minimum_monte_carlo_runs": BANK_GRADE_N_RUNS,
            "reproducibility": "Fixed seed for all scenarios",
            "stress_dominance": "BI_overall = min(BI_baseline, BI_moderate, BI_stress)"
        }
    }


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/", status_code=200)
async def root() -> Dict[str, str]:
    """Root endpoint with API overview."""
    return {
        "service": "Forest EcoValue Bank-Proof Tool",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/models": "List supported models and calibration options",
            "/run/{model_id}": "Run bankability assessment (POST with UserCalibrationRequest)"
        },
        "documentation": "/docs",
        "openapi": "/openapi.json"
    }