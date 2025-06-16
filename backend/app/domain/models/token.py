from typing import Optional

from pydantic import BaseModel


class TokenModel(BaseModel):
    chain: str
    address: str
    is_honeypot: Optional[bool]
    is_old: Optional[bool]


class TokenRevenueModel(BaseModel):
    chain: str
    address: str
    first_signal_time: int