import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
from clickhouse_pool import ChPool


class ClickHouseClient:

    def __init__(self):
        self.pool = None
        self._create_pool()

    def _create_pool(self):
        try:
            self.pool = ChPool(
                host='192.200.99.10',
                port=9000,
                user='default',
                password='P@mao123',
                database='diting_database',
                connections_min=10,
                connections_max=30,
            )
            logging.info("ClickHouse pool created successfully")
        except Exception as e:
            logging.error(f"Error creating ClickHouse pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """返回 ClickHouse 客户端实例"""
        try:
            if not self.pool:
                self._create_pool()
            with self.pool.get_client() as ch_client:
                yield ch_client
        except Exception as e:
            logging.error(f"Database operation error: {e}")
            raise

    def execute(self, query: str, params: Optional[Dict] = None) -> List[Tuple]:
        """执行 ClickHouse 查询并返回结果"""
        with self.get_connection() as client:
            try:
                if params:
                    result = client.execute(query, params=params)
                else:
                    result = client.execute(query)
                return result
            except Exception as e:
                logging.error(f"ClickHouse query execution failed: {e}")
                raise

