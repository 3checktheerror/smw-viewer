"""
钱包仓储类
"""
import logging
from typing import Dict, List
from backend.app.utils.pg_client import PostgreSQLClient
from backend.app.utils.time_utils import TimeUtils

class WalletRepository:
    """钱包仓储类"""
    
    def __init__(self):
        self.pg_client = PostgreSQLClient()
    
    def get_token_wallets(self, token_list: List[str], chain: str) -> Dict[str, List[str]]:
        start_time, end_time = TimeUtils.get_prev_utc_day_time_range()
        logging.info(f"get wallet from timestamp {start_time} to {end_time}")
        
        if not token_list:
            return {}

        return self.pg_client.get_distinct_wallets_by_tokens(chain, token_list, start_time, end_time)