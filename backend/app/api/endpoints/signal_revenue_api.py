import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
from fastapi import APIRouter
from backend.app.api.schemas.common_schemas import CommonResult
from backend.app.api.schemas.signal_revenue_schemas import SignalRevenueRequest
from backend.app.services.asynctask.async_task_service import AsyncProgressService, NoSignalsFoundError
from backend.app.utils.task_stage_utils import TaskStageUtils
from backend.app.api.schemas.task_schemas import TaskCreateResponse

router = APIRouter()


@router.post("/revenue/daily_signal", response_model=CommonResult, summary="计算信号策略收益（异步）")
async def create_signal_revenue_task(request: SignalRevenueRequest):
    """创建后台任务计算信号策略收益，并返回 task_id"""
    try:
        task_id = await AsyncProgressService.create_signal_revenue_task(request)
        return CommonResult().success(data=TaskCreateResponse(task_id=task_id))
    except NoSignalsFoundError as e:
        logging.info(f"No signals found for the request, task not created. Reason: {e}")
        return CommonResult().fail(code=404, description="没有找到符合筛选条件的信号数据")
    except Exception as e:
        logging.error(f"Failed to create async signal revenue task: {e}", exc_info=True)
        return CommonResult().fail(code=500, description=f"创建任务失败: {e}")


@router.get("/revenue/daily_signal_progress/{task_id}", response_model=CommonResult, summary="查询信号策略计算进度")
async def get_signal_revenue_task_progress(task_id: str):
    try:
        progress = await TaskStageUtils.get_progress(task_id)
        if progress:
            return CommonResult().success(data=progress)
        else:
            logging.warning(f"Progress for task_id '{task_id}' not found or has expired.")
            return CommonResult().fail(code=404, description="任务不存在或已过期")
    except Exception as e:
        logging.error(f"Failed to fetch task progress for task_id '{task_id}': {e}", exc_info=True)
        return CommonResult().fail(code=500, description="查询任务进度时发生错误")


@router.get("/revenue/daily_signal_result/{task_id}", response_model=CommonResult, summary="获取信号策略计算结果")
async def get_signal_revenue_result(task_id: str, part: int = 0):
    """
    获取信号策略计算结果。

    说明：
    1. 当 ``part == -1`` 时，仅返回 meta 信息（与旧实现保持一致）。
    2. 当 ``part >= 0`` 时，不再只返回单个分片，而是：
       - 使用 10 线程线程池并发读取 *所有* 分片；
       - 将所有 ``token_results`` 拼接成一个完整列表；
       - 与 meta 信息合并后返回。

    这样可以显著缩短大量分片的读取耗时。
    """
    try:
        # 1. 仅获取 meta 信息
        if part == -1:
            meta_data = await TaskStageUtils.get_result_meta(task_id)
            if meta_data is not None:
                return CommonResult().success(data=meta_data)
            return CommonResult().fail(code=404, description="结果元数据不存在或已过期")

        # 2. 读取所有分片并与 meta 信息拼接
        meta_data = await TaskStageUtils.get_result_meta(task_id)
        if meta_data is None:
            logging.warning(f"Result meta for task_id '{task_id}' not found.")
            return CommonResult().fail(code=404, description="结果不存在或任务尚未完成")

        import asyncio
        from backend.app.utils.thread_pool import ThreadPoolManager

        loop = asyncio.get_running_loop()

        def _fetch_all_parts_blocking() -> list:
            """阻塞函数：使用 ThreadPoolManager 并发拉取所有分片并返回拼接后的列表。"""

            def _fetch_part(idx: int):
                import asyncio as _asyncio
                return _asyncio.run(TaskStageUtils.get_result_part(task_id, idx))

            aggregated_results = []
            part_idx = 0
            with ThreadPoolManager(max_workers=10) as manager:
                while True:
                    batch_indexes = list(range(part_idx, part_idx + 10))
                    futures = [manager.submit_task(_fetch_part, i) for i in batch_indexes]
                    
                    has_data_in_batch = False
                    for fut in futures:
                        part_data = fut.result()
                        if part_data:
                            aggregated_results.extend(part_data)
                            has_data_in_batch = True
                    
                    if not has_data_in_batch:
                        # 如果整个批次都没有数据，说明已经读完
                        break
                    
                    part_idx += 10
            return aggregated_results

        token_results: list = await loop.run_in_executor(None, _fetch_all_parts_blocking)

        meta_data["token_results"] = token_results
        return CommonResult().success(data=meta_data)

    except Exception as e:
        logging.error(f"Failed to fetch task result for task_id '{task_id}': {e}", exc_info=True)
        return CommonResult().fail(code=500, description="获取任务结果时发生错误")