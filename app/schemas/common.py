from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | list | str | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class MessageResponse(BaseModel):
    message: str


class DecimalStr(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
        )

    @classmethod
    def validate(cls, value: str) -> str:
        from decimal import Decimal, InvalidOperation

        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("Invalid decimal value") from exc
        if amount <= 0:
            raise ValueError("Amount must be greater than zero")
        return f"{amount:.2f}"


class PositiveDecimal(BaseModel):
    amount: str = Field(..., pattern=r"^\d+(\.\d{1,2})?$")

    def to_decimal(self):
        from decimal import Decimal

        return Decimal(self.amount)
