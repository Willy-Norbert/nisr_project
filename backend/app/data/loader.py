import logging
from functools import lru_cache

import pandas as pd
import pyreadstat

from app.data.registry import DatasetInfo, get_dataset

logger = logging.getLogger(__name__)


def _read_dta(dataset: DatasetInfo, **kwargs):
    # Some AHS files store value labels in Latin-1 rather than UTF-8.
    try:
        return pyreadstat.read_dta(str(dataset.path), **kwargs)
    except UnicodeDecodeError:
        return pyreadstat.read_dta(str(dataset.path), encoding="latin1", **kwargs)


def read_metadata(dataset: DatasetInfo) -> pyreadstat.metadata_container:
    _, meta = _read_dta(dataset, metadataonly=True)
    return meta


def load_dataset(dataset_id: str, columns: list[str] | None = None) -> pd.DataFrame:
    """Load a dataset with Stata value labels applied (codes become readable text)."""
    dataset = get_dataset(dataset_id)
    logger.info("Loading %s from %s", dataset_id, dataset.path)
    df, _ = _read_dta(dataset, usecols=columns, apply_value_formats=True, formats_as_category=False)
    return df


@lru_cache(maxsize=16)
def load_dataset_cached(dataset_id: str) -> pd.DataFrame:
    return load_dataset(dataset_id)
