from pydantic import BaseModel, Field


class ProductCsvImportResult(BaseModel):
    dry_run: bool
    row_count: int
    created: int | None = None
    updated: int | None = None
    errors: list[str] = Field(default_factory=list)
