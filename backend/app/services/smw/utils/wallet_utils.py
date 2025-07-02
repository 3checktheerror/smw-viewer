from typing import List, Dict

from backend.app.domain.models.wallet import WalletModel
from backend.app.services.smw.smw_lw_st_handler import LowStatisticWalletHandler
from backend.app.utils.thread_pool import ThreadPoolManager


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

    @staticmethod
    def get_wallet_daily_statistics(wallet_list: List[WalletModel]) -> Dict[str, Dict]:
        wallet_groups, _ = WalletUtils.group_wallet_by_chain(wallet_list)
        all_stats = {}
        handler = LowStatisticWalletHandler()

        for chain, addresses in wallet_groups.items():
            if not addresses:
                continue

            def process_batch(batch_wallets: List[str]) -> Dict[str, Dict]:
                batch_stats = {}
                pnl_data = handler.get_wallet_pnl(chain, batch_wallets)
                token_win_rate_data = handler.get_wallet_token_win_rate(chain, batch_wallets)

                for wallet_address in batch_wallets:
                    pnl_info = pnl_data.get(wallet_address, {})
                    token_win_rate = token_win_rate_data.get(wallet_address, 0.0)

                    batch_stats[wallet_address] = {
                        'pnl': pnl_info.get('pnl_7d', 0.0),
                        'winrate': pnl_info.get('winrate_7d', 0.0),
                        'token_winrate': token_win_rate
                    }
                return batch_stats

            batch_size = 5000
            wallet_batches = [addresses[i:i + batch_size] for i in range(0, len(addresses), batch_size)]

            with ThreadPoolManager(max_workers=1) as executor:
                tasks_args = [(batch,) for batch in wallet_batches]
                results = executor.execute_tasks_and_wait(process_batch, tasks_args, show_log=False)
                for result in results:
                    if result:
                        all_stats.update(result)

        return all_stats

if __name__ == '__main__':
    # 1. 构造一个 mock 的 List[WalletModel]
    mock_wallets: List[WalletModel] = [
        WalletModel(chain="solana", address="143GFLEUDji7LvAKm1wvP91Jy8c3MjT3XnC2DrZs1gHe", stored_date="2025-07-01"),
        WalletModel(chain="solana", address="3jP1Lw8Y11Wc6y2TCpUnwaG7RzVgHPoPFGMMmusurbXr", stored_date="2025-07-01"),
        WalletModel(chain="bsc", address="0x0982f0115b5855004e37df6f2c0ed927dd2ed796", stored_date="2025-07-01"),
        WalletModel(chain="base", address="0x047801d2cf337027e49264a4f2a082750f83d2f5", stored_date="2025-07-01"),
    ]

    print(WalletUtils.get_wallet_daily_statistics(mock_wallets))
