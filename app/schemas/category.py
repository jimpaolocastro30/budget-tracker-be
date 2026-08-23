from uuid import UUID

from pydantic import Field

from app.db.enums import CategoryType
from app.schemas.common import ORMModel


class CategoryCreate(ORMModel):
    name: str = Field(..., min_length=1, max_length=255)
    category_type: CategoryType
    parent_id: UUID | None = None


class CategoryUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: UUID | None = None
    is_active: bool | None = None


class CategoryResponse(ORMModel):
    id: UUID
    user_id: UUID | None
    name: str
    category_type: CategoryType
    parent_id: UUID | None
    is_system: bool
    is_active: bool
