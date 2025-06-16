import logging
from typing import List, Dict, Any
from backend.app.domain.models.token import TokenModel, TokenRevenueModel
from backend.app.utils.http_utils import DebotHTTPUtils
from backend.app.utils.thread_pool import ThreadPoolManager


class KLineFetcher:
    def _fetch_one_kline(self, token: TokenRevenueModel, start_ts: int, duration: int, interval: int) -> Dict[str, Any]:
        """
        Fetches K-line data for a single token.
        """
        endpoint = "/api/market/v4"
        end_ts = start_ts + duration
        limit = (end_ts - start_ts) // interval + 2
        params = {
            "token": token.address,
            "chain": token.chain,
            "limit": limit,
            "end": end_ts,
            "interval": interval,
        }


        try:
            response = DebotHTTPUtils.get(endpoint=endpoint, params=params)

            if response and response.get("code") == 0 and "data" in response:
                return {"token": token, "kline_data": response["data"]["list"]}
            else:
                logging.warning(f"Failed to fetch kline for {token.chain}:{token.address}. Response: {response}")
                return {"token": token, "kline_data": None}
        except Exception as e:
            logging.error(f"Exception fetching kline for {token.chain}:{token.address}: {e}")
            return {"token": token, "kline_data": None}

    def fetch_klines(
            self,
            token_list: List[TokenRevenueModel],
            duration: int,
            interval: int = 1
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetches K-line data for a list of tokens in parallel.

        Args:
            token_list: List of TokenRevenueModel objects.
            start_ts: The start timestamp.
            duration: The duration in seconds.
            interval: The time interval.

        Returns:
            A dictionary where keys are chain names, and values are dictionaries
            mapping token addresses to their corresponding K-line data.
        """

        with ThreadPoolManager(max_workers=30) as manager:
            tasks_args = [(token, token.first_signal_time, duration, interval) for token in token_list]
            results = manager.execute_tasks_and_wait(self._fetch_one_kline, tasks_args, show_log=True)

        final_results: Dict[str, Dict[str, Any]] = {}
        for result in results:
            if result and result.get("kline_data"):
                token = result["token"]
                chain = token.chain
                address = token.address

                if chain not in final_results:
                    final_results[chain] = {}

                final_results[chain][address] = result["kline_data"]

        return final_results
