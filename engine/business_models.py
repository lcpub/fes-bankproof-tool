"""
engine/business_models.py – Business Model Configurations (LAYER A)

Five heterogeneous FES business models are defined PURELY as configuration objects.
No calculations. No logic. No Monte Carlo.

Each configuration specifies:
- Unique revenue structure
- Unique cost structure
- Unique stochastic drivers (by business model)
- Policy dependence factor

These configurations are inputs to the engine; they do NOT contain behavioral logic.

Living Labs:
AT – Austria (reverse auction for biodiversity & carbon)
FR – France (recreational forest & water services)
DE – Germany (forest cemetery – cultural ecosystem services)
IT – Italy (circular bio‑economy: biomass, sawdust, carbon, tourism)
SI – Slovenia (torrent protection & risk‑reduction fund)
"""


# ============================================================================
# AT – AUSTRIA: REVERSE AUCTION FOR BIODIVERSITY & CARBON
# ============================================================================

AT_AUSTRIA_CONFIG = {
    'id': 'AT',
    'name': 'Austria – Reverse Auction: Biodiversity & Carbon',
    'region': 'Austria',
    'duration_years': 20,
    'unit_of_analysis': 'year',
    'scale_unit': 'hectare',
    'description': (
        'Payment-for-ecosystem-services scheme based on competitive reverse auction. '
        'Landowners bid for biodiversity/carbon payments. Economic model reflects '
        'payment levels, land area, and policy-driven volatility.'
    ),
    
    'revenues': [
        {
            'name': 'biodiversity_payment',
            'description': 'Annual payment per hectare from auction mechanism',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'biodiversity_payment_volatility'
        },
        {
            'name': 'carbon_credit_revenue',
            'description': 'Revenue from verified carbon sequestration',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'carbon_price_volatility'
        },
        {
            'name': 'premium_payment',
            'description': 'Additional premium for certified biodiversity-friendly practices',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'policy_revision_risk'
        }
    ],
    
    'costs': [
        {
            'name': 'sustainable_forestry_management',
            'description': 'Costs for FSC/PEFC certification and compliance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0  # Adjustable by user
        },
        {
            'name': 'monitoring_verification',
            'description': 'Third-party audit and carbon verification',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'administration_overhead',
            'description': 'Auction participation, contract management',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.65,  # High sensitivity to EU environmental policy
    
    'stochastic_drivers': {
        'biodiversity_payment_volatility': {
            'type': 'triangular',
            'description': 'Auction clearing price fluctuation',
            'min_multiplier': 0.70,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.30
        },
        'carbon_price_volatility': {
            'type': 'triangular',
            'description': 'EU ETS carbon price fluctuation',
            'min_multiplier': 0.50,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.80
        },
        'policy_revision_risk': {
            'type': 'uniform',
            'description': 'Policy change affecting premium eligibility',
            'min_multiplier': 0.80,
            'max_multiplier': 1.0
        }
    }
}


# ============================================================================
# FR – FRANCE: RECREATIONAL FOREST & WATER SERVICES
# ============================================================================

FR_FRANCE_CONFIG = {
    'id': 'FR',
    'name': 'France – Recreational Forest & Water Services',
    'region': 'France',
    'duration_years': 20,
    'unit_of_analysis': 'year',
    'scale_unit': 'hectare',
    'description': (
        'Multi-service forest model combining recreation revenue (trails, wellness), '
        'water purification services (payment from water utilities), and carbon sequestration. '
        'Revenue drivers: visitor volume, premium pricing, water service contracts.'
    ),
    
    'revenues': [
        {
            'name': 'tourism_recreation_fee',
            'description': 'Visitor fees, wellness activities, guided tours',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'visitor_volume_volatility'
        },
        {
            'name': 'water_service_payment',
            'description': 'Payment from water utilities for ecosystem service (purification, regulation)',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'water_demand_volatility'
        },
        {
            'name': 'carbon_sequestration_revenue',
            'description': 'Carbon credit sales from forest growth',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'carbon_price_volatility'
        },
        {
            'name': 'premium_eco_label',
            'description': 'Premium pricing for certified sustainable recreation/water',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'ecolabel_market_volatility'
        }
    ],
    
    'costs': [
        {
            'name': 'sustainable_forestry_management',
            'description': 'Silviculture, tending, biodiversity compliance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'trail_maintenance',
            'description': 'Walking paths, signage, safety inspections',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'water_monitoring',
            'description': 'Water quality testing, regulatory reporting',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'labour_staffing',
            'description': 'Rangers, guides, administrative staff',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'certification_marketing',
            'description': 'FSC certification, ecolabel maintenance, marketing',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.45,  # Moderate; subject to water regulation and recreation policy
    
    'stochastic_drivers': {
        'visitor_volume_volatility': {
            'type': 'triangular',
            'description': 'Tourism demand and visitor count fluctuation',
            'min_multiplier': 0.60,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.40
        },
        'water_demand_volatility': {
            'type': 'triangular',
            'description': 'Water utility demand and service contract renewal',
            'min_multiplier': 0.80,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.20
        },
        'carbon_price_volatility': {
            'type': 'triangular',
            'description': 'International carbon market price fluctuation',
            'min_multiplier': 0.50,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.80
        },
        'ecolabel_market_volatility': {
            'type': 'uniform',
            'description': 'Market premium for certified sustainable products',
            'min_multiplier': 0.90,
            'max_multiplier': 1.15
        }
    }
}


# ============================================================================
# DE – GERMANY: FOREST CEMETERY – CULTURAL ECOSYSTEM SERVICES
# ============================================================================

DE_GERMANY_CONFIG = {
    'id': 'DE',
    'name': 'Germany – Forest Cemetery: Cultural Ecosystem Services',
    'region': 'Germany',
    'duration_years': 50,  # Perpetual cemetery; 50-year horizon
    'unit_of_analysis': 'year',
    'scale_unit': 'hectare',
    'description': (
        'Specialized forest-cemetery model combining burial services, perpetual-care revenues, '
        'and cultural/recreational value. Revenue drivers: burial plot sales, annual maintenance fees, '
        'visitor/pilgrimage payments. Long horizon reflects perpetual obligation.'
    ),
    
    'revenues': [
        {
            'name': 'burial_plot_sales',
            'description': 'One-time sale of burial plots (recognized annually over cohort)',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'plot_demand_volatility'
        },
        {
            'name': 'perpetual_maintenance_fee',
            'description': 'Annual maintenance fee per active plot (in perpetuity)',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'maintenance_fee_volatility'
        },
        {
            'name': 'cultural_visitor_revenue',
            'description': 'Visitor fees, ceremonies, guided services',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'visitor_demand_volatility'
        },
        {
            'name': 'ecosystem_service_recognition',
            'description': 'Premium for cultural heritage and biodiversity certification',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'cultural_premium_volatility'
        }
    ],
    
    'costs': [
        {
            'name': 'forest_maintenance_tending',
            'description': 'Silviculture, ecosystem management',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'burial_site_care',
            'description': 'Grave maintenance, memorials, landscaping',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'regulatory_compliance',
            'description': 'Cemetery oversight, health/safety, heritage compliance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'administrative_staffing',
            'description': 'Groundskeepers, office staff, ceremonies coordination',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.50,  # Moderate; cemetery regulations are stable but burial law varies
    
    'stochastic_drivers': {
        'plot_demand_volatility': {
            'type': 'triangular',
            'description': 'Burial demand and plot sales variability',
            'min_multiplier': 0.70,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.25
        },
        'maintenance_fee_volatility': {
            'type': 'uniform',
            'description': 'Annual maintenance fee adjustments',
            'min_multiplier': 0.95,
            'max_multiplier': 1.10
        },
        'visitor_demand_volatility': {
            'type': 'triangular',
            'description': 'Cultural/spiritual visitor demand',
            'min_multiplier': 0.60,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.35
        },
        'cultural_premium_volatility': {
            'type': 'uniform',
            'description': 'Market recognition of cultural heritage value',
            'min_multiplier': 0.85,
            'max_multiplier': 1.15
        }
    }
}


# ============================================================================
# IT – ITALY: CIRCULAR BIO‑ECONOMY (BIOMASS, SAWDUST, CARBON, TOURISM)
# ============================================================================

IT_ITALY_CONFIG = {
    'id': 'IT',
    'name': 'Italy – Circular Bio‑Economy: Biomass, Sawdust, Carbon, Tourism',
    'region': 'Italy',
    'duration_years': 20,
    'unit_of_analysis': 'year',
    'scale_unit': 'hectare',
    'description': (
        'Integrated circular-economy model: sustainable timber harvesting, biomass energy sales, '
        'sawdust byproduct valorization, carbon sequestration, and agritourism. '
        'Revenue streams: timber sales, biomass pellet sales, sawdust/chips, carbon, tourism. '
        'Cost drivers: harvesting, processing, transport, labor, equipment.'
    ),
    
    'revenues': [
        {
            'name': 'timber_sales',
            'description': 'Sustainable timber harvesting and sales',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'timber_price_volatility'
        },
        {
            'name': 'biomass_pellet_sales',
            'description': 'Biomass energy pellets for heating/power',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'biomass_price_volatility'
        },
        {
            'name': 'sawdust_byproduct',
            'description': 'Sawdust, wood chips, bark as secondary revenue',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'sawdust_price_volatility'
        },
        {
            'name': 'carbon_credit_revenue',
            'description': 'Carbon sequestration credits',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'carbon_price_volatility'
        },
        {
            'name': 'agritourism_recreation',
            'description': 'Farm stays, forest tours, educational activities',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'tourism_volatility'
        }
    ],
    
    'costs': [
        {
            'name': 'harvesting_logging',
            'description': 'Felling, extraction, road maintenance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'processing_chipping',
            'description': 'Sawmill, chipping, drying, pelletizing equipment/operation',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'transport_logistics',
            'description': 'Transport of timber, biomass, byproducts to market',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'labour_operations',
            'description': 'Harvesters, equipment operators, administrative staff',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'equipment_maintenance',
            'description': 'Machinery, vehicles, tool maintenance and depreciation',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'forest_regeneration',
            'description': 'Replanting, regeneration, biodiversity management',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.55,  # Moderate-high; subject to EU biomass policy and carbon pricing
    
    'stochastic_drivers': {
        'timber_price_volatility': {
            'type': 'triangular',
            'description': 'International timber market price',
            'min_multiplier': 0.65,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.45
        },
        'biomass_price_volatility': {
            'type': 'triangular',
            'description': 'Biomass energy price (linked to fossil fuel)',
            'min_multiplier': 0.55,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.60
        },
        'sawdust_price_volatility': {
            'type': 'uniform',
            'description': 'Secondary product market price',
            'min_multiplier': 0.75,
            'max_multiplier': 1.20
        },
        'carbon_price_volatility': {
            'type': 'triangular',
            'description': 'EU ETS and international carbon market',
            'min_multiplier': 0.50,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.80
        },
        'tourism_volatility': {
            'type': 'uniform',
            'description': 'Agritourism demand fluctuation',
            'min_multiplier': 0.70,
            'max_multiplier': 1.30
        }
    }
}


# ============================================================================
# SI – SLOVENIA: TORRENT PROTECTION & RISK‑REDUCTION FUND
# ============================================================================

SI_SLOVENIA_CONFIG = {
    'id': 'SI',
    'name': 'Slovenia – Torrent Protection & Risk‑Reduction Fund',
    'region': 'Slovenia',
    'duration_years': 25,
    'unit_of_analysis': 'year',
    'scale_unit': 'hectare',
    'description': (
        'Ecosystem service model: forest restoration and maintenance for torrent/debris-flow mitigation. '
        'Landowners are compensated through risk-reduction fund for maintaining protective forests. '
        'Revenue drivers: disaster-risk-reduction payments, insurance fund contributions, '
        'ecosystem service contracts. Cost drivers: restoration, monitoring, maintenance.'
    ),
    
    'revenues': [
        {
            'name': 'risk_reduction_payment',
            'description': 'Annual payment for torrent/erosion mitigation service',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'fund_allocation_volatility'
        },
        {
            'name': 'insurance_contribution',
            'description': 'Payment from catastrophe insurance pool for risk reduction',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'insurance_pool_volatility'
        },
        {
            'name': 'ecosystem_service_contract',
            'description': 'Contract payments for water regulation, biodiversity',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'stochastic_driver': 'contract_renewal_volatility'
        }
    ],
    
    'costs': [
        {
            'name': 'forest_restoration',
            'description': 'Afforestation, erosion control, stabilization works',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'maintenance_monitoring',
            'description': 'Annual maintenance, hazard monitoring, annual inspection',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'engineering_works',
            'description': 'Specialized torrent protection works, check dams, drainage',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        },
        {
            'name': 'administration_coordination',
            'description': 'Fund administration, landowner coordination, compliance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,  # User-supplied
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.70,  # High; depends on national disaster fund allocation and EU policy
    
    'stochastic_drivers': {
        'fund_allocation_volatility': {
            'type': 'triangular',
            'description': 'Year-to-year national fund allocation variance',
            'min_multiplier': 0.75,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.25
        },
        'insurance_pool_volatility': {
            'type': 'uniform',
            'description': 'Insurance pool contribution and claims payout variability',
            'min_multiplier': 0.80,
            'max_multiplier': 1.15
        },
        'contract_renewal_volatility': {
            'type': 'triangular',
            'description': 'Ecosystem service contract renewal probability and terms',
            'min_multiplier': 0.70,
            'mode_multiplier': 1.0,
            'max_multiplier': 1.20
        }
    }
}


# ============================================================================
# BUSINESS MODEL REGISTRY
# ============================================================================

BUSINESS_MODELS = {
    'AT': AT_AUSTRIA_CONFIG,
    'FR': FR_FRANCE_CONFIG,
    'DE': DE_GERMANY_CONFIG,
    'IT': IT_ITALY_CONFIG,
    'SI': SI_SLOVENIA_CONFIG
}


def get_business_model_config(model_id: str) -> dict:
    """
    Retrieve a business model configuration by ID.
    
    Args:
        model_id: str – one of 'AT', 'FR', 'DE', 'IT', 'SI'
    
    Returns:
        Configuration dict for the business model.
    
    Raises:
        ValueError: If model_id not found.
    """
    if model_id not in BUSINESS_MODELS:
        raise ValueError(
            f"Unknown business model: {model_id}. "
            f"Available: {list(BUSINESS_MODELS.keys())}"
        )
    return BUSINESS_MODELS[model_id]