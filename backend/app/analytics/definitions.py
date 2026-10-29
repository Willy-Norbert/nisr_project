"""Indicator catalogue: the single place where every published Analiza indicator is defined."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Indicator:
    id: str
    name: str
    unit: str
    topic: str
    source: str
    description: str
    higher_is_better: bool = True
    crop_specific: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


SAS = "NISR Seasonal Agricultural Survey 2024-2025"
AHS = "NISR Agriculture Household Survey 2024"

INDICATORS: dict[str, Indicator] = {
    i.id: i
    for i in [
        Indicator(
            "yield_kg_ha", "Crop yield", "kg/ha", "production", SAS,
            "Weighted ratio of total harvest (kg) to total planted crop area (ha). Plots under 5 m2 and the top 1% of "
            "yields per crop are excluded.",
            crop_specific=True,
        ),
        Indicator(
            "production_t", "Estimated production", "tonnes", "production", SAS,
            "Survey-weighted total harvest for the season, in tonnes.",
            crop_specific=True,
        ),
        Indicator(
            "improved_seed_pct", "Improved seed use", "% of plots", "inputs", SAS,
            "Share of crop plots sown with improved seed (weighted by plot weight).",
        ),
        Indicator(
            "inorganic_fertilizer_pct", "Inorganic fertilizer use", "% of plots", "inputs", SAS,
            "Share of plots where inorganic (mineral) fertilizer was applied this season.",
        ),
        Indicator(
            "organic_fertilizer_pct", "Organic fertilizer use", "% of plots", "inputs", SAS,
            "Share of plots where organic fertilizer (manure, compost) was applied this season.",
        ),
        Indicator(
            "irrigation_pct", "Irrigation", "% of plots", "practices", SAS,
            "Share of plots irrigated during the season.",
        ),
        Indicator(
            "anti_erosion_pct", "Anti-erosion measures", "% of plots", "practices", SAS,
            "Share of plots with anti-erosion activities (terraces, ditches, hedges).",
        ),
        Indicator(
            "land_consolidation_pct", "Land consolidation", "% of plots", "practices", SAS,
            "Share of plots located in a land consolidation site.",
        ),
        Indicator(
            "extension_access_pct", "Extension service access", "% of households", "support", AHS,
            "Share of agricultural households where a member received extension or advisory services this season.",
        ),
        Indicator(
            "cooperative_member_pct", "Cooperative membership", "% of households", "support", AHS,
            "Share of households with a member in an agricultural cooperative or association.",
        ),
        Indicator(
            "crop_insurance_pct", "Crop insurance", "% of households", "support", AHS,
            "Share of households where a member took crop insurance this season.",
        ),
        Indicator(
            "agri_support_pct", "Agricultural support received", "% of households", "support", AHS,
            "Share of households that received a grant, fund or other support for agriculture.",
        ),
        Indicator(
            "fertilizer_risk_aware_pct", "Fertilizer risk awareness", "% of households", "sustainability", AHS,
            "Share of households aware of environmental risks from excessive fertilizer use.",
        ),
    ]
}

SAS_RATE_COLUMNS = {
    "improved_seed_pct": "improved_seed",
    "inorganic_fertilizer_pct": "inorganic_fertilizer",
    "organic_fertilizer_pct": "organic_fertilizer",
    "irrigation_pct": "irrigated",
    "anti_erosion_pct": "anti_erosion",
    "land_consolidation_pct": "land_consolidation",
}

AHS_RATE_COLUMNS = {
    "extension_access_pct": "extension_access",
    "cooperative_member_pct": "cooperative_member",
    "crop_insurance_pct": "crop_insurance",
    "agri_support_pct": "agri_support_received",
    "fertilizer_risk_aware_pct": "fertilizer_risk_aware",
}

# Inputs a farmer or programme can change; used for input-effect comparisons and the scenario model.
INPUT_COLUMNS = {
    "improved_seed": "Improved seed",
    "inorganic_fertilizer": "Inorganic fertilizer",
    "organic_fertilizer": "Organic fertilizer",
    "irrigated": "Irrigation",
}

MIN_CELL_N = 10  # cells with fewer observations are suppressed
LOW_RELIABILITY_N = 30
