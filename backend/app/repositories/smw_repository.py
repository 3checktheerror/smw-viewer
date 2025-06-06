import logging
from typing import List, Dict

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




    def find_bad_wallet_possess_garbage_tokens(self, wallet_list: List[WalletModel], garbage_tokens: List[TokenModel]) -> List[WalletModel]:
        WalletUtils.group_wallet_by_chain(wallet_list)
        pass