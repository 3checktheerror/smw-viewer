import logging
from typing import Dict, List
from backend.app.repositories.wallet_repository import WalletRepository
from backend.app.repositories.token_repository import HotTokenRepository
from backend.app.utils.log_utils import setup_logging
from backend.app.utils.thread_pool import ThreadPoolManager



class BaseWalletFinderTask:
    
    def __init__(self):
        self.wallet_repository = WalletRepository()
        self.token_repository = HotTokenRepository()

    def _get_wallets_for_chain(self, chain: str, tokens: List[str]) -> List[Dict]:
        logging.info(f"Fetching wallets for chain {chain} with {len(tokens)} tokens")
        token_wallets = self.wallet_repository.get_token_wallets(tokens, chain)
        if not token_wallets:
            return []

        all_wallets = set()
        for wallets in token_wallets.values():
            all_wallets.update(wallets)

        wallet_docs = []
        for wallet in all_wallets:
            wallet_docs.append(
                {
                    "chain": chain,
                    "address": wallet,
                }
            )
        logging.info(f"Found {len(wallet_docs)} wallets for chain {chain}")
        return wallet_docs

    def run(self) -> List[Dict]:
        try:
            logging.info("BaseWalletFinderTask started")

            chain_tokens = self.token_repository.get_previous_day_tokens()

            tasks_args = []
            for chain, tokens in chain_tokens.items():
                if chain in ["bsc", "solana", "base"] and tokens:
                    tasks_args.append((chain, tokens))

            if not tasks_args:
                logging.info("No tasks to run. BaseWalletFinderTask finished.")
                return []

            all_wallet_docs = []
            with ThreadPoolManager(max_workers=len(tasks_args)) as manager:
                results = manager.execute_tasks_and_wait(
                    self._get_wallets_for_chain, tasks_args, show_log=True
                )

            for result_list in results:
                if result_list:
                    all_wallet_docs.extend(result_list)

            logging.info(
                f"BaseWalletFinderTask finished. Found {len(all_wallet_docs)} wallets in total."
            )
            return all_wallet_docs

        except Exception as e:
            logging.error(f"Error in BaseWalletFinderTask.run: {e}")
            return []

if __name__ == '__main__':
    setup_logging()
    task = BaseWalletFinderTask()
    task.run()