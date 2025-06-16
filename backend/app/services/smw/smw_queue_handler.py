import logging
import os
import csv
import re
from typing import List, Dict
from backend.app.core.config import settings
from backend.app.domain.models.wallet import WalletModel
from backend.app.services.smw.smw_filter_manager import SMWFilterManager
from backend.app.services.smw.smw_filter_utils import SMWFilterUtils
from backend.app.services.smw.smw_statistic_manager import SMWStatisticManager
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.time_utils import TimeUtils
from collections import defaultdict


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
    def cleanup():
        mongo_client = MongoDBClient()
        three_days_ago = TimeUtils.get_3_days_ago_date()
        filter_dict = {"stored_date": {"$lt": three_days_ago}}

        logging.info("Cleaning up old documents...")

        # Cleanup honeypot in token db
        deleted_count_honeypot = mongo_client.delete_many(
            collection_name='honeypot',
            db_name='token',
            filter_dict=filter_dict
        )
        logging.info(f"Deleted {deleted_count_honeypot} documents from honeypot older than {three_days_ago}.")

        deleted_count_honeypot = mongo_client.delete_many(
            collection_name='onchain_token',
            db_name='token',
            filter_dict=filter_dict
        )
        logging.info(f"Deleted {deleted_count_honeypot} documents from onchain_token older than {three_days_ago}.")

        deleted_count_honeypot = mongo_client.delete_many(
            collection_name='rank_token',
            db_name='token',
            filter_dict=filter_dict
        )
        logging.info(f"Deleted {deleted_count_honeypot} documents from rank_token older than {three_days_ago}.")

        # Cleanup old report files
        logging.info("Cleaning up old report files...")
        report_dir = os.path.join(os.path.dirname(__file__), 'report')
        if not os.path.isdir(report_dir):
            logging.info("Report directory does not exist, skipping cleanup.")
            return

        seven_days_ago = TimeUtils.get_7_days_ago_date()
        file_pattern = re.compile(r"(?:queue_change_report_|daily_avg_buy_)(\d{4}-\d{2}-\d{2})\.csv")

        for filename in os.listdir(report_dir):
            match = file_pattern.match(filename)
            if match:
                date_str = match.group(1)
                if date_str < seven_days_ago:
                    file_path = os.path.join(report_dir, filename)
                    try:
                        os.remove(file_path)
                        logging.info(f"Deleted old report file: {file_path}")
                    except OSError as e:
                        logging.error(f"Error deleting file {file_path}: {e}")


    @staticmethod
    def daily_queue_shuffle_and_supply(new_wallets: List[Dict]):
        in_date = TimeUtils.get_cur_date()
        mongo_client = MongoDBClient()

        q_db = settings.queue_db
        q1_name, q2_name, q3_name = settings.queue_1, settings.queue_2, settings.queue_3
        queues = [q1_name, q2_name, q3_name]

        report_data = {}
        logging.info(f"SMW Queue processing started for date: {in_date}")

        # 1. Get initial state of all queues for reporting and processing
        initial_wallets_docs = {q_name: mongo_client.find_many(collection_name=q_name, db_name=q_db) for q_name in queues}

        report_data['initial_queue_1'] = [WalletModel(**w) for w in initial_wallets_docs[q1_name]]
        report_data['initial_queue_2'] = [WalletModel(**w) for w in initial_wallets_docs[q2_name]]
        report_data['initial_queue_3'] = [WalletModel(**w) for w in initial_wallets_docs[q3_name]]

        q1_wallets = [WalletModel(**w) for w in initial_wallets_docs[q1_name]]
        q2_wallets = [WalletModel(**w) for w in initial_wallets_docs[q2_name]]
        q3_wallets = [WalletModel(**w) for w in initial_wallets_docs[q3_name]]

        wallets_to_add = defaultdict(list)
        wallets_to_delete = defaultdict(list)

        # 2. Process Q1: Demotion for rejected wallets
        logging.info(f"Processing {len(q1_wallets)} wallets from queue 1...")
        if q1_wallets:
            _, rejected_q1_low, rejected_q1_tx = SMWFilterUtils.start_filter(q1_wallets, is_daily_fetch=False)
            demoted_from_q1 = rejected_q1_low + rejected_q1_tx
            report_data['demoted_from_queue_1_to_2'] = demoted_from_q1
            wallets_to_add[q2_name].extend(demoted_from_q1)
            wallets_to_delete[q1_name].extend(demoted_from_q1)

        # 3. Process Q2: Promotion for final, Demotion for rejected
        logging.info(f"Processing {len(q2_wallets)} wallets from queue 2...")
        if q2_wallets:
            promoted_from_q2, rejected_q2_low, rejected_q2_tx = SMWFilterUtils.start_filter(q2_wallets, is_daily_fetch=False)
            demoted_from_q2 = rejected_q2_low + rejected_q2_tx
            report_data['promoted_from_queue_2_to_1'] = promoted_from_q2
            report_data['demoted_from_queue_2_to_3'] = demoted_from_q2
            wallets_to_add[q1_name].extend(promoted_from_q2)
            wallets_to_add[q3_name].extend(demoted_from_q2)
            wallets_to_delete[q2_name].extend(q2_wallets)

        # 4. Process Q3: Promotion for final, Elimination for rejected
        logging.info(f"Processing {len(q3_wallets)} wallets from queue 3...")
        if q3_wallets:
            promoted_from_q3, rejected_q3_low, rejected_q3_tx = SMWFilterUtils.start_filter(q3_wallets, is_daily_fetch=False)
            eliminated_from_q3 = rejected_q3_low + rejected_q3_tx
            report_data['promoted_from_queue_3_to_2'] = promoted_from_q3
            report_data['eliminated_from_queue_3'] = eliminated_from_q3
            wallets_to_add[q2_name].extend(promoted_from_q3)
            wallets_to_delete[q3_name].extend(q3_wallets)

        # 5. Apply database changes
        logging.info("Applying database changes...")
        for q_name, wallets in wallets_to_delete.items():
            if wallets:
                delete_filter = {
                    "$or": [{"chain": w.chain, "address": w.address} for w in wallets]
                }
                deleted_count = mongo_client.delete_many(collection_name=q_name, filter_dict=delete_filter, db_name=q_db)
                logging.info(f"Deleted {deleted_count} wallets from {q_name}.")

        for q_name, wallets in wallets_to_add.items():
            if wallets:
                # De-duplicate wallets before insertion
                unique_wallets_map = {(w.address, w.chain): w for w in wallets}
                unique_wallets = list(unique_wallets_map.values())

                docs = []
                for wallet in unique_wallets:
                    doc = wallet.model_dump()
                    doc['updated_date'] = in_date
                    if not wallet.stored_date:
                        doc['stored_date'] = in_date
                    docs.append(doc)

                mongo_client.insert_many(collection_name=q_name, documents=docs, db_name=q_db)
                logging.info(f"Inserted {len(docs)} wallets into {q_name}.")

        # 6. Supply new wallets to queue_2
        logging.info("Supplying new wallets to queue_2...")
        if new_wallets:
            SMWFilterManager.supply_smw_routine(wallets_data=new_wallets)
        else:
            logging.info("No new wallets to supply.")

        # 7. Generate SMW buy statistics for the new state of queue_1
        logging.info("Generating SMW buy statistics for queue_1...")
        q1_updated_data = mongo_client.find_many(collection_name=q1_name, db_name=q_db)
        if q1_updated_data:
            SMWStatisticManager.get_smw_avg_buy_statistics(wallet_data_list=q1_updated_data)
        else:
            logging.info("Queue 1 is empty. Skipping statistics generation.")

        # 8. Generate and write the final report
        SMWQueueHandlerTask._write_report(report_data)

        logging.info("Daily queue shuffle and supply process finished.")

