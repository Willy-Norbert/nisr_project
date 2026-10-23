"""Catalogue of the NISR source files used by FarmGap.

The Stata (.dta) version of each file is used as the source of truth because it
carries variable labels; the CSV exports are tab-separated and unlabeled.
"""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

SAS_MODULES = {
    "production": "Rwa_raw_Season{season}{year}_Production.dta",
    "screening": "Rwa_raw_Season{season}{year}_Screening.dta",
    "practices": "Rwa_raw_Season{season}{year}_Agricultural_practice.dta",
    "fertilizer": "Rwa_raw_fertilizer_pesticide{season}{year}.dta",
}

SAS_FOLDERS = {
    2024: "sas_2024",
    2025: "sas_2025",
}

AHS_FOLDER = "ahs_2024"

AHS_SECTIONS = {
    "section0": ("AHS2024_Section0.dta", "Household identification and livelihood"),
    "members": ("AHS2024_Section1_HOUSEHOLD MEMBERS CHARACTERISTICS.dta", "Household members characteristics"),
    "land_tenure": ("AHS2024_Section2_LAND TENURE.dta", "Land tenure"),
    "crops_inputs": (
        "AHS2024_Section3_4_CROP GROWN, SEEDS AND PRODUCTION & AGRICULTURAL INPUTS AND PRACTICES.dta",
        "Crops grown, seeds, production, inputs and practices",
    ),
    "fruits": ("AHS2024_Section5_FRUITS PRODUCTION.dta", "Fruits production"),
    "extension": ("AHS2024_Section6_EXTENSION SERVICES AND AGRICULTURAL PROGRAMMES.dta", "Extension services and programmes"),
    "tools": ("AHS2024_Section7_AGRICULTURAL TOOLS.dta", "Agricultural tools"),
    "sustainable": ("AHS2024_Section8_SUSTAINABLE AGRICULTURE.dta", "Sustainable agriculture"),
    "livestock": ("AHS2024_Section9_10_12_LIVESTOCK AND ANIMAL INPUTS EXPENDITURES,.dta", "Livestock and animal input expenditures"),
    "milk": ("AHS2024_Section11_1_CATTLE MILK PRODUCTION AND USE.dta", "Cattle milk production and use"),
    "eggs": ("AHS2024_Section11_2_EGG PRODUCTION.dta", "Egg production"),
    "honey": ("AHS2024_Section11_3_HONEY PRODUCTION.dta", "Honey production"),
    "credits": ("AHS2024_Credits.dta", "Agricultural credit"),
    "savings": ("AHS2024_Saving.dta", "Savings"),
}


@dataclass(frozen=True)
class DatasetInfo:
    id: str
    survey: str
    year: int
    season: str | None
    module: str
    description: str
    relative_path: str

    @property
    def path(self) -> Path:
        return get_settings().raw_data_dir / self.relative_path


def _build_registry() -> dict[str, DatasetInfo]:
    registry: dict[str, DatasetInfo] = {}
    for year, folder in SAS_FOLDERS.items():
        for season in ("A", "B", "C"):
            for module, pattern in SAS_MODULES.items():
                ds = DatasetInfo(
                    id=f"sas{year}_{season.lower()}_{module}",
                    survey="Seasonal Agricultural Survey",
                    year=year,
                    season=season,
                    module=module,
                    description=f"SAS {year} Season {season} - {module.replace('_', ' ')}",
                    relative_path=f"{folder}/Season {season}/{pattern.format(season=season, year=year)}",
                )
                registry[ds.id] = ds
    for module, (filename, description) in AHS_SECTIONS.items():
        ds = DatasetInfo(
            id=f"ahs2024_{module}",
            survey="Agriculture Household Survey",
            year=2024,
            season=None,
            module=module,
            description=description,
            relative_path=f"{AHS_FOLDER}/{filename}",
        )
        registry[ds.id] = ds
    return registry


DATASETS: dict[str, DatasetInfo] = _build_registry()


def get_dataset(dataset_id: str) -> DatasetInfo:
    try:
        return DATASETS[dataset_id]
    except KeyError:
        raise KeyError(f"Unknown dataset '{dataset_id}'") from None
