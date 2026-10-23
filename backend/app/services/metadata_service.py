from app.data.loader import read_metadata
from app.data.registry import DATASETS, DatasetInfo, get_dataset
from app.schemas.metadata import DatasetDetail, DatasetSummary, VariableInfo


def _summary(ds: DatasetInfo) -> DatasetSummary:
    return DatasetSummary(
        id=ds.id,
        survey=ds.survey,
        year=ds.year,
        season=ds.season,
        module=ds.module,
        description=ds.description,
        available=ds.path.exists(),
    )


def list_datasets() -> list[DatasetSummary]:
    return [_summary(ds) for ds in DATASETS.values()]


def get_dataset_detail(dataset_id: str) -> DatasetDetail:
    ds = get_dataset(dataset_id)
    meta = read_metadata(ds)
    return DatasetDetail(
        **_summary(ds).model_dump(),
        rows=meta.number_rows,
        columns=meta.number_columns,
        variables=[VariableInfo(name=n, label=l) for n, l in meta.column_names_to_labels.items()],
    )
