from pydantic import BaseModel
from typing import Optional


class WalletModel(BaseModel):
    chain: str
    address: str
    stored_date: Optional[str] = None