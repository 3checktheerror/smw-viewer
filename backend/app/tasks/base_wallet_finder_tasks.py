import logging
from typing import Dict, List
from backend.app.repositories.wallet_repository import WalletRepository
from backend.app.repositories.token_repository import HotTokenRepository
from backend.app.utils import MongoDBClient
from backend.app.core.config import settings
from backend.app.utils.log_utils import setup_logging
from backend.app.utils.time_utils import TimeUtils



class BaseWalletFinderTask:
    
    def __init__(self):
        self.mongodb_client = MongoDBClient()
        self.wallet_repository = WalletRepository()
        self.token_repository = HotTokenRepository()
    
    def run(self):
        try:
            logging.info("BaseWalletFinderTask started")
            chain_tokens = self.token_repository.get_previous_day_tokens()
            for chain, tokens in chain_tokens.items():
                if chain in ['bsc', 'solana', 'base']:
                    token_wallets = self.wallet_repository.get_token_wallets(tokens, chain)
                    all_wallets = set()
                    for wallets in token_wallets.values():
                        all_wallets.update(wallets)
                    self._save_daily_wallets(chain, list(all_wallets))
        
        except Exception as e:
            logging.error(f"Error in BaseWalletFinderTask.run: {e}")
    
    def _save_daily_wallets(self, chain: str, wallets: List[str]):
        cur_dt = TimeUtils.get_cur_date()
        
        documents = []
        for wallet in wallets:
            documents.append({
                'chain': chain,
                'address': wallet,
                'stored_date': cur_dt
            })
        
        if documents:
            self.mongodb_client.insert_many(
                settings.daily_wallet_collection,
                documents,
                db_name=settings.mongodb_wallet_db
            )



if __name__ == '__main__':
    setup_logging()
    task = BaseWalletFinderTask()
    task.run()