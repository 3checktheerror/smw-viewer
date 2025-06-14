import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


def calculate_signal_yield(
        t1: float,
        p1: float,
        kline_data: list,
        profit_strategies: list,
        loss_strategies: list,
        t2: float
) -> float:
    """
    计算单个信号在止盈止损策略下的收益率

    参数:
    t1: 告警时间戳
    p1: 告警价格
    kline_data: 秒级K线数据列表，每个元素为[时间戳, open, high, low, close]
    profit_strategies: 止盈策略列表，每个元素为(触发倍数, 卖出比例)
    loss_strategies: 止损策略列表，每个元素为(触发倍数, 卖出比例)
    t2: 策略生效时间(秒)

    返回:
    yield_rate: 收益率(0.0-1.0)
    """
    # 初始参数设置
    initial_coins = 100.0  # 假设初始买入100个代币
    current_coins = initial_coins
    total_sell_value = 0.0
    end_time = t1 + t2

    # 策略状态跟踪
    profit_triggered = [False] * len(profit_strategies)
    loss_triggered = [False] * len(loss_strategies)

    # 策略排序：止盈按触发倍数升序，止损按触发倍数降序
    profit_strategies = sorted(profit_strategies, key=lambda x: x[0])
    loss_strategies = sorted(loss_strategies, key=lambda x: x[0], reverse=True)

    # 处理每条K线数据
    for ts, _, high, low, _ in kline_data:
        if ts < t1:  # 忽略告警前的数据
            continue
        if ts > end_time:  # 超出策略有效期
            break

        # 检查止盈策略
        for idx, (z_ratio, sell_ratio) in enumerate(profit_strategies):
            if profit_triggered[idx]:
                continue

            trigger_price = p1 * z_ratio
            if high >= trigger_price:  # 达到止盈触发价
                sell_coins = current_coins * sell_ratio
                total_sell_value += sell_coins * trigger_price
                current_coins -= sell_coins
                profit_triggered[idx] = True

        # 检查止损策略
        for idx, (d_ratio, sell_ratio) in enumerate(loss_strategies):
            if loss_triggered[idx]:
                continue

            trigger_price = p1 * d_ratio
            if low <= trigger_price:  # 达到止损触发价
                sell_coins = current_coins * sell_ratio
                total_sell_value += sell_coins * trigger_price
                current_coins -= sell_coins
                loss_triggered[idx] = True

    # 计算收益率
    initial_investment = initial_coins * p1
    yield_rate = total_sell_value / initial_investment if initial_investment > 0 else 0.0
    return yield_rate


def generate_mock_kline(start_time: float, duration: int, volatility: float = 0.05) -> list:
    """
    生成模拟秒级K线数据

    参数:
    start_time: 起始时间戳
    duration: 数据持续时间(秒)
    volatility: 价格波动率

    返回:
    kline_data: 生成的K线数据列表
    """
    kline_data = []
    current_price = 1.0  # 起始价格

    for sec in range(duration):
        ts = start_time + sec
        open_price = current_price
        # 生成价格波动
        change = random.uniform(-volatility, volatility)
        current_price *= (1 + change)

        # 生成high/low (有10%概率出现大幅波动)
        if random.random() < 0.1:
            spike = random.uniform(0, 2 * volatility)
            if random.choice([True, False]):
                high = current_price * (1 + spike)
                low = current_price * (1 - spike / 2)
            else:
                high = current_price * (1 + spike / 2)
                low = current_price * (1 - spike)
        else:
            high = max(open_price, current_price) * (1 + random.uniform(0, volatility / 2))
            low = min(open_price, current_price) * (1 - random.uniform(0, volatility / 2))

        close_price = current_price
        kline_data.append([ts, open_price, high, low, close_price])

    return kline_data


def main():
    """主函数：模拟多个信号并计算平均收益率"""
    # 模拟参数配置
    num_signals = 10  # 模拟信号数量
    t2_duration = 3600  # 策略有效期(秒)
    results = []

    # 示例止盈止损策略
    profit_strategies = [
        (1.05, 0.3),  # 上涨5%时卖出30%
        (1.15, 0.5),  # 上涨15%时卖出50%
    ]
    loss_strategies = [
        (0.95, 0.2),  # 下跌5%时卖出20%
        (0.85, 0.6),  # 下跌15%时卖出60%
    ]

    for i in range(num_signals):
        # 生成随机告警时间和价格
        t1 = datetime.now().timestamp() - random.randint(0, 86400)
        p1 = random.uniform(0.8, 1.2)

        # 生成K线数据 (策略有效期前后各加300秒缓冲)
        kline_data = generate_mock_kline(t1 - 300, t2_duration + 600)

        # 计算收益率
        yield_rate = calculate_signal_yield(
            t1, p1, kline_data,
            profit_strategies, loss_strategies,
            t2_duration
        )

        results.append({
            'signal_id': i + 1,
            't1': datetime.fromtimestamp(t1).strftime('%Y-%m-%d %H:%M:%S'),
            'p1': round(p1, 4),
            'yield': round(yield_rate, 4)
        })

    # 打印结果
    print(f"模拟结果 ({num_signals}个信号, 策略有效期: {t2_duration // 60}分钟)")
    print("=" * 50)
    for res in results:
        print(f"信号 {res['signal_id']}: "
              f"告警时间={res['t1']}, "
              f"告警价格={res['p1']}, "
              f"收益率={res['yield'] * 100:.2f}%")

    avg_yield = sum(r['yield'] for r in results) / num_signals
    print("\n平均收益率: {:.2f}%".format(avg_yield * 100))


if __name__ == "__main__":
    main()