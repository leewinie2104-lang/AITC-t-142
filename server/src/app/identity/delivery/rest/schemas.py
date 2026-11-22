from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=1, max_length=128)  # cap stops argon2 DoS with huge passwords


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class EligibilityOut(BaseModel):
    zone_id: UUID
    building_id: UUID | None
    asset_kind: str
    role: str
    valid_until: datetime | None
    active: bool


class MeOut(BaseModel):
    id: UUID
    full_name: str
    phone: str
    role: str
    staff_zone_id: UUID | None
    eligibilities: list[EligibilityOut]
