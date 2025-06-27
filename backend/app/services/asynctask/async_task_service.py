from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any

from backend.app.api.schemas.signal_revenue_schemas import SignalRevenueRequest
from backend.app.services.revenue.signal_pl_calculator import SignalRevenueCalculator
from backend.app.utils.task_stage_utils import TaskStageUtils


class NoSignalsFoundError(Exception):
    """当找不到符合条件的信号数据时抛出此异常。"""
    pass


class AsyncProgressService:
    """Service that handles long-running tasks and reports progress via Redis."""

    _executor: Optional[ThreadPoolExecutor] = None

    @classmethod
    def _get_executor(cls) -> ThreadPoolExecutor:
        if cls._executor is None:
            # 默认线程池大小为 CPU 核心数 * 2, 如果以后有需要可以做成可配置
            cls._executor = ThreadPoolExecutor()
        return cls._executor

    @classmethod
    async def _estimate_total_signals(cls, request: SignalRevenueRequest) -> int:
        """在线程池中执行阻塞的 MongoDB 查询来预估信号总数。"""
        loop = asyncio.get_running_loop()
        executor = cls._get_executor()

        def _blocking_query() -> int:
            try:
                from datetime import datetime
                from backend.app.utils.mongo_client import MongoDBClient

                original_start_ts, original_end_ts = request.start_ts, request.end_ts
                start_ts = original_start_ts + 86400
                end_ts = original_end_ts + 86400

                mongo_client = MongoDBClient()
                start_date_str = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d')
                end_date_str = datetime.fromtimestamp(end_ts).strftime('%Y-%m-%d')

                query: dict = {"store_time": {"$gte": start_date_str, "$lte": end_date_str}}
                if request.whitelist_tokens:
                    query["token"] = {"$in": request.whitelist_tokens}
                elif request.blacklist_tokens:
                    query["token"] = {"$nin": request.blacklist_tokens}
                projection = {"first_signal_time": 1}

                raw_signals = mongo_client.find_many("debot_signal", query, projection=projection, db_name="graph")
                # 根据 first_signal_time 再做一次过滤
                filtered_signals = [s for s in raw_signals if original_start_ts <= s.get('first_signal_time', 0) <= original_end_ts]
                return len(filtered_signals)
            except Exception as e:
                logging.error(f"Failed to estimate total signals: {e}", exc_info=True)
                raise  # Propagate exception

        try:
            total_count = await loop.run_in_executor(executor, _blocking_query)
            return total_count
        except Exception as e:
            raise ValueError(f"预估信号总数时出错: {e}")

    # ----------------------------------------------------------------------
    # Signal-revenue specific implementation
    # ----------------------------------------------------------------------
    @classmethod
    async def create_signal_revenue_task(cls, request: SignalRevenueRequest) -> str:
        """Create background task for signal revenue calculation and return a task_id."""

        # 1. 预估信号总数，如果没有数据则直接报错，不创建任务
        total_cnt = await cls._estimate_total_signals(request)
        if total_cnt == 0:
            raise NoSignalsFoundError("没有找到符合筛选条件的信号数据")

        # 2. 创建任务并初始化进度
        task_id = await TaskStageUtils.create_task()
        logging.info(f"Created async signal revenue task: {task_id}, processing {total_cnt} signals.")

        # 3. 将耗时计算放到线程池中执行
        executor = cls._get_executor()

        def _blocking_job(known_total: int):
            """同步函数，在线程池中执行。"""
            import asyncio as _asyncio

            processed_cnt: int = 0
            total_cnt: int = known_total

            # 本地辅助函数，用同步方式更新 Redis 进度
            def _update_progress_sync(progress: int, total: int, status: str, result=None):
                async def _inner():
                    await TaskStageUtils.update_progress(task_id, progress, total, status, result)
                try:
                    # 在新线程中运行新的事件循环来执行异步代码
                    _asyncio.run(_inner())
                except Exception as e:
                    logging.error(f"Failed to update task progress in Redis: {e}", exc_info=True)

            # progress 回调：拉取 KLine 时每完成 batch_size (50) 个 token 调用一次
            def _progress_callback(delta: int):
                nonlocal processed_cnt, total_cnt
                processed_cnt += delta
                _update_progress_sync(processed_cnt, total_cnt, "RUNNING")

            try:
                # 预估总数已前置，此处直接更新进度
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
                logging.error(f"Async signal revenue task {task_id} failed: {calc_err}", exc_info=True)
                _update_progress_sync(processed_cnt, total_cnt, "FAIL", result=str(calc_err))

        # 提交到线程池，任务后台运行
        executor.submit(_blocking_job, total_cnt)

        return task_id