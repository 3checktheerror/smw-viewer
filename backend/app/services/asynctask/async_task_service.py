from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from backend.app.api.schemas.signal_revenue_schemas import SignalRevenueRequest
from backend.app.services.revenue.signal_pl_calculator import SignalRevenueCalculator
from backend.app.utils.task_stage_utils import TaskStageUtils


class AsyncProgressService:
    """Service that handles long-running tasks and reports progress via Redis."""

    _executor: Optional[ThreadPoolExecutor] = None

    @classmethod
    def _get_executor(cls) -> ThreadPoolExecutor:
        if cls._executor is None:
            # 默认线程池大小为 CPU 核心数 * 2, 如果以后有需要可以做成可配置
            cls._executor = ThreadPoolExecutor()
        return cls._executor

    # ----------------------------------------------------------------------
    # Signal-revenue specific implementation
    # ----------------------------------------------------------------------
    @classmethod
    async def create_signal_revenue_task(cls, request: SignalRevenueRequest) -> str:
        """Create background task for signal revenue calculation and return a task_id."""

        # 1. 创建任务并初始化进度
        task_id = await TaskStageUtils.create_task()
        logging.info(f"Created async signal revenue task: {task_id}")

        # 2. 将耗时计算放到线程池中执行
        executor = cls._get_executor()

        def _blocking_job():
            """同步函数，在线程池中执行。"""
            import asyncio as _asyncio  # 线程中再次 import 避免闭包带来的问题

            processed_cnt: int = 0
            total_cnt: int = 0  # 会在稍后确定

            # 本地辅助函数，用同步方式更新 Redis 进度
            def _update_progress_sync(progress: int, total: int, status: str, result=None):
                async def _inner():
                    await TaskStageUtils.update_progress(task_id, progress, total, status, result)
                try:
                    _asyncio.run(_inner())
                except Exception as e:
                    logging.error(f"Failed to update task progress in Redis: {e}")

            # --------------------------------------
            # progress 回调：拉取 KLine 时每完成 batch_size (50) 个 token 调用一次
            # --------------------------------------
            def _progress_callback(delta: int):
                nonlocal processed_cnt, total_cnt
                processed_cnt += delta
                _update_progress_sync(processed_cnt, total_cnt, "RUNNING")

            try:
                # --------------------------------------
                # 先通过 Calculator 的内部逻辑获取总信号数 (all_signals)
                # 为避免重复实现过滤逻辑，这里通过紧耦合方式调用内部私有 API:
                #   - 直接调用 calculate_signal_revenue 之前，预先执行其前置步骤
                #   - 因为相关方法并未对外暴露，只能复制轻量逻辑
                # 此处复制部分逻辑以统计总数 (仅访问 MongoDB，不会执行 K 线或收益计算)
                # --------------------------------------
                try:
                    from datetime import datetime
                    from backend.app.utils.mongo_client import MongoDBClient

                    original_start_ts, original_end_ts = request.start_ts, request.end_ts
                    start_ts = original_start_ts + 86400
                    end_ts = original_end_ts + 86400

                    mongo_client = MongoDBClient()
                    start_date_str = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d')
                    end_date_str = datetime.fromtimestamp(end_ts).strftime('%Y-%m-%d')

                    query: dict =  {"store_time": {"$gte": start_date_str, "$lte": end_date_str}}
                    if request.whitelist_tokens:
                        query["token"] = {"$in": request.whitelist_tokens}
                    elif request.blacklist_tokens:
                        query["token"] = {"$nin": request.blacklist_tokens}
                    projection = {"first_signal_time": 1}

                    raw_signals = mongo_client.find_many("debot_signal", query, projection=projection, db_name="graph")
                    # 根据 first_signal_time 再做一次过滤
                    filtered_signals = [s for s in raw_signals if original_start_ts <= s.get('first_signal_time', 0) <= original_end_ts]
                    total_cnt = len(filtered_signals)
                except Exception as estimate_err:
                    logging.warning(f"Failed to estimate total signals, fallback to unknown total: {estimate_err}")
                    total_cnt = 0

                # 更新一次总数信息
                _update_progress_sync(0, total_cnt, "RUNNING")

                # --------------------------------------
                # 正式计算收益（阻塞）
                # --------------------------------------
                result_dict = SignalRevenueCalculator.calculate_signal_revenue(
                    initial_usd=request.initial_usd,
                    duration=request.duration,
                    tp_rules=request.tp_rules,
                    sl_rules=request.sl_rules,
                    start_ts=request.start_ts,
                    end_ts=request.end_ts,
                    whitelist_tokens=request.whitelist_tokens,
                    blacklist_tokens=request.blacklist_tokens,
                    progress_callback=_progress_callback
                )

                # 保存大结果到 redis 分片
                from backend.app.utils.task_stage_utils import TaskStageUtils as _tsu
                _asyncio.run(_tsu.save_result(task_id, result_dict))

                # 计算完成
                processed_cnt = total_cnt  # 确保完成度为 100%
                _update_progress_sync(processed_cnt, total_cnt, "SUCCESS", result="READY")
            except Exception as calc_err:
                logging.error(f"Async signal revenue task failed: {calc_err}")
                _update_progress_sync(processed_cnt, total_cnt, "FAIL", result=str(calc_err))

        # 提交到线程池，任务后台运行
        executor.submit(_blocking_job)

        return task_id