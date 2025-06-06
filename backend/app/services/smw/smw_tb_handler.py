import logging
import uuid
from typing import List, Dict
from collections import defaultdict

from backend.app.domain.models.token import TokenModel
from backend.app.domain.models.wallet import WalletModel
from backend.app.repositories.smw_repository import SMWRepository
from backend.app.repositories.token_repository import HotTokenRepository
from backend.app.services.smw.smw_filter_utils import SMWFilterUtils
from backend.app.services.smw.utils.token_utils import TokenUtils
from backend.app.utils.pg_client import PostgreSQLClient


class TransactionHandler:

    def __init__(self):
        self.pg_client = PostgreSQLClient()
        self.smw_repository = SMWRepository()
        self.token_repository = HotTokenRepository()

    def _filter_holding_stats(self, wallet_list: List[WalletModel]) -> List[WalletModel]:
        """
        获取钱包持有时间统计并过滤
        
        Args:
            wallet_list: 钱包模型列表
            
        Returns:
            List[WalletModel]: 过滤后的钱包列表（持仓时间>500秒）
        """
        if not wallet_list:
            return []
        
        logging.info(f"开始处理 {len(wallet_list)} 个钱包的持有时间统计")
        
        # 按chain分组钱包
        chain_wallet_groups: Dict[str, List[WalletModel]] = defaultdict(list)
        for wallet in wallet_list:
            chain_wallet_groups[wallet.chain].append(wallet)

        # 存储所有钱包的持有时间统计
        all_holding_times = {}
        
        # 为每个chain分别查询持有时间
        for chain, wallets in chain_wallet_groups.items():
            logging.info(f"开始处理 {chain} 链上的 {len(wallets)} 个钱包")
            
            wallet_addresses = [wallet.address for wallet in wallets]
            holding_times = self.smw_repository.get_avg_holding_time(wallet_addresses, chain)
            
            # 合并到总的持有时间字典中
            for wallet in wallets:
                holding_time = holding_times.get(wallet.address, 0.0)
                all_holding_times[wallet.address] = holding_time
                logging.debug(f"钱包 {wallet.address} 在 {chain} 链上的平均持有时间: {holding_time:.2f} 秒")
        
        # 过滤持仓时间大于500秒的钱包
        filtered_wallets = []
        for wallet in wallet_list:
            holding_time = all_holding_times.get(wallet.address, 0.0)
            if holding_time > 500:
                filtered_wallets.append(wallet)
                logging.debug(f"钱包 {wallet.address} 符合条件，持有时间: {holding_time:.2f} 秒")
            else:
                logging.debug(f"钱包 {wallet.address} 被过滤，持有时间: {holding_time:.2f} 秒 <= 500秒")
        
        logging.info(f"持有时间统计处理完成，共处理 {len(wallet_list)} 个钱包，过滤后剩余 {len(filtered_wallets)} 个钱包")
        return filtered_wallets



    @staticmethod
    def filter(wallet_list: List[WalletModel]) -> List[WalletModel]:
        """
        完整的钱包过滤流程
        
        Args:
            wallet_list: 钱包模型列表
            
        Returns:
            List[WalletModel]: 经过所有过滤条件后的钱包列表
        """
        handler = TransactionHandler()
        garbage_tokens = TokenUtils.get_wallet_group_bad_tokens(wallet_list)
        # 第一步：过滤持有时间统计
        stats_filtered = handler._filter_holding_stats(wallet_list)
        # 第二步：过滤持有低流动性代币的钱包 + 过滤买入貔貅币钱包 + 过滤2天内没有买入新币钱包
        res = SMWRepository().find_bad_wallet_possess_garbage_tokens(stats_filtered, garbage_tokens)

        
        return res