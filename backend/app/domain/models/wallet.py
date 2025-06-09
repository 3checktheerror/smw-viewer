from pydantic import BaseModel


class WalletModel(BaseModel):
    chain: str
    address: str
    group_id: int
    priority: int