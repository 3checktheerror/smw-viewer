from pydantic import BaseModel, Field
from typing import List

class BadTokenSchema(BaseModel):
    address: str = Field(..., description="Token address")
    chain: str = Field(..., description="Chain name")

class BadTokenAddRequest(BaseModel):
    tokens: List[BadTokenSchema] = Field(..., description="List of bad tokens to add")

class BadTokenDeleteRequest(BaseModel):
    tokens: List[BadTokenSchema] = Field(..., description="List of bad tokens to delete")

class BadTokenInfo(BaseModel):
    address: str = Field(..., description="Token address")
    chain: str = Field(..., description="Chain name")
    store_time: int = Field(..., description="Timestamp when the token was added")
