from fastapi import APIRouter, BackgroundTasks
from typing import List, Dict
from backend.app.services.kol.kol_service import KOLService
from backend.app.api.schemas.common_schemas import CommonResult
from backend.app.api.schemas.kol_schemas import KOLResultModel

router = APIRouter(prefix="/kol", tags=["KOL"])


@router.get("/gmgn/daily_hot_tokens", response_model=CommonResult[Dict[str, List[str]]])
async def get_gmgn_daily_hot_tokens():
    """
    Get GmgN daily hot tokens.
    """
    tokens = KOLService.get_gmgn_daily_hot_tokens()
    return CommonResult().success(data=tokens)


@router.post("/kol_info", response_model=CommonResult)
async def upsert_kol_info(kols: List[KOLResultModel], background_tasks: BackgroundTasks):
    """
    Upsert KOL information and trigger background processing.
    """
    background_tasks.add_task(KOLService.process_kol_data, kols)
    return CommonResult().success(data="Task to process KOL data has been started in the background.")
