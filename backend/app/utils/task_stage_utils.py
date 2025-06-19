import json
import uuid
from typing import Dict, Any, Optional

from backend.app.utils.redis_client import RedisClient


class TaskStageUtils:
    
    _task_key_prefix = "task_progress:"
    _expire_seconds = 600  # 30 minitues

    _result_meta_prefix = "task_result_meta:"
    _result_part_prefix = "task_result_part:"
    _chunk_size = 100  # 每个 key 存储 token_results 的条目数

    @classmethod
    async def create_task(cls) -> str:
        """
        创建一个新的任务并返回任务ID
        """
        task_id = str(uuid.uuid4())
        try:
            await cls.update_progress(task_id, 0, 100, "PENDING")
        except Exception as e:
            # 即使 Redis 写入失败也返回 task_id，后续仍可重试
            import logging
            logging.error(f"Failed to initialize task progress in Redis: {e}")
        return task_id

    @classmethod
    async def update_progress(cls, task_id: str, progress: int, total: int, status: str, result: Optional[Any] = None):
        """
        更新任务进度
        """
        import asyncio, logging
        key = f"{cls._task_key_prefix}{task_id}"
        data = {
            "progress": progress,
            "total": total,
            "status": status
        }
        if result is not None:
            # 仅允许存储很小的 result（如字符串标识或摘要）
            data["result"] = result

        max_retry = 3
        for i in range(max_retry):
            try:
                redis_cli = RedisClient.get_client()
                await redis_cli.set(key, json.dumps(data), ex=cls._expire_seconds)
                return
            except Exception as e:
                logging.warning(f"Redis set failed (attempt {i+1}/{max_retry}): {e}")
                await asyncio.sleep(0.5)
        logging.error("Exceeded retry limit when updating task progress")

    @classmethod
    async def get_progress(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务进度
        """
        import asyncio, logging
        key = f"{cls._task_key_prefix}{task_id}"
        max_retry = 3
        for i in range(max_retry):
            try:
                redis_cli = RedisClient.get_client()
                data_str = await redis_cli.get(key)
                if data_str:
                    return json.loads(data_str)
                return None
            except Exception as e:
                logging.warning(f"Redis get failed (attempt {i+1}/{max_retry}): {e}")
                await asyncio.sleep(0.5)
        logging.error("Exceeded retry limit when fetching task progress")
        return None

    # ------------------------------------------------------------------
    # Result 存取：将大结果拆分成多个 key
    # ------------------------------------------------------------------

    @classmethod
    async def save_result(cls, task_id: str, result_data: Dict[str, Any]):
        """将庞大的 result_data 拆分写入 Redis。"""
        import asyncio, logging

        # 分离 token_results 与汇总信息
        meta = result_data.copy()
        token_results = meta.pop("token_results", [])

        # 写 meta
        meta_key = f"{cls._result_meta_prefix}{task_id}"
        try:
            redis_cli = RedisClient.get_client()
            await redis_cli.set(meta_key, json.dumps(meta), ex=cls._expire_seconds)
        except Exception as e:
            logging.error(f"Failed to save result meta for {task_id}: {e}")
            return

        # 写 token_results 分片
        if not token_results:
            return

        total_parts = (len(token_results) + cls._chunk_size - 1) // cls._chunk_size
        tasks = []
        for idx in range(total_parts):
            part_list = token_results[idx * cls._chunk_size : (idx + 1) * cls._chunk_size]
            part_key = f"{cls._result_part_prefix}{task_id}:{idx}"

            async def _set(k, data):
                try:
                    redis_cli_local = RedisClient.get_client()
                    await redis_cli_local.set(k, json.dumps(data), ex=cls._expire_seconds)
                except Exception as e:
                    logging.error(f"Failed to save result part {k}: {e}")

            tasks.append(_set(part_key, part_list))

        await asyncio.gather(*tasks)

    @classmethod
    async def get_result_meta(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """获取结果的 meta 信息（不含 token_results）。"""
        import logging
        try:
            redis_cli = RedisClient.get_client()
            val = await redis_cli.get(f"{cls._result_meta_prefix}{task_id}")
            return json.loads(val) if val else None
        except Exception as e:
            logging.error(f"Failed to fetch result meta for {task_id}: {e}")
            return None

    @classmethod
    async def get_result_part(cls, task_id: str, index: int) -> Optional[Any]:
        import logging, json as _json
        try:
            redis_cli = RedisClient.get_client()
            val = await redis_cli.get(f"{cls._result_part_prefix}{task_id}:{index}")
            return _json.loads(val) if val else None
        except Exception as e:
            logging.error(f"Failed to fetch result part {index} for {task_id}: {e}")
            return None