from typing import List, Optional
from pydantic import BaseModel, Field

class SMWHistoryModel(BaseModel):
    address: Optional[str] = Field(default=None, description="历史钱包地址")
    chain: Optional[str] = Field(default=None, description="链")
    pnl: Optional[float] = Field(default=0.0, description="钱包7D PNL")
    winrate: Optional[float] = Field(default=0.0, description="钱包7D 赢率")
    token_winrate: Optional[float] = Field(default=0.0, description="钱包7D 代币赢率")
    store_date: Optional[str] = Field(default=None, description="存储日期(北京时间XXXX_XX_XX)")
    out_tag: Optional[int] = Field(default=0, description="标签状态(1: 默认 (添加进白名单后变成4)，2: 低数据，3: 交易行为差，4: 白名单 (移除后变成1))")

class SMWIncrementalModel(BaseModel):
    address: Optional[str] = Field(default=None, description="每日增量钱包地址")
    chain: Optional[str] = Field(default=None, description="链")
    store_date: Optional[str] = Field(default=None, description="存储日期(北京时间XXXX_XX_XX)")
    pnl: Optional[float] = Field(default=None, description="钱包7D PNL")
    winrate: Optional[float] = Field(default=None, description="钱包7D 赢率")
    token_winrate: Optional[float] = Field(default=None, description="钱包7D 代币赢率")


class WalletOperation(BaseModel):
    address: Optional[str] = Field(default=None, description="钱包地址")
    chain: Optional[str] = Field(default=None, description="链")
    op: Optional[int] = Field(default=None, description="操作(1: thumb_up, 2: thumb_down, 3: other)")

class WalletAddress(BaseModel):
    address: str = Field(..., description="钱包地址")
    chain: str = Field(..., description="链")