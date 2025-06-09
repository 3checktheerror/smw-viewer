import logging
import os
import csv
from typing import List, Dict
from backend.app.core.config import settings
from backend.app.domain.models.wallet import WalletModel
from backend.app.services.smw.smw_filter_manager import SMWFilterManager
from backend.app.services.smw.smw_statistic_manager import SMWStatisticManager
from backend.app.utils.log_utils import setup_logging
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.time_utils import TimeUtils


class SMWQueueHandlerTask:

    @staticmethod
    def _write_report(report_data: Dict[str, List[WalletModel]]):
        date_str = TimeUtils.get_cur_date()
        report_dir = os.path.join(os.path.dirname(__file__), 'report')
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"queue_change_report_{date_str}.csv")

        with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['category', 'address', 'chain'])

            for category, wallets in report_data.items():
                if wallets:
                    for wallet in wallets:
                        writer.writerow([category, wallet.address, wallet.chain])
        
        logging.info(f"Report generated at {report_path}")

    @staticmethod
    def daily_queue_shuffle_and_supply():
        in_date = TimeUtils.get_cur_date()
        mongo_client = MongoDBClient()

        q_db = settings.queue_db
        q1 = settings.queue_1
        q2 = settings.queue_2
        q3 = settings.queue_3

        report_data = {}

        # 1. Get initial state of all queues for the report
        q1_initial_data = mongo_client.find_many(collection_name=q1, db_name=q_db)
        report_data['initial_queue_1'] = [WalletModel(**w) for w in q1_initial_data]
        q2_initial_data = mongo_client.find_many(collection_name=q2, db_name=q_db)
        report_data['initial_queue_2'] = [WalletModel(**w) for w in q2_initial_data]
        q3_initial_data = mongo_client.find_many(collection_name=q3, db_name=q_db)
        report_data['initial_queue_3'] = [WalletModel(**w) for w in q3_initial_data]
        
        logging.info(f"Processing wallets for date: {in_date}")

        # 2. Eliminate from queue_3
        _, rejected_q3_low, rejected_q3_tx = SMWFilterManager.shuffle_smw_queue_routine(
            in_db_name=q_db, in_collection_name=q3, in_date=in_date, out_db_name=q_db
        )
        report_data['eliminated_from_queue_3'] = rejected_q3_low + rejected_q3_tx

        # 3. Demote from queue_2 to queue_3
        _, demoted_from_q2_low, demoted_from_q2_tx = SMWFilterManager.shuffle_smw_queue_routine(
            in_db_name=q_db, in_collection_name=q2, in_date=in_date, out_db_name=q_db
        )
        demoted_from_q2 = demoted_from_q2_low + demoted_from_q2_tx
        report_data['demoted_from_queue_2_to_3'] = demoted_from_q2
        if demoted_from_q2:
            demoted_docs = []
            for wallet in demoted_from_q2:
                doc = wallet.model_dump()
                doc['stored_date'] = in_date
                doc['updated_date'] = in_date
                demoted_docs.append(doc)
            mongo_client.insert_many(collection_name=q3, documents=demoted_docs, db_name=q_db)

        # 4. Demote from queue_1 to queue_2
        _, demoted_from_q1_low, demoted_from_q1_tx = SMWFilterManager.shuffle_smw_queue_routine(
            in_db_name=q_db, in_collection_name=q1, in_date=in_date, out_db_name=q_db
        )
        demoted_from_q1 = demoted_from_q1_low + demoted_from_q1_tx
        report_data['demoted_from_queue_1_to_2'] = demoted_from_q1
        if demoted_from_q1:
            demoted_docs = []
            for wallet in demoted_from_q1:
                doc = wallet.model_dump()
                doc['stored_date'] = in_date
                doc['updated_date'] = in_date
                demoted_docs.append(doc)
            mongo_client.insert_many(collection_name=q2, documents=demoted_docs, db_name=q_db)
            
        # 5. Promote from queue_2 to queue_1
        promoted_from_q2, _, _ = SMWFilterManager.shuffle_smw_queue_routine(
            in_db_name=q_db, in_collection_name=q2, in_date=in_date, 
            out_db_name=q_db, out_collection_name=q1
        )
        report_data['promoted_from_queue_2_to_1'] = promoted_from_q2
        if promoted_from_q2:
            delete_filter = {
                "stored_date": in_date,
                "$or": [{"chain": w.chain, "address": w.address} for w in promoted_from_q2]
            }
            mongo_client.delete_many(collection_name=q2, filter_dict=delete_filter, db_name=q_db)

        # 6. Promote from queue_3 to queue_2
        promoted_from_q3, _, _ = SMWFilterManager.shuffle_smw_queue_routine(
            in_db_name=q_db, in_collection_name=q3, in_date=in_date,
            out_db_name=q_db, out_collection_name=q2
        )
        report_data['promoted_from_queue_3_to_2'] = promoted_from_q3
        if promoted_from_q3:
            delete_filter = {
                "stored_date": in_date,
                "$or": [{"chain": w.chain, "address": w.address} for w in promoted_from_q3]
            }
            mongo_client.delete_many(collection_name=q3, filter_dict=delete_filter, db_name=q_db)

        # 7. Supply new wallets to queue_2
        SMWFilterManager.supply_smw_routine(in_date=in_date)

        # 8. Generate SMW buy statistics
        logging.info("Generating SMW buy statistics for queue_1 wallets...")
        q1_wallets_data = mongo_client.find_many(collection_name=q1, db_name=q_db)
        if q1_wallets_data:
            SMWStatisticManager.get_smw_avg_buy_statistics(wallet_data_list=q1_wallets_data)
        else:
            logging.info("Queue 1 is empty. Skipping statistics generation.")

        # 9. Generate report
        SMWQueueHandlerTask._write_report(report_data)

        logging.info("Daily queue shuffle and supply process finished.")


if __name__ == '__main__':
    setup_logging()
    SMWQueueHandlerTask.daily_queue_shuffle_and_supply()