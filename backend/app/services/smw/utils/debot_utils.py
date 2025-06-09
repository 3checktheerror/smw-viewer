import time
from typing import Dict, Any, List, Tuple, Optional
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend.app.utils.http_utils import DebotHTTPUtils
from backend.app.utils.thread_pool import ThreadPoolManager


class DebotAPIUtils:


    @staticmethod
    def get_wallet_7d_token(wallet: str, chain: str) -> Dict[str, Any]:
        """获取代币分布数据并格式化"""
        params = {"chain": chain, "wallet": wallet, "duration": "7D"}
        response = DebotHTTPUtils.get(endpoint='api/dashboard/wallet/market/profit_distribution', params=params)

        if not response:
            return {
                "7D_token_num": 0,
                "7D_token_address": []
            }

        if response.get("code") != 0 or not isinstance(response.get("data"), list):
            return {
                "7D_token_num": 0,
                "7D_token_address": []
            }

        token_chains = []
        token_addresses = []

        for item in response["data"]:
            token = item.get("token", {})
            if token.get("chain") and token.get("address"):
                token_chains.append(token["chain"])
                token_addresses.append(token["address"])

        return {
            "7D_token_num": len(response["data"]),
            "7D_token_address": token_addresses
        }

    @staticmethod
    def get_low_liquidity_tokens(pair_list: List[Tuple[str, str]], chain: str) -> List[str]:
        """
        获取低流动性代币列表（流动性 < 10000）
        
        Args:
            pair_list: token和pair的元组列表 [(token, pair), ...]
            chain: 链名称
            
        Returns:
            List[str]: 低流动性代币地址列表
        """
        if not pair_list:
            return []
            
        try:
            def check_token_liquidity(token: str, pair: str) -> Tuple[str, bool]:
                """检查单个代币的流动性"""
                try:
                    params = {
                        "pair": pair,
                        "chain": chain,
                        "token": token
                    }
                    response = DebotHTTPUtils.get(
                        endpoint='api/dashboard/token/trading/stats',
                        params=params
                    )
                    
                    if not response or response.get("code") != 0:
                        logging.warning(f"Failed to get liquidity data for token {token}")
                        return token, False
                    
                    data = response.get("data", {})
                    liquidity = data.get("liquidity", 0)
                    holders = data.get("holders", 0)
                    
                    # 返回是否为低流动性代币（流动性 < 10000）
                    is_low_liquidity = float(liquidity) < 10000 or int(holders) <= 300
                    return token, is_low_liquidity
                    
                except Exception as e:
                    logging.error(f"Error checking liquidity for token {token}: {e}")
                    return token, False
            
            total_tokens = len(pair_list)
            logging.info(f"Starting to check liquidity for {total_tokens} tokens on chain {chain}")
            
            low_liquidity_tokens = []
            
            # 使用30个线程并发查询
            with ThreadPoolManager(max_workers=30) as pool:
                tasks_args = pair_list
                results = pool.execute_tasks_and_wait(check_token_liquidity, tasks_args)
                
                completed = 0
                for result in results:
                    try:
                        if result is not None:
                            token, is_low_liquidity = result
                            if is_low_liquidity:
                                low_liquidity_tokens.append(token)
                        
                        completed += 1
                        if completed % 20 or completed == total_tokens:
                            progress = (completed / total_tokens) * 100
                            logging.info(f"Liquidity check progress: {completed}/{total_tokens} ({progress:.1f}%) tokens processed")
                            
                    except Exception as e:
                        logging.error(f"Error processing token liquidity result: {e}")
                        completed += 1
            
            logging.info(f"Completed liquidity check for {total_tokens} tokens. Found {len(low_liquidity_tokens)} low liquidity tokens")
            return low_liquidity_tokens
            
        except Exception as e:
            logging.error(f"Error in get_low_liquidity_tokens: {e}")
            return []

    @staticmethod
    def get_honeypot_tokens(tokens: List[str], chain: str) -> List[str]:
        """
        获取貔貅币列表
        
        Args:
            tokens: 代币地址列表
            chain: 链名称
            
        Returns:
            List[str]: 貔貅币代币地址列表
        """
        if not tokens:
            return []

        def is_honeypot_token(token: str, chain: str) -> Tuple[str, bool]:
            """判断代币是否为貔貅币"""
            try:
                # 调用第一个接口：token_analyzer
                analyzer_url = f"api/token_analyzer/{chain}/{token}"
                token_analyzer_info = DebotHTTPUtils.get(endpoint=analyzer_url)

                # 调用第二个接口：token safe_info
                safe_info_params = {"chain": chain, "token": token}
                token_safe_info = DebotHTTPUtils.get(endpoint='api/dashboard/token/safe_info', params=safe_info_params)

                # 从 token_analyzer_info 提取数据
                warnings = None
                audit = None
                if token_analyzer_info and "data" in token_analyzer_info and token_analyzer_info["data"]:
                    warnings = token_analyzer_info["data"].get("warnings")
                    audit = token_analyzer_info["data"].get("audit")

                # 从 token_safe_info 提取官方判断和 goplus 数据
                official_is_honeypot = False
                official_is_not_honeypot = False
                goplus_is_honeypot = None

                if token_safe_info and "data" in token_safe_info and token_safe_info["data"]:
                    data = token_safe_info["data"]

                    # 检查官方判断
                    if "debot" in data and data["debot"] and "ishoneypot" in data["debot"]:
                        official_is_honeypot = data["debot"]["ishoneypot"] == "1"
                        official_is_not_honeypot = data["debot"]["ishoneypot"] == "0"

                    # 检查 goplus 数据
                    if "goplus" in data and data["goplus"] and "is_honeypot" in data["goplus"]:
                        goplus_is_honeypot = data["goplus"]["is_honeypot"]

                # 应用判断逻辑
                warning_list = warnings.split(";") if warnings else []
                is_honeypot = False

                if warning_list and warning_list[0] and warning_list[0] != "0":
                    is_honeypot = True
                    # 如果经过检测，则设置为低风险
                    if audit:
                        is_honeypot = False

                # 最终判断逻辑
                if official_is_honeypot:
                    final_result = 1
                elif official_is_not_honeypot:
                    final_result = 0
                elif is_honeypot:
                    final_result = 1
                else:
                    # 使用 goplus 的结果，如果没有则默认为0
                    final_result = goplus_is_honeypot if goplus_is_honeypot is not None else 0

                return token, final_result == 1

            except Exception as e:
                logging.error(f"Error in honeypot detection for {token} on {chain}: {e}")
                # 发生错误时，为了安全起见，返回 True（认为是貔貅币）
                return token, True

        honeypot_tokens = []
        with ThreadPoolManager(max_workers=30) as pool:
            tasks_args = [(token, chain) for token in tokens]
            results = pool.execute_tasks_and_wait(is_honeypot_token, tasks_args)

            for result in results:
                if result:
                    token, is_honeypot = result
                    if is_honeypot:
                        honeypot_tokens.append(token)
        
        return honeypot_tokens


    @staticmethod
    def get_token_age(
            chain: str,
            tokens: List[str]
    ) -> List[Dict[str, Any]]:
        """
        判断一组代币是否为老币 (3天前创建)

        Args:
            chain: 链名称
            tokens: 代币地址列表

        Returns:
            List[Dict[str, Any]]: 包含代币年龄信息的字典列表, e.g. [{"is_old": True, "token": "0x...", "chain": "bsc"}]
        """
        if not tokens:
            return []

        def _check_token_age(token: str, chain: str) -> Optional[Dict[str, Any]]:
            """检查单个代币是否为老币"""
            try:
                response = DebotHTTPUtils.get(
                    endpoint="api/market/token/info",
                    params={"chain": chain, "token": token}
                )

                if not response or response.get("code") != 0:
                    logging.warning(f"Failed to get token info for {token} on {chain}")
                    return None

                data = response.get("data")
                if data is None:
                    logging.info(f"Token-chain mismatch: {token}, {chain}")
                    return None

                meta = data.get("meta", {})
                tag_map = data.get("tag_map", {}) or {}
                now_utc = datetime.now(timezone.utc)
                midnight_utc = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
                five_days_ago_midnight_utc = midnight_utc - timedelta(days=5)
                five_days_ago = int(five_days_ago_midnight_utc.timestamp())
                creation_timestamp = int(meta.get("creation_timestamp", 0))
                graduated_timestamp = int(tag_map.get("graduated", 0))

                if graduated_timestamp > 0:
                    is_old = graduated_timestamp < five_days_ago
                else:
                    is_old = creation_timestamp > 0 and creation_timestamp < five_days_ago

                return {
                    "is_old": is_old,
                    "token": token,
                    "chain": chain
                }

            except Exception as e:
                logging.error(f"Error checking token age for {token} on {chain}: {e}")
                return None

        with ThreadPoolManager(max_workers=50) as pool:
            tasks_args = [(token, chain) for token in tokens]
            results = pool.execute_tasks_and_wait(_check_token_age, tasks_args, show_log=False)

            return [res for res in results if res is not None]


    @staticmethod
    def get_wallet_avg_buy(self, wallet: str, chain: str, tokens: set) -> Dict[str, Any]:

        STABLECOINS = {
            "solana": [
                "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                "9zNQRsGLjNKwCUU5Gq5LR8beUCPzQMVMqKAi3SSZh54u",
                "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo",
                "9gP2kCy3wA1ctvYWQk75guqXuHfrEomqydHLtcTCqiLa",
                "So11111111111111111111111111111111111111112"    # SOL
            ],
            "base": [
                "0x4200000000000000000000000000000000000006",  # WETH
                "0xd07379a755a8f11b57610154861d694b2a0f615a"  # Base
            ],
            "bsc": [
                "0x90c97f71e18723b0cf0dfa30ee176ab653e89f40",
                "0x40af3827f39d0eacbf4a168f8d4ee67c121d11c9",
                "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
            ]
        }


        """获取并计算持仓代币统计信息"""
        total_buy_times = 0
        stable_buy_volumes_sum = 0.0
        stable_buy_times_sum = 0
        next_cursor = ""

        # 预处理地址集合
        target_tokens = {t.lower() for t in tokens}
        stable_coins = {c.lower() for c in STABLECOINS.get(chain, [])}

        for _ in range(self.max_pages):
            try:
                params = {
                    "chain": chain,
                    "wallet": wallet,
                    "sort_field": "last_active_timestamp",
                    "sort_order": "desc",
                    "next": next_cursor
                }

                response = self.client.get(
                    "https://preapi.debot.ai/api/dashboard/wallet/latest/pnl",
                    params=params,
                    timeout=self.timeout
                )

                if not response:
                    break

                data = response.json() or {}
                page_data = data.get("data") or {}
                holding_tokens = page_data.get("holding_tokens", [])

                # 处理当前页数据
                for item in holding_tokens:
                    token_info = item.get("token", {})
                    token_addr = token_info.get("address", "").lower()

                    # 统计目标token
                    if token_addr in target_tokens:
                        total_buy_times += item.get("buy_times", 0)

                    # 统计稳定币
                    if token_addr in stable_coins:
                        stable_buy_volumes_sum += item.get("buy_volume", 0)
                        stable_buy_times_sum += item.get("buy_times", 0)

                # 检查退出条件（7天）
                if holding_tokens:
                    current_time = time.time()
                    last_token = holding_tokens[-1]
                    last_active = last_token.get("last_active_timestamp", 0)

                    if current_time - last_active > 604802:  # 7天+2秒缓冲
                        break

                next_cursor = page_data.get("next", "")
                if not next_cursor:
                    break

            except Exception as e:
                logging.error(f"HoldingTokens fetch failed: {str(e)}")
                break

        return {
            "total_buy_times": total_buy_times,
            "stable_buy_volumes_sum": round(stable_buy_volumes_sum, 4),
            "stable_buy_times_sum": stable_buy_times_sum
        }