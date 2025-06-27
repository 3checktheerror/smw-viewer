import json
import logging
from sys import int_info
from typing import List, Dict

from backend.app.services.revenue.daily_signal_revenue_fetcher import SignalRevenueStatisticsFetcher
from backend.app.services.revenue.profit_loss_strategy import ProfitLossStrategy
from backend.app.utils.log_utils import setup_logging
from backend.app.utils.thread_pool import ThreadPoolManager
from backend.app.utils.time_utils import TimeUtils


class SignalRevenueCalculator:

    @staticmethod
    def _calculate_profit_for_signal(signal_info, initial_usd, tp_rules, sl_rules, duration):
        """
        Helper function to calculate profit for a single signal and return it with the signal info.
        This ensures that the result is always associated with the correct signal,
        avoiding potential mismatches when processing in parallel.
        """
        result = ProfitLossStrategy.get_single_token_profit(
            initial_used=initial_usd,
            signal_price=signal_info.signal_price,
            signal_ts=signal_info.signal_time,
            k_line_data=signal_info.kline,
            tp_rules=tp_rules,
            sl_rules=sl_rules,
            duration=duration
        )
        return signal_info, result

    @staticmethod
    def calculate_signal_revenue(initial_usd: float,
                                 duration: int,
                                 tp_rules: List[Dict[str, float]],
                                 sl_rules: List[Dict[str, float]],
                                 start_ts: int = 0,
                                 end_ts: int = 4116779249,
                                 whitelist_tokens: List[str] = None,
                                 blacklist_tokens: List[str] = None,
                                 progress_callback=None):
        """
        Calculates the profit and loss for signals within a given time range based on provided strategies.

        Args:
            initial_usd (float): The total initial investment in USD.
            duration (int): The maximum duration for the strategy to be active for each signal.
            tp_rules (List[Dict[str, float]]): Take-profit strategy rules.
            sl_rules (List[Dict[str, float]]): Stop-loss strategy rules.
            start_ts (int, optional): The start timestamp for fetching signals. Defaults to 0.
            end_ts (int, optional): The end timestamp for fetching signals. Defaults to a far-future timestamp.
            whitelist_tokens (List[str], optional): A list of token addresses to include. Defaults to None.
            blacklist_tokens (List[str], optional): A list of token addresses to exclude. Defaults to None.
            progress_callback (callable, optional): A callback function to update progress. Defaults to None.

        Returns:
            dict: A dictionary containing the results.
        """
        # 1. Fetch signal data
        revenue_models = SignalRevenueStatisticsFetcher.get_signal_revenue_stats(
            duration=duration,
            start_ts=start_ts,
            end_ts=end_ts,
            whitelist_tokens=whitelist_tokens,
            blacklist_tokens=blacklist_tokens,
            progress_callback=progress_callback
        )

        if not revenue_models:
            logging.error("No revenue models found for the given period.")
            return None

        # 2. Flatten all signals and filter out those with invalid prices
        all_signals = []
        for model in revenue_models:
            for signal_info in model.info:
                if signal_info.signal_price is not None and signal_info.signal_price > 0:
                    all_signals.append(signal_info)
                else:
                    logging.warning(
                        f"Skipping signal for token {signal_info.token} due to invalid signal price: {signal_info.signal_price}")

        if not all_signals:
            logging.error("No valid signals found in the revenue models.")
            return None

        # 3. Prepare arguments for parallel processing
        tasks_args = [
            (
                signal,
                initial_usd,
                tp_rules,
                sl_rules,
                duration
            )
            for signal in all_signals
        ]

        # 4. Execute profit calculation in parallel using ThreadPoolManager
        with ThreadPoolManager(max_workers=50) as manager:
            results = manager.execute_tasks_and_wait(
                func=SignalRevenueCalculator._calculate_profit_for_signal,
                tasks_args=tasks_args,
                show_log=False
            )

        # 5. Process and aggregate results
        token_results = []
        sum_revenue = 0.0

        for signal_info, result in results:
            if result:
                total_revenue, initial_cost, roi, trigger_events = result
                sum_revenue += total_revenue

                token_results.append({
                    "token": signal_info.token,
                    "signal_time": signal_info.signal_time,
                    "total_revenue": total_revenue,
                    "initial_cost": initial_cost,
                    "final_roi": roi,
                    "trigger_event": trigger_events,
                    "dog": signal_info.dog,
                    "max_price_ts": signal_info.max_price_ts,
                    "max_increase": signal_info.max_increase
                })

        # 6. Calculate final summary
        inward_usd = initial_usd * len(all_signals)
        sum_roi = (sum_revenue - inward_usd) / inward_usd if inward_usd > 0 else 0.0

        return {
            "token_results": token_results,
            "sum_revenue": sum_revenue,
            "sum_initial_usd": inward_usd,
            "sum_roi": sum_roi
        }



if __name__ == '__main__':
    setup_logging()
    signal_revenue_calculator = SignalRevenueCalculator()
    tp_rules_input = [
        {'z': 0.3, 's': 0.3},  # 上涨 10% 时, 卖出 30%
        {'z': 0.5, 's': 1.0},  # 上涨 25% 时, 再卖出剩余部分的 50%
    ]

    # 止损 (Stop Loss) 策略规则
    # 'd' 是下跌目标价与初始价格的比值, 's' 是卖出持有代币的比例
    sl_rules_input = [
        {'d': 0.60, 's': 0.2},  # 价格跌至初始价的 90% 时, 卖出 50%
        {'d': 0.30, 's': 1.0},  # 价格跌至初始价的 80% 时, 卖出剩余的 100%
    ]

    res = signal_revenue_calculator.calculate_signal_revenue(
        initial_usd=1000,
        duration=7200,
        tp_rules=tp_rules_input,
        sl_rules = sl_rules_input,
        start_ts=TimeUtils.get_prev_utc_0_hour_ts(),
        whitelist_tokens=['0x6B175474E89094C44Da98b954EedeAC495271d0F'],
    )

    print(json.dumps(res, indent=2))