import logging
from typing import List, Tuple
from backend.app.domain.models.wallet import WalletModel
from backend.app.services.smw.smw_tb_handler import TransactionHandler
from backend.app.services.smw.smw_lw_st_handler import LowStatisticWalletHandler


class SMWFilterUtils:

    @staticmethod
    def filter_low_statistic_wallet(wallet_list: List[WalletModel], is_daily_fetch: bool = True) -> List[WalletModel]:
        res = LowStatisticWalletHandler.filter(wallet_list, is_daily_fetch=is_daily_fetch)
        return res

    @staticmethod
    def filter_transaction_behavior(wallet_list: List[WalletModel]) -> List[WalletModel]:
        res = TransactionHandler.filter(wallet_list)
        return res

    @staticmethod
    def start_filter(wallet_list: List[WalletModel], is_daily_fetch: bool = True) -> Tuple[List[WalletModel], List[WalletModel], List[WalletModel]]:
        res1 = SMWFilterUtils.filter_low_statistic_wallet(wallet_list, is_daily_fetch=is_daily_fetch)
        res1_keys = {(wallet.chain, wallet.address) for wallet in res1}
        eliminated_by_low_statistic = [wallet for wallet in wallet_list if (wallet.chain, wallet.address) not in res1_keys]

        res = SMWFilterUtils.filter_transaction_behavior(res1)
        res_keys = {(wallet.chain, wallet.address) for wallet in res}
        eliminated_by_transaction_behavior = [wallet for wallet in res1 if (wallet.chain, wallet.address) not in res_keys]

        logging.info(f"Origin wallet num: {len(wallet_list)}")
        logging.info(f"Low stats wallet num: {len(eliminated_by_low_statistic)}")
        logging.info(f"Bad tx behavior wallet num: {len(eliminated_by_transaction_behavior)}")
        return res, eliminated_by_low_statistic, eliminated_by_transaction_behavior