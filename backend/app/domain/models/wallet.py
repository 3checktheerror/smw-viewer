from pydantic import BaseModel


class WalletModel(BaseModel):
    chain: str
    address: str
    group: str
    priority: int