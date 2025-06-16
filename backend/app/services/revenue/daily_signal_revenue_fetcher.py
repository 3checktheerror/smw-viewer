import logging
from backend.app.utils.log_utils import setup_logging
from typing import List, Optional
from datetime import datetime, timedelta
import json
import os
from backend.app.domain.models.revenue import RevenueModel, RevenueInfoModel
from backend.app.domain.models.token import TokenModel, TokenRevenueModel
from backend.app.services.revenue.kline_fetcher import KLineFetcher
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.time_utils import TimeUtils


class SignalRevenueStatisticsFetcher:
    @staticmethod
    def cleanup_old_kline_data():
        pass

    @staticmethod
    def get_signal_revenue_stats(duration: int, start_ts: int = 0, end_ts: int = 4116779249) -> List[RevenueModel]:
        """
        Fetches signal revenue statistics.
        """
        original_start_ts, original_end_ts = start_ts, end_ts
        start_ts = start_ts + 86400
        end_ts = end_ts + 86400

        # 1. Fetch data from MongoDB
        mongo_client = MongoDBClient()
        start_date_str = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d')
        end_date_str = datetime.fromtimestamp(end_ts).strftime('%Y-%m-%d')

        query = {"store_time": {"$gte": start_date_str, "$lte": end_date_str}}
        projection = {"chain": 1, "token": 1, "first_signal_time": 1, "store_time": 1}

        logging.info(f"Fetching signals from MongoDB with query: {query}")
        all_signals = mongo_client.find_many("debot_signal", query, projection=projection, db_name="graph")

        if not all_signals:
            logging.warning("No signals found in the specified date range.")
            return []

        # Group signals by store_time
        signals_by_store_time = {}
        for s in all_signals:
            signals_by_store_time.setdefault(s['store_time'], []).append(s)

        # 2. Filter signals based on first_signal_time
        filtered_signals_by_store_time = {}
        for store_time, daily_signals in signals_by_store_time.items():
            filtered_list = [
                s for s in daily_signals
                if original_start_ts <= s.get('first_signal_time', 0) <= original_end_ts
            ]
            if filtered_list:
                filtered_signals_by_store_time[store_time] = filtered_list

        if not filtered_signals_by_store_time:
            logging.warning("No signals passed the first_signal_time filter.")
            return []

        # 3. Fetch K-lines for filtered signals
        kline_fetcher = KLineFetcher()
        final_results = []

        for store_time, signals in filtered_signals_by_store_time.items():
            logging.info(f"Processing {len(signals)} signals for store_time: {store_time}")

            # De-duplicate signals by token, keeping the one with the earliest first_signal_time
            unique_signals_by_token = {}
            for s in signals:
                token = s['token']
                if token not in unique_signals_by_token or s['first_signal_time'] < unique_signals_by_token[token]['first_signal_time']:
                    unique_signals_by_token[token] = s

            signals = list(unique_signals_by_token.values())
            logging.info(f"Processing {len(signals)} unique signals for store_time: {store_time}")

            token_list = list({s['token']: TokenRevenueModel(address=s['token'], chain=s['chain'], first_signal_time=s['first_signal_time']) for s in signals}.values())

            klines_data = kline_fetcher.fetch_klines(
                token_list=token_list,
                duration=duration
            )

            # 4. Calculate signal_price and structure data
            info_list = []
            for signal in signals:
                chain = signal['chain']
                token_address = signal['token']
                first_signal_time = signal['first_signal_time']

                kline_list = klines_data.get(chain, {}).get(token_address)
                signal_price = None

                if kline_list:
                    # Find k-line point with time less than or equal to first_signal_time
                    # and closest to first_signal_time.
                    klines_before_signal = [k for k in kline_list if k['time'] <= first_signal_time]
                    if klines_before_signal:
                        # Find the latest k-line among those
                        closest_kline = max(klines_before_signal, key=lambda k: k['time'])
                        signal_price = closest_kline['open']

                    # Format kline data
                    formatted_kline = [
                        {"time": k["time"], "open": k["open"], "high": k["high"], "low": k["low"], "close": k["close"]}
                        for k in kline_list
                    ]
                else:
                    formatted_kline = []

                info_list.append(RevenueInfoModel(
                    token=token_address,
                    kline=formatted_kline,
                    signal_time=first_signal_time,
                    signal_price=signal_price
                ))

            date_dt = datetime.strptime(store_time, '%Y-%m-%d')
            date_timestamp = int(date_dt.timestamp()) - 86400

            final_results.append(RevenueModel(date=date_timestamp, info=info_list))

        # 5. Save results to a JSON file
        output_dir = os.path.dirname(__file__)
        output_filename = f"revenue_stats_{original_start_ts}_{original_end_ts}.json"
        output_path = os.path.join(output_dir, output_filename)

        serializable_results = [model.dict() for model in final_results]

        try:
            with open(output_path, 'w') as f:
                json.dump(serializable_results, f, indent=4)
            logging.info(f"Successfully saved revenue stats to {output_path}")
        except IOError as e:
            logging.error(f"Failed to save results to {output_path}: {e}")

        return final_results