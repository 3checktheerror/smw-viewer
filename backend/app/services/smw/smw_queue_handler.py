import logging
import os
import csv
import re
from typing import List, Dict
from backend.app.core.config import settings
from backend.app.domain.models.wallet import WalletModel
from backend.app.services.smw.smw_filter_manager import SMWFilterManager
from backend.app.services.smw.smw_filter_utils import SMWFilterUtils
from backend.app.services.smw.smw_incremental_manager import SMWIncrementalManager
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
        five_days_ago = TimeUtils.get_5_days_ago_bg_date()
        filter_dict = {"stored_date": {"$lt": five_days_ago}}

        logging.info("Cleaning up old documents...")

        # Cleanup honeypot in token db
        deleted_count_honeypot = mongo_client.delete_many(
            collection_name='honeypot',
            db_name='token',
            filter_dict=filter_dict
        )
        logging.info(f"Deleted {deleted_count_honeypot} documents from honeypot older than {five_days_ago}.")

        deleted_count_honeypot = mongo_client.delete_many(
            collection_name='onchain_token',
            db_name='token',
            filter_dict=filter_dict
        )
        logging.info(f"Deleted {deleted_count_honeypot} documents from onchain_token older than {five_days_ago}.")

        deleted_count_honeypot = mongo_client.delete_many(
            collection_name='rank_token',
            db_name='token',
            filter_dict=filter_dict
        )
        logging.info(f"Deleted {deleted_count_honeypot} documents from rank_token older than {five_days_ago}.")

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

        # 0. 从 history.smw_history 中筛除历史钱包
        if new_wallets:
            history_wallets = mongo_client.find_many(
                collection_name="smw_history",
                filter_dict={},
                projection={"address": 1, "chain": 1},
                db_name="history"
            )

            whitelist_set = {
                (rec.get("address"), rec.get("chain"))
                for rec in history_wallets
                if rec.get("address") and rec.get("chain")
            }

            if whitelist_set:
                original_len = len(new_wallets)
                new_wallets[:] = [
                    w for w in new_wallets
                    if (w.get("address"), w.get("chain")) not in whitelist_set
                ]
                removed_cnt = original_len - len(new_wallets)
                if removed_cnt:
                    logging.info(f"Filtered out {removed_cnt} wallets from history.")

        # 1. Get initial state of all queues for reporting and processing
        initial_wallets_docs = {q_name: mongo_client.find_many(collection_name=q_name, db_name=q_db) for q_name in queues}

        # Removed initial_queue_* categories as per updated reporting requirements.

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
            report_data['变动：Top -> Mid'] = demoted_from_q1
            wallets_to_add[q2_name].extend(demoted_from_q1)
            wallets_to_delete[q1_name].extend(demoted_from_q1)

        # 3. Process Q2: Promotion for final, Demotion for rejected
        logging.info(f"Processing {len(q2_wallets)} wallets from queue 2...")
        if q2_wallets:
            promoted_from_q2, rejected_q2_low, rejected_q2_tx = SMWFilterUtils.start_filter(q2_wallets, is_daily_fetch=False)
            demoted_from_q2 = rejected_q2_low + rejected_q2_tx
            report_data['变动：Mid -> Top'] = promoted_from_q2
            report_data['变动：Mid -> Bottom'] = demoted_from_q2
            wallets_to_add[q1_name].extend(promoted_from_q2)
            wallets_to_add[q3_name].extend(demoted_from_q2)
            wallets_to_delete[q2_name].extend(q2_wallets)

        # 4. Process Q3: Promotion for final, Elimination for rejected
        logging.info(f"Processing {len(q3_wallets)} wallets from queue 3...")
        if q3_wallets:
            promoted_from_q3, rejected_q3_low, rejected_q3_tx = SMWFilterUtils.start_filter(q3_wallets, is_daily_fetch=False)
            eliminated_from_q3 = rejected_q3_low + rejected_q3_tx
            report_data['变动：Bottom -> Mid'] = promoted_from_q3
            report_data['变动：Bottom -> '] = eliminated_from_q3
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
            final_wallets, _, _ = SMWFilterManager.supply_smw_routine(wallets_data=new_wallets)
            report_data['增量'] = final_wallets
        else:
            logging.info("No new wallets to supply.")
            report_data['增量'] = []

        # 7. Generate SMW buy statistics for the new state of queue_1
        logging.info("Generating SMW buy statistics for queue_1...")
        q1_updated_data = mongo_client.find_many(collection_name=q1_name, db_name=q_db)
        # if q1_updated_data:
        #     SMWStatisticManager.get_smw_avg_buy_statistics(wallet_data_list=q1_updated_data)
        # else:
        #     logging.info("Queue 1 is empty. Skipping statistics generation.")

        # 8. Capture the final state of each queue for reporting
        q2_updated_data = mongo_client.find_many(collection_name=q2_name, db_name=q_db)
        q3_updated_data = mongo_client.find_many(collection_name=q3_name, db_name=q_db)
        report_data['结果：Top-队列'] = [WalletModel(**w) for w in q1_updated_data]
        report_data['结果：Mid-队列'] = [WalletModel(**w) for w in q2_updated_data]
        report_data['结果：Bottom-队列'] = [WalletModel(**w) for w in q3_updated_data]

        # 9. Generate and write the final report
        SMWQueueHandlerTask._write_report(report_data)

        # 10. Generate incremental wallets
        SMWIncrementalManager.generate_incremental_wallets()

        # 11. 根据最新过滤结果更新 history.smw_history 的 out_tag
        logging.info("Updating out_tag for history wallets...")

        history_records = mongo_client.find_many(
            collection_name="smw_history",
            filter_dict={"out_tag": {"$ne": 4}},
            projection={"address": 1, "chain": 1},
            db_name="history"
        )

        if history_records:
            history_wallet_models = [
                WalletModel(chain=rec.get("chain"), address=rec.get("address"))
                for rec in history_records
                if rec.get("address") and rec.get("chain")
            ]

            if history_wallet_models:
                res_wallets, low_stat_wallets, tx_bad_wallets = SMWFilterUtils.start_filter(
                    history_wallet_models, is_daily_fetch=False
                )

                def _update_tag(wallet_list: List[WalletModel], tag: int):
                    if not wallet_list:
                        return 0
                    filter_cond = {
                        "$or": [
                            {"address": w.address, "chain": w.chain}
                            for w in wallet_list
                        ]
                    }
                    return mongo_client.update_many(
                        collection_name="smw_history",
                        filter_dict=filter_cond,
                        update_dict={"out_tag": tag},
                        db_name="history"
                    )

                updated_low = _update_tag(low_stat_wallets, 2)
                updated_tx = _update_tag(tx_bad_wallets, 3)
                updated_res = _update_tag(res_wallets, 1)

                logging.info(
                    "History wallets out_tag updated. low_statistic=%s, bad_tx=%s, normal=%s",
                    updated_low, updated_tx, updated_res
                )
        else:
            logging.info("No history wallets found for out_tag update.")

        logging.info("Daily queue shuffle and supply process finished.")

