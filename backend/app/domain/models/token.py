from pydantic import BaseModel


class TokenModel(BaseModel):
    chain: str
    address: str
    is_honeypot: bool
    is_low_liquidity: bool
    is_old: bool