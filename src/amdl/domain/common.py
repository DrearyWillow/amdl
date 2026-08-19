from typing import Self

from pydantic import BaseModel, model_validator


class DomainModel(BaseModel):
    library_id: str | None = None
    catalog_id: str | None = None

    @model_validator(mode="after")
    def has_id(self) -> Self:
        if self.library_id is None and self.catalog_id is None:
            raise ValueError("A library or catalog ID is required")
        return self

    @property
    def id(self) -> str:
        if self.catalog_id is not None:
            return self.catalog_id
        if self.library_id is not None:
            return self.library_id

        raise AssertionError("DomainModel invariant violated")
