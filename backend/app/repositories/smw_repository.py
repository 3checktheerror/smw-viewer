import logging
from typing import List, Dict, Optional

from redis.auth.token import TokenResponse

from backend.app.domain.models.token import TokenModel
from backend.app.domain.models.wallet import WalletModel
from backend.app.repositories.token_repository import HotTokenRepository
from backend.app.services.smw.utils.wallet_utils import WalletUtils
from backend.app.utils import RedisSentinelClient, MongoDBClient
from backend.app.utils.pg_client import PostgreSQLClient
from backend.app.utils.thread_pool import ThreadPoolManager


class SMWRepository:
    """聪明钱存储类"""

    def __init__(self):
        self.redis_client = RedisSentinelClient()
        self.mongodb_client = MongoDBClient()
        self.pg_client = PostgreSQLClient()
        self.token_repository = HotTokenRepository()
    
    def get_avg_holding_time(self, wallet_list: List[str], chain: str) -> Dict[str, float]:
        """
        查询钱包的平均持有时间
        
        Args:
            wallet_list: 钱包地址列表
            chain: 链名称
            
        Returns:
            Dict[str, float]: 钱包地址 -> 平均持有时间(秒)
        """
        if not wallet_list:
            return {}
        
        logging.info(f"开始查询 {len(wallet_list)} 个钱包在 {chain} 链上的平均持有时间")
        
        # 准备任务参数
        tasks_args = [(wallet, chain) for wallet in wallet_list]
        
        # 使用ThreadPoolManager进行并发查询
        with ThreadPoolManager(max_workers=20) as pool:
            results = pool.execute_tasks_and_wait(
                self._query_single_wallet_holding_time, 
                tasks_args,
            )
        
        # 整理结果
        wallet_holding_times = {}
        successful_count = 0
        total_wallets = len(wallet_list)
        
        for i, result in enumerate(results):
            wallet = wallet_list[i]
            if result is not None:
                wallet_holding_times[wallet] = result
                successful_count += 1
            else:
                wallet_holding_times[wallet] = 0.0

            if i % 100 == 0:
                logging.info(f"进度: {i}/{total_wallets} 个钱包处理完成")
                
        logging.info(f"查询完成: {successful_count}/{len(wallet_list)} 个钱包查询成功")
        return wallet_holding_times

    def _query_single_wallet_holding_time(self, wallet: str, chain: str) -> float:
        """
        查询单个钱包的平均持有时间
        
        Args:
            wallet: 钱包地址
            chain: 链名称
            
        Returns:
            float: 平均持有时间(秒)，如果查询失败返回0.0
        """
        table_name = f"t_transaction_daily_{chain}"
        
        sql = f"""
        WITH WalletTokenTimes AS (
            SELECT
                token,
                MIN(CASE WHEN first_trade = 1 THEN unix_time END) AS t1, 
                MAX(CASE WHEN op = 'sell' THEN unix_time END) AS t2
            FROM
                {table_name}
            WHERE
                wallet = %(wallet)s
            GROUP BY
                token
        ),
        ValidHoldingPeriods AS (
            SELECT
                token,
                t1,
                t2,
                (t2 - t1) AS holding_time
            FROM
                WalletTokenTimes
            WHERE
                t1 IS NOT NULL
                AND t2 IS NOT NULL 
                AND t2 > t1
        )
        SELECT
            COALESCE(AVG(holding_time), 0) AS average_holding_time_seconds
        FROM
            ValidHoldingPeriods
        """
        
        params = {'wallet': wallet}
        
        try:
            result = self.pg_client.execute(sql, params)
            if result and len(result) > 0:
                avg_holding_time = float(result[0][0])
                logging.debug(f"钱包 {wallet} 平均持有时间: {avg_holding_time:.2f} 秒")
                return avg_holding_time
            else:
                logging.warning(f"钱包 {wallet} 查询结果为空")
                return 0.0
        except Exception as e:
            logging.error(f"查询钱包 {wallet} 持有时间失败: {e}")
            return 0.0

    def _check_single_wallet_is_bad(self, wallet: WalletModel, garbage_token_map: Dict[str, TokenModel], token_repo: HotTokenRepository) -> Optional[WalletModel]:
        """
        检查单个钱包是否为垃圾钱包
        
        Args:
            wallet: 钱包模型
            garbage_token_map: 当前链的垃圾token map {token_address: TokenModel}
            token_repo: HotTokenRepository 实例
            
        Returns:
            如果为垃圾钱包则返回钱包模型，否则返回None
        """
        try:
            traded_token_pairs = token_repo.get_wallet_2d_trade_tokens(wallet.address, wallet.chain)
            
            if not traded_token_pairs:
                # 没有任何交易记录，也视为"垃圾钱包"（没有买入新币）
                return wallet

            traded_tokens = {token for token, pair in traded_token_pairs}
            
            new_token_count = 0
            has_traded_garbage = False
            
            for token_address in traded_tokens:
                if token_address in garbage_token_map:
                    has_traded_garbage = True
                    token_model = garbage_token_map[token_address]
                    
                    if token_model.is_honeypot or token_model.is_low_liquidity:
                        logging.debug(f"钱包 {wallet.address} 因交易了貔貅或低流动性代币 {token_address} 被标记为垃圾钱包")
                        return wallet
                    
                    if not token_model.is_old:
                        new_token_count += 1
            
            if has_traded_garbage and new_token_count == 0:
                logging.debug(f"钱包 {wallet.address} 因2天内没有买入新币被标记为垃圾钱包")
                return wallet
                
        except Exception as e:
            logging.error(f"检查钱包 {wallet.address} 时发生错误: {e}")
            
        return None

    def filter_bad_wallet_possess_garbage_tokens(self, wallet_list: List[WalletModel], garbage_tokens: List[TokenModel]) -> List[WalletModel]:
        logging.info(f"开始筛选垃圾钱包，总钱包数: {len(wallet_list)}, 垃圾代币数: {len(garbage_tokens)}")
        
        # 1. 按链对垃圾代币进行分组
        chain_garbage_tokens_map: Dict[str, Dict[str, TokenModel]] = {}
        for token in garbage_tokens:
            if token.chain not in chain_garbage_tokens_map:
                chain_garbage_tokens_map[token.chain] = {}
            chain_garbage_tokens_map[token.chain][token.address] = token

        # 2. 准备并发任务
        tasks_args = []
        token_repo = HotTokenRepository()
        for wallet in wallet_list:
            garbage_map = chain_garbage_tokens_map.get(wallet.chain, {})
            tasks_args.append((wallet, garbage_map, token_repo))
        
        if not tasks_args:
            logging.warning("没有需要处理的钱包任务")
            return []

        # 3. 使用线程池并发执行检查
        bad_wallets: List[WalletModel] = []
        with ThreadPoolManager(max_workers=40) as pool:
            # show_log=False因为我们只关心最终结果，并且已经在单任务函数中记录了必要信息
            results = pool.execute_tasks_and_wait(
                self._check_single_wallet_is_bad,
                tasks_args,
                show_log=True
            )
            
            for result in results:
                if result:
                    bad_wallets.append(result)

        logging.info(f"垃圾钱包筛选完成，共找到 {len(bad_wallets)} 个垃圾钱包")
        
        good_wallets = []
        bad_wallet_addresses = {w.address for w in bad_wallets}
        for w in wallet_list:
            if w.address not in bad_wallet_addresses:
                good_wallets.append(w)

        logging.info(f"过滤后剩余 {len(good_wallets)} 个优质钱包")
        return good_wallets