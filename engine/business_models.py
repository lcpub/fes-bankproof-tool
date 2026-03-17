"""
engine/business_models.py – Business Model Configurations & Execution (LAYER A)

ARCHITECTURE:
- Configuration dicts (AT_AUSTRIA_CONFIG, etc.) remain PURE (no logic)
- Executable BusinessModel classes wrap configs (generic algorithm applies structure)
- Factory function creates instances from model_id
- No business logic, only mechanical application of config structure

LAYER A (heterogeneous):
- Five business models with unique revenue/cost/driver structures
- Each model computes annual cash flows per scenario independently
- No scenario averaging or blending within BM calculation

KEY PRINCIPLES:
1. Configuration is immutable specification
2. Cash flow calculation is data-driven (applies config structure, no business logic)
3. Each scenario processed independently (no cross-scenario math in BM)
4. All numerical values (prices, volumes, costs) supplied by user at runtime
5. No hard-coded economics; only structural templates
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


# ============================================================================
# CONFIGURATION DICTS (PURE, NO LOGIC)
# ============================================================================

# AT – AUSTRIA: REVERSE AUCTION FOR BIODIVERSITY & CARBON
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
            'deterministic_baseline': None,
            'stochastic_driver': 'biodiversity_payment_volatility'
        },
        {
            'name': 'carbon_credit_revenue',
            'description': 'Revenue from verified carbon sequestration',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'carbon_price_volatility'
        },
        {
            'name': 'premium_payment',
            'description': 'Additional premium for certified biodiversity-friendly practices',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'policy_revision_risk'
        }
    ],
    
    'costs': [
        {
            'name': 'sustainable_forestry_management',
            'description': 'Costs for FSC/PEFC certification and compliance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'monitoring_verification',
            'description': 'Third-party audit and carbon verification',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'administration_overhead',
            'description': 'Auction participation, contract management',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.65,
    
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
    },
    
    'default_parameters': {
        'baseline': {
            'biodiversity_payment_baseline': 200,
            'carbon_credit_revenue_baseline': 80,
            'premium_payment_baseline': 60,
            'sustainable_forestry_management_baseline': 150,
            'monitoring_verification_baseline': 50,
            'administration_overhead_baseline': 40,
            'discount_rate': 0.05,
            'duration_years': 20
        },
        'moderate': {
            'biodiversity_payment_baseline': 180,
            'carbon_credit_revenue_baseline': 72,
            'premium_payment_baseline': 54,
            'sustainable_forestry_management_baseline': 158,
            'monitoring_verification_baseline': 53,
            'administration_overhead_baseline': 42,
            'discount_rate': 0.07,
            'duration_years': 20
        },
        'stress': {
            'biodiversity_payment_baseline': 140,
            'carbon_credit_revenue_baseline': 56,
            'premium_payment_baseline': 42,
            'sustainable_forestry_management_baseline': 173,
            'monitoring_verification_baseline': 58,
            'administration_overhead_baseline': 46,
            'discount_rate': 0.09,
            'duration_years': 20
        }
    }
}


# FR – FRANCE: RECREATIONAL FOREST & WATER SERVICES
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
            'deterministic_baseline': None,
            'stochastic_driver': 'visitor_volume_volatility'
        },
        {
            'name': 'water_service_payment',
            'description': 'Payment from water utilities for ecosystem service (purification, regulation)',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'water_demand_volatility'
        },
        {
            'name': 'carbon_sequestration_revenue',
            'description': 'Carbon credit sales from forest growth',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'carbon_price_volatility'
        },
        {
            'name': 'premium_eco_label',
            'description': 'Premium pricing for certified sustainable recreation/water',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'ecolabel_market_volatility'
        }
    ],
    
    'costs': [
        {
            'name': 'sustainable_forestry_management',
            'description': 'Silviculture, tending, biodiversity compliance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'trail_maintenance',
            'description': 'Walking paths, signage, safety inspections',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'water_monitoring',
            'description': 'Water quality testing, regulatory reporting',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'labour_staffing',
            'description': 'Rangers, guides, administrative staff',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'certification_marketing',
            'description': 'FSC certification, ecolabel maintenance, marketing',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.45,
    
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
    },
    
    'default_parameters': {
        'baseline': {
            'tourism_recreation_fee_baseline': 300,
            'water_service_payment_baseline': 150,
            'carbon_sequestration_revenue_baseline': 100,
            'premium_eco_label_baseline': 80,
            'sustainable_forestry_management_baseline': 200,
            'trail_maintenance_baseline': 100,
            'water_monitoring_baseline': 80,
            'labour_staffing_baseline': 150,
            'certification_marketing_baseline': 60,
            'discount_rate': 0.05,
            'duration_years': 20
        },
        'moderate': {
            'tourism_recreation_fee_baseline': 270,
            'water_service_payment_baseline': 135,
            'carbon_sequestration_revenue_baseline': 90,
            'premium_eco_label_baseline': 72,
            'sustainable_forestry_management_baseline': 210,
            'trail_maintenance_baseline': 105,
            'water_monitoring_baseline': 84,
            'labour_staffing_baseline': 158,
            'certification_marketing_baseline': 63,
            'discount_rate': 0.07,
            'duration_years': 20
        },
        'stress': {
            'tourism_recreation_fee_baseline': 210,
            'water_service_payment_baseline': 105,
            'carbon_sequestration_revenue_baseline': 70,
            'premium_eco_label_baseline': 56,
            'sustainable_forestry_management_baseline': 230,
            'trail_maintenance_baseline': 115,
            'water_monitoring_baseline': 92,
            'labour_staffing_baseline': 173,
            'certification_marketing_baseline': 69,
            'discount_rate': 0.09,
            'duration_years': 20
        }
    }
}


# DE – GERMANY: FOREST CEMETERY – CULTURAL ECOSYSTEM SERVICES
DE_GERMANY_CONFIG = {
    'id': 'DE',
    'name': 'Germany – Forest Cemetery: Cultural Ecosystem Services',
    'region': 'Germany',
    'duration_years': 50,
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
            'deterministic_baseline': None,
            'stochastic_driver': 'plot_demand_volatility'
        },
        {
            'name': 'perpetual_maintenance_fee',
            'description': 'Annual maintenance fee per active plot (in perpetuity)',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'maintenance_fee_volatility'
        },
        {
            'name': 'cultural_visitor_revenue',
            'description': 'Visitor fees, ceremonies, guided services',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'visitor_demand_volatility'
        },
        {
            'name': 'ecosystem_service_recognition',
            'description': 'Premium for cultural heritage and biodiversity certification',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'cultural_premium_volatility'
        }
    ],
    
    'costs': [
        {
            'name': 'forest_maintenance_tending',
            'description': 'Silviculture, ecosystem management',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'burial_site_care',
            'description': 'Grave maintenance, memorials, landscaping',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'regulatory_compliance',
            'description': 'Cemetery oversight, health/safety, heritage compliance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'administrative_staffing',
            'description': 'Groundskeepers, office staff, ceremonies coordination',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.50,
    
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
    },
    
    'default_parameters': {
        'baseline': {
            'burial_plot_sales_baseline': 500,
            'perpetual_maintenance_fee_baseline': 200,
            'cultural_visitor_revenue_baseline': 100,
            'ecosystem_service_recognition_baseline': 50,
            'forest_maintenance_tending_baseline': 150,
            'burial_site_care_baseline': 200,
            'regulatory_compliance_baseline': 80,
            'administrative_staffing_baseline': 120,
            'discount_rate': 0.05,
            'duration_years': 50
        },
        'moderate': {
            'burial_plot_sales_baseline': 450,
            'perpetual_maintenance_fee_baseline': 180,
            'cultural_visitor_revenue_baseline': 90,
            'ecosystem_service_recognition_baseline': 45,
            'forest_maintenance_tending_baseline': 158,
            'burial_site_care_baseline': 210,
            'regulatory_compliance_baseline': 84,
            'administrative_staffing_baseline': 126,
            'discount_rate': 0.07,
            'duration_years': 50
        },
        'stress': {
            'burial_plot_sales_baseline': 350,
            'perpetual_maintenance_fee_baseline': 140,
            'cultural_visitor_revenue_baseline': 70,
            'ecosystem_service_recognition_baseline': 35,
            'forest_maintenance_tending_baseline': 173,
            'burial_site_care_baseline': 230,
            'regulatory_compliance_baseline': 92,
            'administrative_staffing_baseline': 138,
            'discount_rate': 0.09,
            'duration_years': 50
        }
    }
}


# IT – ITALY: CIRCULAR BIO-ECONOMY
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
            'deterministic_baseline': None,
            'stochastic_driver': 'timber_price_volatility'
        },
        {
            'name': 'biomass_pellet_sales',
            'description': 'Biomass energy pellets for heating/power',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'biomass_price_volatility'
        },
        {
            'name': 'sawdust_byproduct',
            'description': 'Sawdust, wood chips, bark as secondary revenue',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'sawdust_price_volatility'
        },
        {
            'name': 'carbon_credit_revenue',
            'description': 'Carbon sequestration credits',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'carbon_price_volatility'
        },
        {
            'name': 'agritourism_recreation',
            'description': 'Farm stays, forest tours, educational activities',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'tourism_volatility'
        }
    ],
    
    'costs': [
        {
            'name': 'harvesting_logging',
            'description': 'Felling, extraction, road maintenance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'processing_chipping',
            'description': 'Sawmill, chipping, drying, pelletizing equipment/operation',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'transport_logistics',
            'description': 'Transport of timber, biomass, byproducts to market',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'labour_operations',
            'description': 'Harvesters, equipment operators, administrative staff',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'equipment_maintenance',
            'description': 'Machinery, vehicles, tool maintenance and depreciation',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'forest_regeneration',
            'description': 'Replanting, regeneration, biodiversity management',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.55,
    
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
    },
    
    'default_parameters': {
        'baseline': {
            'timber_sales_baseline': 600,
            'biomass_pellet_sales_baseline': 400,
            'sawdust_byproduct_baseline': 200,
            'carbon_credit_revenue_baseline': 100,
            'agritourism_recreation_baseline': 150,
            'harvesting_logging_baseline': 300,
            'processing_chipping_baseline': 250,
            'transport_logistics_baseline': 150,
            'labour_operations_baseline': 200,
            'equipment_maintenance_baseline': 100,
            'forest_regeneration_baseline': 100,
            'discount_rate': 0.05,
            'duration_years': 20
        },
        'moderate': {
            'timber_sales_baseline': 540,
            'biomass_pellet_sales_baseline': 360,
            'sawdust_byproduct_baseline': 180,
            'carbon_credit_revenue_baseline': 90,
            'agritourism_recreation_baseline': 135,
            'harvesting_logging_baseline': 315,
            'processing_chipping_baseline': 263,
            'transport_logistics_baseline': 158,
            'labour_operations_baseline': 210,
            'equipment_maintenance_baseline': 105,
            'forest_regeneration_baseline': 105,
            'discount_rate': 0.07,
            'duration_years': 20
        },
        'stress': {
            'timber_sales_baseline': 420,
            'biomass_pellet_sales_baseline': 280,
            'sawdust_byproduct_baseline': 140,
            'carbon_credit_revenue_baseline': 70,
            'agritourism_recreation_baseline': 105,
            'harvesting_logging_baseline': 345,
            'processing_chipping_baseline': 288,
            'transport_logistics_baseline': 173,
            'labour_operations_baseline': 230,
            'equipment_maintenance_baseline': 115,
            'forest_regeneration_baseline': 115,
            'discount_rate': 0.09,
            'duration_years': 20
        }
    }
}


# SI – SLOVENIA: TORRENT PROTECTION & RISK-REDUCTION FUND
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
            'deterministic_baseline': None,
            'stochastic_driver': 'fund_allocation_volatility'
        },
        {
            'name': 'insurance_contribution',
            'description': 'Payment from catastrophe insurance pool for risk reduction',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'insurance_pool_volatility'
        },
        {
            'name': 'ecosystem_service_contract',
            'description': 'Contract payments for water regulation, biodiversity',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'stochastic_driver': 'contract_renewal_volatility'
        }
    ],
    
    'costs': [
        {
            'name': 'forest_restoration',
            'description': 'Afforestation, erosion control, stabilization works',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'maintenance_monitoring',
            'description': 'Annual maintenance, hazard monitoring, annual inspection',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'engineering_works',
            'description': 'Specialized torrent protection works, check dams, drainage',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        },
        {
            'name': 'administration_coordination',
            'description': 'Fund administration, landowner coordination, compliance',
            'unit': 'EUR/hectare/year',
            'deterministic_baseline': None,
            'efficiency_factor': 1.0
        }
    ],
    
    'policy_dependence': 0.70,
    
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
    },
    
    'default_parameters': {
        'baseline': {
            'risk_reduction_payment_baseline': 300,
            'insurance_contribution_baseline': 150,
            'ecosystem_service_contract_baseline': 100,
            'forest_restoration_baseline': 200,
            'maintenance_monitoring_baseline': 150,
            'engineering_works_baseline': 180,
            'administration_coordination_baseline': 80,
            'discount_rate': 0.05,
            'duration_years': 25
        },
        'moderate': {
            'risk_reduction_payment_baseline': 270,
            'insurance_contribution_baseline': 135,
            'ecosystem_service_contract_baseline': 90,
            'forest_restoration_baseline': 210,
            'maintenance_monitoring_baseline': 158,
            'engineering_works_baseline': 189,
            'administration_coordination_baseline': 84,
            'discount_rate': 0.07,
            'duration_years': 25
        },
        'stress': {
            'risk_reduction_payment_baseline': 210,
            'insurance_contribution_baseline': 105,
            'ecosystem_service_contract_baseline': 70,
            'forest_restoration_baseline': 230,
            'maintenance_monitoring_baseline': 173,
            'engineering_works_baseline': 207,
            'administration_coordination_baseline': 92,
            'discount_rate': 0.09,
            'duration_years': 25
        }
    }
}


# Business model registry
BUSINESS_MODELS = {
    'AT': AT_AUSTRIA_CONFIG,
    'FR': FR_FRANCE_CONFIG,
    'DE': DE_GERMANY_CONFIG,
    'IT': IT_ITALY_CONFIG,
    'SI': SI_SLOVENIA_CONFIG
}


# ============================================================================
# ABSTRACT BASE CLASS & CONCRETE IMPLEMENTATIONS (EXECUTABLE LAYER)
# ============================================================================

class BusinessModel(ABC):
    """
    Abstract base class for all Forest EcoValue business models.
    
    Each business model computes annual cash flows deterministically,
    independent of other scenarios. No business logic; only mechanical
    application of config structure to user-supplied parameters.
    
    ASSUMPTION: All five business models share identical cash flow calculation logic:
    1. Sum revenues: baseline_i × driver_multiplier_i
    2. Sum costs: baseline_j × efficiency_factor_j
    3. Annual CF = total_revenue − total_costs
    4. Return np.ndarray of annual CFs for duration years
    
    This ensures no hidden assumptions and enables audit trail.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize business model from configuration.
        
        Args:
            config: Configuration dict (e.g., AT_AUSTRIA_CONFIG)
                   Must contain: id, name, region, duration_years, revenues, costs,
                                 policy_dependence, stochastic_drivers
        
        Raises:
            KeyError: If required config keys missing
        """
        required_keys = {'id', 'name', 'duration_years', 'revenues', 'costs', 
                        'policy_dependence', 'stochastic_drivers'}
        missing = required_keys - set(config.keys())
        if missing:
            raise KeyError(f"Config missing required keys: {missing}")
        
        self.config = config
        self.id = config['id']
        self.name = config['name']
        self.duration_years = config['duration_years']
    
    def calculate_annual_cash_flows(self, params: Dict[str, Any]) -> np.ndarray:
        """
        Calculate deterministic annual cash flows for ONE scenario.
        
        CRITICAL: Each scenario is processed INDEPENDENTLY.
        No cross-scenario averaging or blending.
        
        ALGORITHM (homogeneous across all five BMs):
        1. Initialize revenues dict {revenue_name: value}
        2. For each revenue in config['revenues']:
           - Get baseline from params (user-supplied, mandatory)
           - Get driver multiplier from params (from MC sampling)
           - Result: revenue = baseline × multiplier
        3. Sum all revenues
        4. For each cost in config['costs']:
           - Get baseline from params (user-supplied, mandatory)
           - Get efficiency_factor from params (user-supplied, default 1.0)
           - Result: cost = baseline × efficiency_factor
        5. Sum all costs
        6. Annual CF = revenue - cost (one value per year, same for all years)
        7. Return np.array([CF, CF, ..., CF]) repeated for duration_years
        
        ASSUMPTIONS:
        - Params dict is scenario-specific (not mixture of scenarios)
        - All baseline values for revenues in params (no fallback/defaults)
        - All baseline values for costs in params (no fallback/defaults)
        - Discount rate comes from params (not applied here; NPV is LAYER B)
        - Duration is deterministic (from config, can be overridden in params)
        
        Args:
            params: Dict with scenario-specific parameters.
                   Required keys (example for Austria):
                   - 'biodiversity_payment': float (EUR/hectare/year)
                   - 'biodiversity_payment_volatility_multiplier': float ∈ [0.70, 1.30]
                   - 'carbon_credit_revenue': float
                   - 'carbon_price_volatility_multiplier': float ∈ [0.50, 1.80]
                   - 'premium_payment': float
                   - 'policy_revision_risk_multiplier': float ∈ [0.80, 1.0]
                   - [Similarly for costs]
                   - Optional: 'duration_years' (overrides config default)
        
        Returns:
            np.ndarray of shape (duration,), annual cash flows (can be negative)
        
        Raises:
            KeyError: If required param missing
            TypeError: If param types invalid
            ValueError: If duration invalid
        """
        # Get duration (user override or config default)
        duration = params.get('duration_years', self.duration_years)
        if not isinstance(duration, int) or duration <= 0:
            raise ValueError(f"duration_years must be positive int. Got: {duration}")
        
        # ===== REVENUE CALCULATION =====
        
        total_revenue = 0.0
        revenue_breakdown = {}
        
        for revenue_spec in self.config['revenues']:
            revenue_name = revenue_spec['name']
            driver_name = revenue_spec['stochastic_driver']
            
            # Get baseline value (user-supplied, mandatory)
            baseline_key = f'{revenue_name}_baseline'
            if baseline_key not in params:
                raise KeyError(
                    f"Param '{baseline_key}' missing for revenue '{revenue_name}'. "
                    f"Business model {self.id}: {self.name}"
                )
            baseline = params[baseline_key]
            if not isinstance(baseline, (int, float)):
                raise TypeError(
                    f"Revenue baseline '{baseline_key}' must be numeric. "
                    f"Got: {type(baseline).__name__}"
                )
            
            # Get stochastic multiplier (from MC sampling)
            multiplier_key = f'{driver_name}_multiplier'
            multiplier = params.get(multiplier_key, 1.0)
            if not isinstance(multiplier, (int, float)):
                raise TypeError(
                    f"Driver multiplier '{multiplier_key}' must be numeric. "
                    f"Got: {type(multiplier).__name__}"
                )
            
            # Compute revenue = baseline × multiplier
            revenue_value = baseline * multiplier
            revenue_breakdown[revenue_name] = float(revenue_value)
            total_revenue += revenue_value
        
        # ===== COST CALCULATION =====
        
        total_cost = 0.0
        cost_breakdown = {}
        
        for cost_spec in self.config['costs']:
            cost_name = cost_spec['name']
            
            # Get baseline value (user-supplied, mandatory)
            baseline_key = f'{cost_name}_baseline'
            if baseline_key not in params:
                raise KeyError(
                    f"Param '{baseline_key}' missing for cost '{cost_name}'. "
                    f"Business model {self.id}: {self.name}"
                )
            baseline = params[baseline_key]
            if not isinstance(baseline, (int, float)):
                raise TypeError(
                    f"Cost baseline '{baseline_key}' must be numeric. "
                    f"Got: {type(baseline).__name__}"
                )
            
            # Get efficiency factor (user-supplied; default 1.0)
            efficiency_key = f'{cost_name}_efficiency_factor'
            efficiency_factor = params.get(efficiency_key, 1.0)
            if not isinstance(efficiency_factor, (int, float)):
                raise TypeError(
                    f"Efficiency factor '{efficiency_key}' must be numeric. "
                    f"Got: {type(efficiency_factor).__name__}"
                )
            
            # Sanity check: efficiency factor in reasonable range
            if efficiency_factor < 0.2 or efficiency_factor > 5.0:
                raise ValueError(
                    f"Efficiency factor '{efficiency_key}' = {efficiency_factor} "
                    f"is outside [0.2, 5.0] sanity bounds. Check calibration."
                )
            
            # Compute cost = baseline × efficiency_factor
            cost_value = baseline * efficiency_factor
            cost_breakdown[cost_name] = float(cost_value)
            total_cost += cost_value
        
        # ===== ANNUAL CASH FLOW =====
        # Assumption: Same annual CF for all years (constant stream)
        # This is deterministic calculation; variability comes from stochastic drivers in MC
        
        annual_cf = total_revenue - total_cost
        
        # Return array repeated for duration years
        cf_array = np.full(duration, annual_cf, dtype=np.float64)
        
        return cf_array
    
    def get_stochastic_drivers(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve stochastic driver specifications for this business model.
        
        ASSUMPTION: Drivers are defined in config and never modified.
        This method is a simple accessor.
        
        Returns:
            Dict mapping driver_name → driver_spec
            Example:
            {
                'carbon_price_volatility': {
                    'type': 'triangular',
                    'min_multiplier': 0.50,
                    'mode_multiplier': 1.0,
                    'max_multiplier': 1.80
                },
                ...
            }
        """
        return self.config['stochastic_drivers']
    
    def get_policy_dependence(self) -> float:
        """
        Retrieve policy dependence factor for this business model.
        
        ASSUMPTION: Policy dependence is homogeneous (same for all scenarios).
        This reflects structural business model risk, not scenario variability.
        
        Returns:
            float ∈ [0, 1] – degree of policy dependence
        """
        return self.config['policy_dependence']


# ============================================================================
# CONCRETE BUSINESS MODEL IMPLEMENTATIONS
# ============================================================================

class AustriaReverseAuction(BusinessModel):
    """
    Austria: Reverse Auction for Biodiversity & Carbon
    
    Driven by auction payments + carbon credits + policy-dependent premium.
    Uses inherited calculate_annual_cash_flows() from base class.
    """
    pass


class FranceRecreational(BusinessModel):
    """
    France: Recreational Forest & Water Services
    
    Multi-service model: tourism + water utilities + carbon + ecolabel.
    Uses inherited calculate_annual_cash_flows() from base class.
    """
    pass


class GermanyCemetery(BusinessModel):
    """
    Germany: Forest Cemetery – Cultural Ecosystem Services
    
    Long-horizon model (50 years) combining burial services + perpetual care
    + cultural/heritage value. Uses inherited calculate_annual_cash_flows().
    """
    pass


class ItalyBioeconomy(BusinessModel):
    """
    Italy: Circular Bio-Economy (Biomass, Sawdust, Carbon, Tourism)
    
    Integrated model: timber + biomass + byproducts + carbon + agritourism.
    Uses inherited calculate_annual_cash_flows() from base class.
    """
    pass


class SloveniaRiskreduction(BusinessModel):
    """
    Slovenia: Torrent Protection & Risk-Reduction Fund
    
    Ecosystem service model: compensation for disaster risk mitigation
    via restoration + maintenance + monitoring. Uses inherited
    calculate_annual_cash_flows() from base class.
    """
    pass


# ============================================================================
# FACTORY FUNCTION & ACCESSORS
# ============================================================================

def create_business_model(
    model_id: str,
    user_calibration: Optional[Dict[str, Any]] = None
) -> BusinessModel:
    """
    Factory function: Create a BusinessModel instance from model_id.
    
    ARCHITECTURE: Converts config dict → executable object
    
    Args:
        model_id: str – one of 'AT', 'FR', 'DE', 'IT', 'SI'
        user_calibration: Optional dict with user overrides.
                         Allowed keys: prices, volumes, costs, discount_rate, duration
                         Forbidden keys: revenue_structure, cost_structure, 
                                        stochastic_drivers, policy_dependence
    
    Returns:
        BusinessModel instance (subclass specific to model_id)
    
    Raises:
        ValueError: If model_id unknown or user_calibration contains forbidden keys
    """
    if model_id not in BUSINESS_MODELS:
        available = list(BUSINESS_MODELS.keys())
        raise ValueError(
            f"Unknown business model: {model_id}. Available: {available}"
        )
    
    # Validate user calibration (if provided)
    if user_calibration:
        forbidden_keys = {
            'revenue_structure', 'cost_structure', 'stochastic_drivers',
            'policy_dependence', 'bankability_formula', 'scenario_dominance'
        }
        if forbidden_keys.intersection(user_calibration.keys()):
            overlap = forbidden_keys.intersection(user_calibration.keys())
            raise ValueError(
                f"User calibration cannot modify: {overlap}. "
                f"These are immutable per Golden Prompt."
            )
    
    # Get config
    config = BUSINESS_MODELS[model_id]
    
    # Instantiate correct subclass
    subclass_map = {
        'AT': AustriaReverseAuction,
        'FR': FranceRecreational,
        'DE': GermanyCemetery,
        'IT': ItalyBioeconomy,
        'SI': SloveniaRiskreduction
    }
    
    subclass = subclass_map[model_id]
    return subclass(config)


def get_business_model_config(model_id: str) -> Dict[str, Any]:
    """
    Retrieve a business model configuration dict by ID.
    
    PURE DATA accessor; no logic.
    
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