import logging
import time
from datetime import datetime
from decimal import Decimal, getcontext
import random
import json

from backend.app.utils.log_utils import setup_logging


class ProfitLossStrategy:
    @staticmethod
    def get_single_token_profit(
            initial_used: float,
            signal_price: float,
            signal_ts: int,
            k_line_data: list[dict],
            tp_rules: list[dict],
            sl_rules: list[dict],
            duration: int
    ):
        """
        计算在给定的止盈止损策略下，单个DEX信号的收益率 (使用Decimal确保精度)。

        Args:
            initial_used (float): 初始美金,
            signal_price (float): 告警时的价格 (入场价格).
            signal_ts (int): 告警时的时间戳.
            k_line_data (list[dict]): 秒级K线数据列表.
                每个元素格式: {'time': int, 'open': float, 'high': float, 'low': float, 'close': float}.
            tp_rules (list[dict]): 止盈策略列表.
                每个元素格式: {'z': float, 's': float}. z是上涨幅度, s是卖出比例.
            sl_rules (list[dict]): 止损策略列表.
                每个元素格式: {'d': float, 's': float}. d是下跌目标价与p1的比值, s是卖出比例.
            duration (int): 策略生效的最大持续时间（秒）.

        Returns:
            total_revenue (float): 收益 (美金),
            initial_cost (float): 总投入 (美金),
            final_roi (float): 收益率.
        """
        # --- 设置Decimal精度 ---
        # 30位精度对于绝大多数金融计算都已足够
        getcontext().prec = 30

        # --- 1. 初始化状态 (将所有输入转换为Decimal以保证精度) ---
        # 使用 str() 进行中转，是避免二进制浮点数表示误差的最佳实践
        try:
            initial_used_dec = Decimal(str(initial_used))
            signal_price_dec = Decimal(str(signal_price))

            # 初始化持有量和成本
            current_holdings = initial_used_dec / signal_price_dec if signal_price_dec != 0 else Decimal('0')
            initial_cost_dec = initial_used_dec
            total_revenue_dec = Decimal('0.0')

            # 转换止盈规则
            active_tp_rules = [
                {
                    'z': Decimal(str(rule['z'])),
                    's': Decimal(str(rule['s'])),
                    'triggered': False,
                    'target_price': signal_price_dec * (Decimal('1') + Decimal(str(rule['z'])))
                }
                for rule in tp_rules
            ]

            # 转换止损规则
            active_sl_rules = [
                {
                    'd': Decimal(str(rule['d'])),
                    's': Decimal(str(rule['s'])),
                    'triggered': False,
                    'target_price': signal_price_dec * Decimal(str(rule['d']))
                }
                for rule in sl_rules
            ]

            # 转换K线数据
            k_line_data_dec = [
                {
                    'time': candle['time'],
                    'open': Decimal(str(candle['open'])),
                    'high': Decimal(str(candle['high'])),
                    'low': Decimal(str(candle['low'])),
                    'close': Decimal(str(candle['close']))
                } for candle in k_line_data
            ]

            k_line_data_dec = [candle for candle in k_line_data_dec if candle['time'] >= signal_ts]
            k_line_data_dec.sort(key=lambda x: x['time'])


        except Exception as e:
            logging.info(f"Error during Decimal conversion: {e}")
            # 如果转换失败，返回零值避免崩溃
            return 0.0, float(initial_used), 0.0

        active_tp_rules.sort(key=lambda x: x['target_price'])
        active_sl_rules.sort(key=lambda x: x['target_price'], reverse=True)

        logging.info("--- 模拟开始 ---")
        # 使用 to_eng_string() 避免科学计数法，并用 format 控制小数位数
        logging.info(f"入场价格: {signal_price_dec:.8f}, 初始成本: ${initial_cost_dec:.4f}")

        # --- 2. 遍历K线数据进行模拟 ---
        simulation_end_time = signal_ts + duration
        for candle in k_line_data_dec:
            if candle['time'] > simulation_end_time:
                logging.info(f"时间达到 {duration} 秒上限，结束。")
                break

            # 使用一个极小值来判断持仓是否耗尽
            if current_holdings <= Decimal('1e-18'):
                logging.info("所有代币已卖出，结束。")
                break

            candle_high = candle['high']
            candle_low = candle['low']

            def process_triggers(rules_to_check: list[dict], is_stop_loss: bool):
                nonlocal current_holdings, total_revenue_dec
                for rule in rules_to_check:
                    if not rule['triggered']:
                        triggered = False
                        # 检查是否满足触发条件 (所有比较均在Decimal对象间进行)
                        if is_stop_loss and candle_low <= rule['target_price']:
                            triggered = True
                        elif not is_stop_loss and candle_high >= rule['target_price']:
                            triggered = True

                        if triggered:
                            # 止损按设定的目标价卖出，止盈按当时K线的最高价卖出
                            execution_price = rule['target_price'] if is_stop_loss else candle_high

                            sell_proportion = rule['s']
                            sell_amount = current_holdings * sell_proportion
                            revenue_this_trade = sell_amount * execution_price

                            total_revenue_dec += revenue_this_trade
                            current_holdings -= sell_amount
                            rule['triggered'] = True

                            event = "止损" if is_stop_loss else "止盈"
                            rule_detail = ""
                            if 'd' in rule:  # Stop loss rule
                                rule_detail = f" (d={rule['d']}, s={rule['s']})"
                            elif 'z' in rule:  # Take profit rule
                                rule_detail = f" (z={rule['z']}, s={rule['s']})"

                            logging.info(f"时间: {candle['time']}, 价格范围触及目标 {rule['target_price']:.8f}, 触发 {event}{rule_detail}!")
                            logging.info(
                                f"  在价格 {execution_price:.8f} 卖出 {sell_amount:.8f} 个币, 获得收入 ${revenue_this_trade:.4f}")
                            logging.info(f"  剩余持仓: {current_holdings:.8f} 个币, 累计收入: ${total_revenue_dec:.4f}")

            # 检查触发顺序：先检查是否需要止损，再检查是否能够止盈
            # 如果是阳线 (收盘 >= 开盘)，价格先下跌后上涨，所以先检查止损
            if candle['close'] >= candle['open']:
                process_triggers(active_sl_rules, is_stop_loss=True)
                process_triggers(active_tp_rules, is_stop_loss=False)
            # 如果是阴线 (收盘 < 开盘)，价格先上涨后下跌，所以先检查止盈
            else:
                process_triggers(active_tp_rules, is_stop_loss=False)
                process_triggers(active_sl_rules, is_stop_loss=True)

        logging.info("--- 模拟结束 ---")

        # 如果最后仍有持仓，按最后一根K线的收盘价计算剩余价值
        if current_holdings > Decimal('1e-18') and k_line_data_dec:
            last_close_price = k_line_data_dec[-1]['close']
            remaining_value = current_holdings * last_close_price
            total_revenue_dec += remaining_value
            logging.info(
                f"模拟结束时仍有持仓 {current_holdings:.8f} 个币, 按最后收盘价 {last_close_price:.8f} 计算剩余价值 ${remaining_value:.4f}")
            logging.info(f"最终总收入: ${total_revenue_dec:.4f}")

        # --- 3. 计算最终收益率 ---
        if initial_cost_dec == 0:
            final_roi_dec = Decimal('0.0')
        else:
            # 收益 = 总收入 - 初始成本
            profit = total_revenue_dec - initial_cost_dec
            final_roi_dec = profit / initial_cost_dec

        # 将Decimal结果转换为float返回，保持接口一致性
        return float(total_revenue_dec), float(initial_cost_dec), float(final_roi_dec)


def mock_data():
    initial_used_input = 1000.0

    # 信号触发价格 (告警价格)
    signal_price_input = 0.0002746159131

    # 信号触发时间戳 (例如：10分钟前)
    signal_ts_input = 1750111084

    # 策略生效的最大持续时间 (例如：1小时)
    duration_input = 7200

    # 生成K线数据 (在策略有效期前后各增加5分钟的缓冲数据)
    with open('data.json', 'r') as f:
        data = json.load(f)
        k_line_data_input = data['data']['list']

    # 止盈 (Take Profit) 策略规则
    # 'z' 是上涨幅度, 's' 是卖出持有代币的比例
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

    res = ProfitLossStrategy.get_single_token_profit(initial_used_input, signal_price_input, signal_ts_input,k_line_data_input, tp_rules_input, sl_rules_input, duration_input)
    logging.info(res)

if __name__ == '__main__':
    setup_logging()
    mock_data()