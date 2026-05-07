from pydantic import BaseModel, Field


class ProductCsvImportResult(BaseModel):
    dry_run: bool
    row_count: int
    created: int | None = None
    updated: int | None = None
    errors: list[str] = Field(default_factory=list)


class ProductCsvImportStart(BaseModel):
    job_id: str
    row_count: int
    created_estimate: int
    updated_estimate: int


class ProductCsvImportStatus(BaseModel):
    job_id: str
    status: str
    row_count: int
    processed: int
    created: int
    updated: int
    errors: list[str] = Field(default_factory=list)
