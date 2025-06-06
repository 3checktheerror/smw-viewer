"""
热门代币查找器任务
"""
import json
import logging
from typing import List, Tuple, Optional, Dict
from backend.app.utils import ThreadPoolManager
from backend.app.utils.http_utils import DebotHTTPUtils
from backend.app.repositories.token_repository import HotTokenRepository
from backend.app.utils.log_utils import setup_logging
from backend.app.utils.time_utils import TimeUtils


class HotTokenFinder:
    """热门代币查找器"""
    
    def __init__(self):
        self.repository = HotTokenRepository()
    
    def scan_streams_for_tokens(self) -> List[Tuple[str, str, str]]:
        logging.info("Starting scan on-chain tokens")
        all_tokens = []
        streams = self.repository.get_token_streams()
        for stream_key in streams:
            try:
                tokens = self.repository.read_tokens_from_stream(stream_key)
                all_tokens.extend(tokens)
                logging.debug(f"Found {len(tokens)} tokens in stream {stream_key}")
            except Exception as e:
                logging.error(f"Error scanning stream {stream_key}: {e}")
        
        logging.info(f"On-chain token scan completed, total tokens found: {len(all_tokens)}")
        return all_tokens
    
    def _process_onchain_tokens(self, tokens: List[Tuple[str, str, str]]) -> int:

        if not tokens:
            return 0
        qualified_count = 0

        try:
            tokens = self.repository.get_token_status(tokens)
            qualified_tokens = []
            for token_info, stats in tokens.items():
                if stats is None:
                    continue
                if not self.repository.is_token_qualified(stats):
                    continue
                qualified_tokens.append((token_info, stats))

            if qualified_tokens:
                for token_info, stats in qualified_tokens:
                    chain, token_address, source = token_info
                    success = self.repository.save_qualified_token(chain, token_address, source, stats)
                    if success: qualified_count += 1
        except Exception as e:
            logging.error(f"Error in get_token_status: {e}")
        return qualified_count

    def _handle_onchain_tokens(self) -> int:
        tokens = self.scan_streams_for_tokens()
        if not tokens:
            logging.info("No tokens found in streams")
            return 0
        qualified_count = self._process_onchain_tokens(tokens)
        self.repository.close_connections()
        logging.info(f"find_daily_token_task completed, found {qualified_count} qualified tokens")
        return qualified_count


    def _handle_rank_tokens(self) -> int:
        chains = ['solana', 'bsc', 'base']
        count = 0
        for chain in chains:
            params = {
                "chain": chain,
                "duration": "5m",
                "sort_field": "creation_timestamp",
                "sort_order": "desc",
                "filter": json.dumps({"mkt_cap": [20000, 1e308], "liquidity": [10000, 1e308]}),
                "is_hide_honeypot": "true"
            }

            response = DebotHTTPUtils.get(endpoint='api/dashboard/chain/recommend/hot_token', params=params, timeout=10)

            documents = [{"token": item['address'], "chain": chain} for item in response.get('data', []) if
                         'address' in item]
            for doc in documents:
                doc['updated_ts'] = TimeUtils.get_current_ts()
            self.repository.save_rank_token(chain, documents)
            count += len(documents)

        logging.info(f"rank_tokens completed, found {count} ranked tokens")
        return count


    def run_scan_cycle(self) -> None:
        logging.info("Starting hot token scan cycle")
        with ThreadPoolManager(max_workers=2) as executor:
            function_configs = [
                self._handle_onchain_tokens,
                self._handle_rank_tokens
            ]
            results = executor.execute_multiple_functions(function_configs, show_log=False)
            onchain_token_count = results[0] if len(results) > 0 and results[0] is not None else 0
            rank_token_count = results[1] if len(results) > 1 and results[1] is not None else 0