from typing import List, Dict, Optional

from pydantic import BaseModel, Field


class SignalRevenueRequest(BaseModel):
    initial_usd: float = Field(..., description="初始投资金额 (USD)")
    duration: int = Field(..., description="策略的有效时长（秒）")
    tp_rules: List[Dict[str, float]] = Field(..., description="止盈策略规则")
    sl_rules: List[Dict[str, float]] = Field(..., description="止损策略规则")
    start_ts: int = Field(default=0, description="开始时间戳")
    end_ts: int = Field(default=4116779249, description="结束时间戳")
    whitelist_tokens: Optional[List[str]] = Field(default=None, description="白名单代币列表")
    blacklist_tokens: Optional[List[str]] = Field(default=None, description="黑名单代币列表") 