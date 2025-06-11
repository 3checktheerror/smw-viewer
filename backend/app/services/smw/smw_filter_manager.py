from typing import List, Tuple, Dict
import logging
from backend.app.core.config import settings
from backend.app.domain.models.wallet import WalletModel
from backend.app.services.smw.smw_filter_utils import SMWFilterUtils
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.time_utils import TimeUtils


class SMWFilterManager:

    @staticmethod
    def supply_smw_routine(
            wallets_data: List[Dict],
            out_db_name: str = settings.queue_db,
            out_collection_name: str = settings.queue_2,
    ) -> Tuple[List[WalletModel], List[WalletModel], List[WalletModel]]:
        mongo_client = MongoDBClient()

        initial_wallet_list = [WalletModel(**data) for data in wallets_data]
        logging.info(f"Received {len(initial_wallet_list)} wallets to process for date.")

        queue_db = settings.queue_db
        queue_collections = [settings.queue_1, settings.queue_2, settings.queue_3]
        existing_wallets = set()

        for collection in queue_collections:
            wallets_in_queue = mongo_client.find_many(
                collection_name=collection,
                db_name=queue_db,
                projection={'chain': 1, 'address': 1}
            )
            for wallet in wallets_in_queue:
                existing_wallets.add((wallet['chain'], wallet['address']))
        
        logging.info(f"Found {len(existing_wallets)} existing wallets in queues.")

        wallet_list = [
            wallet for wallet in initial_wallet_list 
            if (wallet.chain, wallet.address) not in existing_wallets
        ]

        logging.info(f"{len(initial_wallet_list) - len(wallet_list)} wallets already in queues, filtering them out.")
        logging.info(f"Processing {len(wallet_list)} new wallets.")

        final_wallets, low_stat_rejected, tx_behavior_rejected = SMWFilterUtils.start_filter(wallet_list, is_daily_fetch=True)

        if final_wallets:
            stored_date = TimeUtils.get_cur_date()
            updated_date = stored_date
            
            final_wallets_data = []
            for wallet in final_wallets:
                wallet_data = wallet.model_dump()
                wallet_data['updated_date'] = updated_date
                wallet_data['stored_date'] = stored_date
                final_wallets_data.append(wallet_data)

            mongo_client.insert_many(
                collection_name=out_collection_name,
                documents=final_wallets_data,
                db_name=out_db_name
            )

        return final_wallets, low_stat_rejected, tx_behavior_rejected