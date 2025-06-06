import logging
from typing import List
from backend.app.domain.models.wallet import WalletModel
from backend.app.services.smw.smw_tb_handler import TransactionHandler
from backend.app.services.smw.smw_lw_st_handler import LowStatisticWalletHandler


class SMWFilterUtils:

    @staticmethod
    def filter_low_statistic_wallet(wallet_list: List[WalletModel]) -> List[WalletModel]:
        res = LowStatisticWalletHandler.filter(wallet_list)
        return res

    @staticmethod
    def filter_transaction_behavior(wallet_list: List[WalletModel]) -> List[WalletModel]:
        res = TransactionHandler.filter(wallet_list)
        return res

    @staticmethod
    def start_filter(wallet_list: List[WalletModel]) -> List[WalletModel]:
        logging.info(f"Starting filter SMW: {len(wallet_list)}")
        res1 = SMWFilterUtils.filter_low_statistic_wallet(wallet_list)
        res = SMWFilterUtils.filter_transaction_behavior(res1)
        return res