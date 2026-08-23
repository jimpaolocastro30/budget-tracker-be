from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.db.enums import TransactionType
from app.schemas.common import ORMModel


class TransactionCreate(ORMModel):
    account_id: UUID
    category_id: UUID | None = None
    transaction_type: TransactionType
    amount: str = Field(..., pattern=r"^\d+(\.\d{1,2})?$")
    currency: str = Field(..., min_length=3, max_length=3)
    transaction_date: date
    description: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    tags: str | None = Field(default=None, max_length=500)
    confirm_duplicate: bool = False


class TransactionUpdate(ORMModel):
    account_id: UUID | None = None
    category_id: UUID | None = None
    transaction_type: TransactionType | None = None
    amount: str | None = Field(default=None, pattern=r"^\d+(\.\d{1,2})?$")
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    transaction_date: date | None = None
    description: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    tags: str | None = Field(default=None, max_length=500)


class TransferCreate(ORMModel):
    source_account_id: UUID
    destination_account_id: UUID
    amount: str = Field(..., pattern=r"^\d+(\.\d{1,2})?$")
    currency: str = Field(..., min_length=3, max_length=3)
    transaction_date: date
    description: str | None = Field(default=None, max_length=500)
    notes: str | None = None


class DuplicateWarning(ORMModel):
    warning: bool = True
    message: str
    similar_transaction_ids: list[UUID]


class TransactionResponse(ORMModel):
    id: UUID
    account_id: UUID
    category_id: UUID | None
    transaction_type: TransactionType
    amount: str
    currency: str
    transaction_date: date
    description: str | None
    notes: str | None
    tags: str | None
    transfer_group_id: UUID | None
    created_at: datetime
    updated_at: datetime
