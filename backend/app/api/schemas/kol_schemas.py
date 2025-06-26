from typing import List, Optional
from pydantic import BaseModel, Field

class KOLResultModel(BaseModel):
    address: Optional[str] = Field(default=None, description="KOL钱包地址")
    chain: Optional[str] = Field(default=None, description="链")
    avatar: Optional[str] = Field(default=None, description="KOL头像")
    twitter_username: Optional[str] = Field(default=None, description="推特用户名")
    twitter_name: Optional[str] = Field(default=None, description="推特名")

