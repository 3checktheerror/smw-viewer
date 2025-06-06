from typing import List

from backend.app.domain.models.wallet import WalletModel


class WalletUtils:
    @staticmethod
    def group_wallet_by_chain(wallet_list: List[WalletModel]):
        wallet_groups = {}
        wallet_mapping = {}
        for wallet in wallet_list:
            if wallet.chain not in wallet_groups:
                wallet_groups[wallet.chain] = []
            wallet_groups[wallet.chain].append(wallet.address)
            wallet_mapping[wallet.address] = wallet
        return wallet_groups, wallet_mapping
