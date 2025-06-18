import logging
from fastapi import APIRouter
from backend.app.api.schemas.common_schemas import CommonResult
from backend.app.api.schemas.signal_revenue_schemas import SignalRevenueRequest
from backend.app.services.revenue.signal_pl_calculator import SignalRevenueCalculator

router = APIRouter()


@router.post("/revenue/daily_signal", response_model=CommonResult, summary="计算信号策略收益")
async def get_signal_revenue(request: SignalRevenueRequest):
    """
    根据指定的参数计算信号策略的收益.
    """
    try:
        result = SignalRevenueCalculator.calculate_signal_revenue(
            initial_usd=request.initial_usd,
            duration=request.duration,
            tp_rules=request.tp_rules,
            sl_rules=request.sl_rules,
            start_ts=request.start_ts,
            end_ts=request.end_ts,
            whitelist_tokens=request.whitelist_tokens,
            blacklist_tokens=request.blacklist_tokens
        )
        if result:
            return CommonResult().success(data=result)
        else:
            logging.warning("calculate_signal_revenue returned None")
            return CommonResult().fail(description="No data available for the given parameters.")
    except Exception as e:
        logging.error(f"Error calculating signal revenue: {e}", exc_info=True)
        return CommonResult().fail(code=500, description=str(e))