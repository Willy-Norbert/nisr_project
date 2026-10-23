from pydantic import BaseModel


class DatasetSummary(BaseModel):
    id: str
    survey: str
    year: int
    season: str | None
    module: str
    description: str
    available: bool


class VariableInfo(BaseModel):
    name: str
    label: str | None


class DatasetDetail(DatasetSummary):
    rows: int
    columns: int
    variables: list[VariableInfo]
