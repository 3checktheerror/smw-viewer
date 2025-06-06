"""
Redis客户端工具类
"""
import logging

import redis
import redis.sentinel
from typing import Optional, List, Dict, Any, Union
from backend.app.core.config import settings
from backend.app.utils.thread_pool import ThreadPoolManager


class RedisSentinelClient:
    """Redis客户端封装类"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._sentinel: Optional[redis.sentinel.Sentinel] = None
    
    def get_client(self) -> Optional[redis.Redis]:
        """获取Redis客户端连接"""
        if self._client is None:
            self._client = self._create_connection()
        return self._client
    
    def _create_connection(self) -> Optional[redis.Redis]:
        """创建Redis连接"""
        try:
            self._sentinel = redis.sentinel.Sentinel(
                settings.redis_sentinel_addrs,
                sentinel_kwargs={'password': settings.redis_sentinel_password} if settings.redis_sentinel_password else {},
                socket_timeout=10
            )
            master = self._sentinel.master_for(
                settings.redis_master_name,
                password=settings.redis_master_password if settings.redis_master_password else None,
                db=settings.redis_db_num,
                socket_timeout=10,
                decode_responses=False
            )
            
            # logging.info("Successfully connected to Redis master")
            return master
            
        except redis.exceptions.TimeoutError as e:
            logging.error(f"Timeout error during Redis connection setup: {e}")
            return None
        except redis.exceptions.RedisError as e:
            logging.error(f"Error connecting to Redis: {e}")
            return None
    
    def reconnect(self) -> bool:
        """重新连接Redis"""
        self._client = None
        client = self.get_client()
        return client is not None
    
    def xrevrange(self, stream_key: str, max_id: str = '+', min_id: str = '-', count: int = None) -> List:
        """从流中读取消息（倒序）"""
        client = self.get_client()
        if client is None:
            return []
        try:
            return client.xrevrange(stream_key, max=max_id, min=min_id, count=count)
        except redis.exceptions.ResponseError as e:
            logging.error(f"Error reading stream {stream_key}: {e}")
            return []
        except redis.exceptions.RedisError as e:
            logging.error(f"Redis error while reading stream {stream_key}: {e}")
            return []
    
    def hgetall(self, key: str) -> Dict[bytes, bytes]:
        """获取哈希表的所有字段和值"""
        client = self.get_client()
        if client is None:
            return {}
        try:
            return client.hgetall(key)
        except redis.exceptions.TimeoutError as e:
            logging.error(f"Timeout fetching HASH for {key}: {e}")
            return {}
        except redis.exceptions.RedisError as e:
            logging.error(f"Redis error fetching HASH for {key}: {e}")
            return {}

    def pool_hgetall(self, keys: List[str], pool_size: int) -> Dict[str, Dict[bytes, bytes]]:

        client = self.get_client()
        if client is None or not keys:
            return {}
        try:
            result_dict = {}
            
            def fetch_hash(key: str) -> tuple[str, Dict[bytes, bytes]]:
                try:
                    hash_data = client.hgetall(key)
                    return key, hash_data if hash_data else {}
                except Exception as e:
                    logging.error(f"Error fetching hash for key {key}: {e}")
                    return key, {}

            tasks_args_list = [(key,) for key in keys]

            with ThreadPoolManager(max_workers=pool_size) as executor:
                list_of_results = executor.execute_tasks_and_wait(fetch_hash, tasks_args_list, show_log=False)
                if list_of_results:
                    for item in list_of_results:
                        if item is not None:
                            key_from_result, hash_data_from_result = item
                            result_dict[key_from_result] = hash_data_from_result

            return result_dict
            
        except Exception as e:
            logging.error(f"Unexpected error during batch hgetall: {e}")
            return {}