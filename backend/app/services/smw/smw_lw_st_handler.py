import logging
from typing import List, Optional

from backend.app.domain.models.wallet import WalletModel
from backend.app.utils import ThreadPoolManager, MongoDBClient
import pandas as pd

from backend.app.utils.ck_client import ClickHouseClient
from backend.app.services.smw.utils.debot_utils import DebotAPIUtils
from backend.app.services.smw.utils.alchemy_utils import AlchemyUtils


class LowStatisticWalletHandler:

    def __init__(self):
        self.ck_client = ClickHouseClient()

    @staticmethod
    def meets_criteria(market_data: dict, chain: str, is_second_check: bool = True) -> bool:
        try:
            if is_second_check:
                token_winrate = float(market_data.get('token_winrate_7d', 0.0) or 0.0)
                return token_winrate > 0.3
            else:

                pnl = float(market_data.get('pnl_7d', 0.0) or 0.0)
                if pnl <= 0.4:
                    return False

                avg_cost = float(market_data.get('avg_buy_volume_7d', 0.0) or 0.0)
                if avg_cost <= 300:
                    return False

                winrate = float(market_data.get('winrate_7d', 0.0) or 0.0)
                if winrate <= (0.3 if chain in ['bsc', 'solana'] else 0.4):
                    return False

                realize_profit = float(market_data.get('realized_profit_7d', 0.0) or 0.0)
                if realize_profit <= 300:
                    return False

                buy = market_data.get('buy_times_7d', 0) or 0
                sell = market_data.get('sell_times_7d', 0) or 0
                if (buy + sell) <= 25:
                    return False

                if (buy + sell) >= 300:
                    return False

                return True

        except (TypeError, ValueError) as e:
            logging.warning(f"数据类型转换失败: {str(e)}")
            return False

    def get_wallet_token_win_rate(self, chain: str, wallets: list, search_days: int = 7) -> dict:
        if not chain or not wallets:
            logging.error("链名或钱包地址不能为空")
            return {}

        formatted_wallets = ",".join(f"'{w}'" for w in wallets)
        sql = f"""
            WITH t_price AS (
                SELECT 
                    chain,
                    token,
                    argMaxMerge(last_price_state) AS last_price
                FROM t_token_latest_state_distributed
                WHERE token GLOBAL IN (
                    SELECT DISTINCT token
                    FROM t_wallet_token_analysis_distributed
                    WHERE (chain = '{chain}') AND (wallet in ({formatted_wallets}))
                )
                GROUP BY chain, token
            ),
            t_token AS (
                SELECT 
                    wallet,
                    chain,
                    token,
                    sum(profit) AS realized_profit,
                    sum(actual_trade_amount) AS position,
                    sum(actual_trade_cost) AS cost
                FROM t_transactions_wallet_distributed
                WHERE (chain = '{chain}')
                    AND (wallet in ({formatted_wallets}))
                    AND (op IN ('buy', 'sell'))
                    AND (unix_time > toStartOfDay(now() - toIntervalDay({search_days - 1}),'Asia/Shanghai'))
                GROUP BY chain, token, wallet
            ),
            t_total_profit AS (
                SELECT 
                    wallet,
                    (realized_profit + (position * last_price)) - cost AS total_profit
                FROM t_token
                GLOBAL LEFT JOIN t_price USING (chain, token)
            )
            SELECT 
                wallet,
                if(count(1) != 0, sum(if(total_profit > 0, 1, 0)) / count(1), 0) AS token_win_rate
            FROM t_total_profit
            GROUP BY wallet
        """
        try:
            result = self.ck_client.execute(sql)
            return {row[0]: float(row[1]) for row in result}
        except Exception as e:
            logging.error(f"查询钱包胜率失败: {str(e)}")
            return {w: 0.0 for w in wallets}

    def get_wallet_pnl(self, chain: str, wallets: list) -> dict:
        formatted_wallets = ",".join(f"'{w}'" for w in wallets)
        sql = f"""
            WITH t AS
            (
                SELECT
                    chain,
                    wallet,
                    SUM(IF(op = 'sell' AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(6), 'Asia/Shanghai'), profit, 0)) AS realized_profit_7d,
                    SUM(IF(op = 'sell' AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(29),'Asia/Shanghai'), profit, 0)) AS realized_profit_30d,
                    SUM(IF(op = 'sell' AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(6), 'Asia/Shanghai') AND profit > 0, 1, 0)) AS win_times_7d,
                    SUM(IF(op = 'sell' AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(29),'Asia/Shanghai') AND profit > 0, 1, 0)) AS win_times_30d,
                    SUM(IF(op = 'buy'  AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(6), 'Asia/Shanghai'), 1, 0))       AS buy_times_7d,
                    SUM(IF(op = 'sell' AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(6), 'Asia/Shanghai'), 1, 0))       AS sell_times_7d,
                    SUM(IF(op = 'buy'  AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(29),'Asia/Shanghai'), 1, 0))      AS buy_times_30d,
                    SUM(IF(op = 'sell' AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(29),'Asia/Shanghai'), 1, 0))      AS sell_times_30d,
                    SUM(IF(op = 'buy'  AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(6), 'Asia/Shanghai'), volume, 0))  AS buy_volume_7d,
                    SUM(IF(op = 'sell' AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(6), 'Asia/Shanghai'), volume, 0)) * -1 AS sell_volume_7d,
                    SUM(IF(op = 'buy'  AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(29),'Asia/Shanghai'), volume, 0)) AS buy_volume_30d,
                    SUM(IF(op = 'sell' AND toDateTime(unix_time) >= toStartOfDay(NOW() - toIntervalDay(29),'Asia/Shanghai'), volume, 0)) * -1 AS sell_volume_30d,
                    MAX(unix_time) AS last_active_timestamp
                FROM t_transactions_wallet_distributed
                WHERE (chain = '{chain}') AND (wallet in ({formatted_wallets})) AND (toDateTime(unix_time) >= (NOW() - toIntervalDay(30))) AND ((op = 'buy') OR (op = 'sell'))
                GROUP BY chain, wallet
            )
            SELECT
                chain,
                wallet,
                realized_profit_7d,
                realized_profit_30d,
                if(buy_volume_7d = 0, 0, realized_profit_7d / buy_volume_7d) AS pnl_7d,
                if(buy_volume_30d = 0, 0, realized_profit_30d / buy_volume_30d) AS pnl_30d,
                win_times_7d,
                win_times_30d,
                buy_times_7d,
                sell_times_7d,
                buy_times_30d,
                sell_times_30d,
                buy_volume_7d,
                sell_volume_7d,
                buy_volume_30d,
                sell_volume_30d,
                if(buy_times_7d = 0, 0, buy_volume_7d / buy_times_7d) AS avg_buy_volume_7d,
                if(buy_times_30d = 0, 0, buy_volume_30d / buy_times_30d) AS avg_buy_volume_30d,
                if(sell_times_7d = 0, 0, win_times_7d / sell_times_7d) AS winrate_7d,
                if(sell_times_30d = 0, 0, win_times_30d / sell_times_30d) AS winrate_30d,
                last_active_timestamp
            FROM t
        """
        try:
            result = self.ck_client.execute(sql)
            return {
                row[1]: {
                    "chain": row[0],
                    "wallet": row[1],
                    "realized_profit_7d": float(row[2]) if row[2] is not None else 0.0,
                    "realized_profit_30d": float(row[3]) if row[3] is not None else 0.0,
                    "pnl_7d": float(row[4]) if row[4] is not None else 0.0,
                    "pnl_30d": float(row[5]) if row[5] is not None else 0.0,
                    "win_times_7d": float(row[6]),
                    "win_times_30d": float(row[7]),
                    "buy_times_7d": float(row[8]),
                    "sell_times_7d": float(row[9]),
                    "buy_times_30d": float(row[10]),
                    "sell_times_30d": float(row[11]),
                    "buy_volume_7d": float(row[12]),
                    "sell_volume_7d": float(row[13]),
                    "buy_volume_30d": float(row[14]),
                    "sell_volume_30d": float(row[15]),
                    "avg_buy_volume_7d": float(row[16]) if row[16] is not None else 0.0,
                    "avg_buy_volume_30d": float(row[17]) if row[17] is not None else 0.0,
                    "winrate_7d": float(row[18]) if row[18] is not None else 0.0,
                    "winrate_30d": float(row[19]) if row[19] is not None else 0.0,
                    "last_active_timestamp": row[20]
                } for row in result
            }
        except Exception as e:
            logging.error(f"get_wallet_30d_pnl: {str(e)}")
            return {}

    def get_wallet_stats(self, chain: str, wallets: list, total_records: int, processed_so_far: int=0) -> dict:
        result_dict = {}
        total_wallets = len(wallets)
        max_workers = 1
        batch_size = 5000
        processed_count = 0

        logging.info(f"开始处理 {len(wallets)} 个钱包，链类型: {chain}")

        def process_batch(batch_wallets: list) -> dict:
            nonlocal processed_count
            try:
                pnl_data = self.get_wallet_pnl(chain, batch_wallets)
                valid_wallets = pd.Series([
                    w for w in batch_wallets
                    if pnl_data.get(w) and LowStatisticWalletHandler.meets_criteria(pnl_data[w], chain, False)
                ])

                if valid_wallets.empty:
                    return {}

                token_winrates = self.get_wallet_token_win_rate(chain, valid_wallets.tolist())
                df = pd.DataFrame.from_dict(pnl_data, orient='index')
                df['token_winrate_7d'] = df.index.map(token_winrates)
                valid_data = df[df.apply(lambda x: LowStatisticWalletHandler.meets_criteria(x.to_dict(), chain, True), axis=1)]
                return valid_data.to_dict('index')
            except Exception as e:
                logging.error(f"处理批次失败: {str(e)}", exc_info=True)
                return {}
            finally:
                processed_count += len(batch_wallets)
                current_total = processed_so_far + processed_count
                progress = current_total / total_records * 100 if total_records > 0 else 0
                logging.info(
                    f"处理进度: {current_total}/{total_records} ({progress:.1f}%)"
                )

        wallet_batches = [wallets[i:i + batch_size] for i in range(0, len(wallets), batch_size)]
        
        with ThreadPoolManager(max_workers=max_workers) as executor:
            tasks_args = [(batch,) for batch in wallet_batches]
            results = executor.execute_tasks_and_wait(process_batch, tasks_args)
            
            for result in results:
                if result:
                    result_dict.update(result)
        
        logging.info(f"处理完成，有效钱包数: {len(result_dict)}/{total_wallets}")
        return result_dict

    @staticmethod
    def filter(wallet_list: List[WalletModel]) -> List[WalletModel]:
        if not wallet_list:
            logging.warning("钱包列表为空")
            return []
        
        # 按照chain进行归类
        wallet_groups = {}
        wallet_mapping = {}  # 用于保存原始WalletModel信息
        
        for wallet in wallet_list:
            if wallet.chain not in wallet_groups:
                wallet_groups[wallet.chain] = []
            wallet_groups[wallet.chain].append(wallet.address)
            wallet_mapping[wallet.address] = wallet
        
        logging.info(f"钱包按链分组统计: {[(chain, len(addresses)) for chain, addresses in wallet_groups.items()]}")
        
        # 支持的链类型
        chains = ['solana', 'bsc', 'base']
        handler = LowStatisticWalletHandler()
        
        # 汇总结果
        filtered_wallets = []
        total_wallets = len(wallet_list)
        processed_so_far = 0
        
        # 遍历支持的链类型
        for chain in chains:
            if chain not in wallet_groups:
                logging.info(f"链 {chain} 没有钱包数据，跳过")
                continue
                
            chain_wallets = wallet_groups[chain]
            logging.info(f"开始处理链 {chain}，钱包数量: {len(chain_wallets)}")
            
            # 调用get_wallet_stats获取满足条件的钱包
            valid_wallet_stats = handler.get_wallet_stats(
                chain=chain,
                wallets=chain_wallets,
                total_records=total_wallets,
                processed_so_far=processed_so_far
            )

            MongoDBClient().insert_many(collection_name='phase1-bak', documents=list(valid_wallet_stats.values()), db_name='test')

            # 对满足条件的钱包进行额外过滤：balance > 0 且 7D_token_num >= 5
            def check_wallet_validity(wallet_address: str) -> Optional[str]:
                """检查单个钱包是否满足余额和代币数量条件"""
                try:
                    # 检查钱包余额
                    balance = AlchemyUtils.get_wallet_balance(wallet_address, chain)
                    if balance is None or balance <= 0:
                        logging.debug(f"钱包 {wallet_address} 余额不足，跳过")
                        return None
                    
                    # 检查7天内代币数量
                    token_data = DebotAPIUtils.get_wallet_7d_token(wallet_address, chain)
                    if token_data.get("7D_token_num", 0) < 5:
                        logging.debug(f"钱包 {wallet_address} 7天内代币数量不足5个，跳过")
                        return None
                    
                    # 通过所有过滤条件
                    return wallet_address
                    
                except Exception as e:
                    logging.error(f"处理钱包 {wallet_address} 时出错: {str(e)}")
                    return None
            
            # 使用100个线程并行处理钱包过滤
            wallet_addresses = valid_wallet_stats
            
            if wallet_addresses:
                logging.info(f"开始并行检查 {len(wallet_addresses)} 个钱包的余额和代币数量")
                
                with ThreadPoolManager(max_workers=50) as executor:
                    tasks_args = [(wallet_address,) for wallet_address in wallet_addresses]
                    results = executor.execute_tasks_and_wait(check_wallet_validity, tasks_args)
                    final_valid_wallets = [wallet for wallet in results if wallet is not None]
                
                logging.info(f"并行过滤完成，通过余额和代币数量检查的钱包数: {len(final_valid_wallets)}")
            
            for wallet_address in final_valid_wallets:
                if wallet_address in wallet_mapping:
                    filtered_wallets.append(wallet_mapping[wallet_address])
            
            processed_so_far += len(chain_wallets)
            logging.info(f"链 {chain} 处理完成，初步有效钱包数: {len(chain_wallets)}，最终有效钱包数: {len(final_valid_wallets)}")
        
        logging.info(f"总体处理完成，输入钱包数: {len(wallet_list)}, 输出有效钱包数: {len(filtered_wallets)}")
        return filtered_wallets