"""
钱包仓储类
"""
import logging

import motor.motor_asyncio
from typing import Dict, List
from backend.app.utils.pg_client import PostgreSQLClient
from backend.app.utils.thread_pool import ThreadPoolManager
from backend.app.utils.time_utils import TimeUtils

class WalletRepository:
    """钱包仓储类"""
    
    def __init__(self):
        self.pg_client = PostgreSQLClient()
    
    def get_token_wallets(self, token_list: List[str], chain: str) -> Dict[str, List[str]]:
        start_time, end_time = TimeUtils.get_prev_utc_day_time_range()
        logging.info(f"get wallet from timestamp {start_time} to {end_time}")
        
        def query_token_wallets(token: str) -> tuple[str, List[str]]:
            wallets = self.pg_client.get_distinct_wallets_by_token(chain, token, start_time, end_time)
            return token, wallets
        
        task_args = [(token,) for token in token_list]

        
        with ThreadPoolManager(max_workers=30) as pool:
            results = pool.execute_tasks_and_wait(query_token_wallets, task_args, show_log=True)
        
        token_wallets = {}
        for result in results:
            if result:
                token, wallets = result
                token_wallets[token] = wallets
        
        return token_wallets