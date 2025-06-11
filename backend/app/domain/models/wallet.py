from pydantic import BaseModel
from typing import Optional


class WalletModel(BaseModel):
    chain: str
    address: str
    group_id: Optional[int] = None
    priority: Optional[int] = None
    stored_date: Optional[str] = None