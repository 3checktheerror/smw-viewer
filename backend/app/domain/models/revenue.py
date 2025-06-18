from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class RevenueInfoModel(BaseModel):
    token: str
    kline: List[Dict[str, Any]]
    signal_time: int
    signal_price: Optional[float] = None
    trigger_event: Optional[List[int]] = None


class RevenueModel(BaseModel):
    date: int = Field(..., description="The timestamp for the date (00:00:00 UTC).")
    info: List[RevenueInfoModel]
