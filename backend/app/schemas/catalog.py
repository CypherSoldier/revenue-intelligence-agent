from pydantic import BaseModel


class ColumnDefinition(BaseModel):
    name: str
    data_type: str
    description: str


class TableDefinition(BaseModel):
    name: str
    description: str
    grain: str
    columns: list[ColumnDefinition]


class MetricDefinition(BaseModel):
    id: str
    name: str
    expression: str
    unit: str
    description: str
    time_column: str
    supported_dimensions: list[str]


class DataCatalog(BaseModel):
    dataset_name: str
    currency: str
    coverage_start: str
    coverage_end: str
    reporting_calendar: str
    tables: list[TableDefinition]
    metrics: list[MetricDefinition]
