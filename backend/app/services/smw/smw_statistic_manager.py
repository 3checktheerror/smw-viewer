import logging
import os
import threading
from collections import defaultdict
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from backend.app.services.smw.utils.debot_utils import DebotAPIUtils
from backend.app.utils.time_utils import TimeUtils


class SMWStatisticManager:

    @staticmethod
    def get_smw_avg_buy_statistics(wallet_data_list: List[Dict]):
        logging.info("开始修正稳定币交易数据...")
        updated_count = 0
        error_count = 0
        updated_addresses = []
        error_addresses = []
        address_lock = threading.Lock()

        wallets_by_chain = defaultdict(list)
        for wallet_data in wallet_data_list:
            if 'chain' in wallet_data:
                wallets_by_chain[wallet_data['chain']].append(wallet_data)

        filtered_data = []

        for chain, raw_data in wallets_by_chain.items():
            logging.info(f"正在处理链 {chain} 的 {len(raw_data)} 个钱包...")

            def process_record(record: Dict) -> Dict:
                nonlocal updated_count, error_count, updated_addresses, error_addresses
                addr = record.get('address', '未知地址')
                try:
                    if not record.get('tx_stable_coin', False):
                        return record

                    origin_avg = record.get('avg_buy_volume_7d', 0)
                    tokens = record.get('7D_token_address', [])

                    stats = DebotAPIUtils.get_wallet_avg_buy(
                        wallet=record['address'],
                        chain=chain,
                        tokens=set(tokens)
                    )

                    stable_vol = stats['stable_buy_volumes_sum']
                    stable_times = stats['stable_buy_times_sum']
                    total_buy_times = stats['total_buy_times']

                    if (total_buy_times - stable_times) <= 0:
                        logging.warning(f"无效分母 {record['address']}: total={total_buy_times} stable={stable_times}")
                        return record

                    new_avg = (origin_avg * total_buy_times - stable_vol) / (total_buy_times - stable_times)

                    with address_lock:
                        updated_addresses.append(addr)
                    updated_count += 1
                    new_record = record.copy()
                    new_record['avg_buy_volume_7d'] = round(max(new_avg, 0), 4)
                    return new_record

                except Exception as e:
                    with address_lock:
                        error_addresses.append(addr)
                    error_count += 1
                    logging.error(f"修正失败 {addr}: {str(e)}")
                    return record

            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(process_record, r) for r in raw_data]
                for f in as_completed(futures):
                    filtered_data.append(f.result())

        logging.info(
            f"稳定币修正完成:\n"
            f"更新地址列表({updated_count}条):\n{updated_addresses}\n"
            f"失败地址列表({error_count}条):\n{error_addresses}"
        )

        def get_volume_group(avg_buy: float) -> str:
            """获取交易量分组标签 (修正版)"""
            try:
                avg = float(avg_buy)
                if avg < 300:
                    return "< 300"
                elif 300 <= avg < 400:
                    return "300-400"
                elif 400 <= avg < 500:
                    return "400-500"
                elif 500 <= avg < 1000:
                    return "500-1000"
                elif 1000 <= avg < 2000:
                    return "1000-2000"
                elif avg >= 2000:
                    return "2000+"
                else:
                    return "其他"
            except (TypeError, ValueError):
                return "Invalid"

        if not filtered_data:
            logging.info("没有数据可生成统计报告。")
            return
            
        df = pd.DataFrame([{
            'Wallet': w['address'],
            'avg_buy_volume_7d': w.get('avg_buy_volume_7d', 0),
            'Group': get_volume_group(w.get('avg_buy_volume_7d', 0))
        } for w in filtered_data])

        stats_df = df.groupby('Group').agg(
            wallet_count=('Wallet', 'count'),
            avg_volume=('avg_buy_volume_7d', lambda x: round(x.mean(), 2))
        ).reset_index()

        report_dir = os.path.join(os.path.dirname(__file__), 'report')
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"daily_avg_buy_{TimeUtils.get_cur_date()}.csv")
        stats_df.to_csv(report_path, index=False, encoding='utf-8')
        logging.info(f"平均购买统计数据已保存至 {report_path}")