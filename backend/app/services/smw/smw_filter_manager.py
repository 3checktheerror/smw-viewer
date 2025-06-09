from typing import List, Tuple
import logging
from backend.app.core.config import settings
from backend.app.domain.models.wallet import WalletModel
from backend.app.services.smw.smw_filter_utils import SMWFilterUtils
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.time_utils import TimeUtils


class SMWFilterManager:
    @staticmethod
    def shuffle_smw_queue_routine(
            in_db_name: str,
            in_collection_name: str,
            in_date: str,
            out_db_name: str,
            out_collection_name: str = None,
    ) -> Tuple[List[WalletModel], List[WalletModel], List[WalletModel]]:
        mongo_client = MongoDBClient()
        wallets_data = mongo_client.find_many(
            collection_name=in_collection_name, 
            db_name=in_db_name,
            filter_dict={'stored_date': in_date}
        )
        wallet_list = [WalletModel(**data) for data in wallets_data]

        final_wallets, low_stat_rejected, tx_behavior_rejected = SMWFilterUtils.start_filter(wallet_list)

        if final_wallets and out_collection_name is not None:
            updated_date = TimeUtils.get_cur_date()
            final_wallets_data = []
            for wallet in final_wallets:
                wallet_data = wallet.model_dump()
                wallet_data['updated_date'] = updated_date
                wallet_data['stored_date'] = in_date
                final_wallets_data.append(wallet_data)
                
            mongo_client.insert_many(
                collection_name=out_collection_name,
                documents=final_wallets_data,
                db_name=out_db_name
            )

        rejected_wallets = low_stat_rejected + tx_behavior_rejected
        if rejected_wallets:
            delete_filter = {
                "stored_date": in_date,
                "$or": [
                    {"chain": wallet.chain, "address": wallet.address}
                    for wallet in rejected_wallets
                ]
            }
            deleted_count = mongo_client.delete_many(
                collection_name=in_collection_name,
                filter_dict=delete_filter,
                db_name=in_db_name
            )
            logging.info(f"Deleted {deleted_count} rejected wallets from {in_collection_name}.")

        return final_wallets, low_stat_rejected, tx_behavior_rejected


    @staticmethod
    def supply_smw_routine(
            in_date: str = TimeUtils.get_cur_date(),
            in_db_name: str = settings.mongodb_wallet_db,
            in_collection_name: str = settings.daily_wallet_collection,
            out_db_name: str = settings.queue_db,
            out_collection_name: str = settings.queue_2,
    ) -> Tuple[List[WalletModel], List[WalletModel], List[WalletModel]]:
        mongo_client = MongoDBClient()
        wallets_data = mongo_client.find_many(
            collection_name=in_collection_name,
            db_name=in_db_name,
            filter_dict={'date': in_date},
            batch_size=20000
        )

        initial_wallet_list = [WalletModel(**data) for data in wallets_data]
        logging.info(f"Fetched {len(initial_wallet_list)} wallets from {in_collection_name} for date {in_date}.")

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

        final_wallets, low_stat_rejected, tx_behavior_rejected = SMWFilterUtils.start_filter(wallet_list)

        if final_wallets:
            stored_date = in_date
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