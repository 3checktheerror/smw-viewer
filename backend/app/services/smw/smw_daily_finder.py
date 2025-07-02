from backend.app.utils.log_utils import setup_logging
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.time_utils import TimeUtils
import logging


class SMWDailyManager:
    @staticmethod
    def generate_incremental_wallets():
        mongo_client = MongoDBClient()
        
        # 获取时间点
        three_days_ago = TimeUtils.get_3_days_ago_bg_date()
        four_days_ago = TimeUtils.get_4_days_ago_bg_date()
        five_days_ago = TimeUtils.get_5_days_ago_bg_date()
        current_bg_date = TimeUtils.get_cur_bg_date()
        
        logging.info(f"查询日期: que_1={three_days_ago}, que_2={four_days_ago}, que_3={five_days_ago}")
        
        # 1. 从队列集合中读取数据
        s1_data = []
        
        # que_1集合中读取3天前的数据
        que_1_data = mongo_client.find_many(
            "que_1", 
            {"stored_date": three_days_ago}, 
            projection={"chain": 1, "address": 1}, 
            db_name="smw"
        )
        s1_data.extend(que_1_data)
        
        # que_2集合中读取4天前的数据
        que_2_data = mongo_client.find_many(
            "que_2", 
            {"stored_date": four_days_ago}, 
            projection={"chain": 1, "address": 1}, 
            db_name="smw"
        )
        s1_data.extend(que_2_data)
        
        # que_3集合中读取5天前的数据
        que_3_data = mongo_client.find_many(
            "que_3", 
            {"stored_date": five_days_ago}, 
            projection={"chain": 1, "address": 1}, 
            db_name="smw"
        )
        s1_data.extend(que_3_data)
        
        logging.info(f"从队列集合中读取到 {len(s1_data)} 条记录")
        
        if not s1_data:
            logging.info("队列集合中没有符合条件的数据")
            return
        
        # 2. 从历史集合中读取所有数据
        s2_data = mongo_client.find_many(
            "smw_history", 
            {}, 
            projection={"chain": 1, "address": 1}, 
            db_name="history"
        )
        
        logging.info(f"从历史集合中读取到 {len(s2_data)} 条记录")
        
        # 3. 创建历史数据的chain+address组合集合，用于快速查找
        s2_combinations = set()
        for record in s2_data:
            chain = record.get('chain')
            address = record.get('address')
            if chain and address:
                s2_combinations.add(f"{chain}:{address}")
        
        # 4. 过滤s1数据，排除在s2中出现过的记录
        filtered_s1 = []
        for record in s1_data:
            chain = record.get('chain')
            address = record.get('address')
            if chain and address:
                combination = f"{chain}:{address}"
                if combination not in s2_combinations:
                    filtered_s1.append(record)
        
        logging.info(f"过滤后剩余 {len(filtered_s1)} 条记录")
        
        if not filtered_s1:
            logging.info("过滤后没有需要新增的记录")
            return
        
        # 5. 按address去重，保留每个address的第一条记录
        unique_records = {}
        for record in filtered_s1:
            address = record.get('address')
            if address and address not in unique_records:
                unique_records[address] = record
        
        # 6. 添加当前北京时间日期，准备插入数据
        incremental_records = []
        for record in unique_records.values():
            incremental_record = {
                'chain': record.get('chain'),
                'address': record.get('address'),
                'store_date': current_bg_date
            }
            incremental_records.append(incremental_record)
        
        logging.info(f"去重后准备插入 {len(incremental_records)} 条记录")
        
        # 7. 插入到smw_incremental集合
        if incremental_records:
            mongo_client.insert_many("smw_incremental", incremental_records, db_name="history")
            logging.info(f"成功插入 {len(incremental_records)} 条记录到smw_incremental集合")
        else:
            logging.info("没有记录需要插入")


    @staticmethod
    def get_daily_incremental_wallets():
        from backend.app.domain.models.wallet import WalletModel
        from backend.app.services.smw.utils.wallet_utils import WalletUtils
        
        mongo_client = MongoDBClient()
        current_bg_date = TimeUtils.get_cur_bg_date()
        
        logging.info(f"查询当前北京时间日期: {current_bg_date}")
        
        # 1. 读取今日增量钱包数据
        incremental_data = mongo_client.find_many(
            "smw_incremental",
            {"store_date": current_bg_date},
            projection={"chain": 1, "address": 1},
            db_name="history"
        )
        
        logging.info(f"从smw_incremental集合中读取到 {len(incremental_data)} 条记录")
        
        if not incremental_data:
            logging.info("今日没有增量钱包数据")
            return []
        
        # 2. 转换为WalletModel列表
        wallet_models = []
        for record in incremental_data:
            chain = record.get('chain')
            address = record.get('address')
            if chain and address:
                wallet_models.append(WalletModel(
                    chain=chain,
                    address=address,
                    stored_date=current_bg_date
                ))
        
        logging.info(f"转换为 {len(wallet_models)} 个WalletModel对象")
        
        # 3. 获取钱包统计数据
        wallet_stats = WalletUtils.get_wallet_daily_statistics(wallet_models)
        
        # 4. 组合结果数据
        result_wallets = []
        for record in incremental_data:
            address = record.get('address')
            chain = record.get('chain')
            
            if address and address in wallet_stats:
                stats = wallet_stats[address]
                result_wallet = {
                    'chain': chain,
                    'address': address,
                    'store_date': current_bg_date,
                    'pnl': stats.get('pnl', 0.0),
                    'winrate': stats.get('winrate', 0.0),
                    'token_winrate': stats.get('token_winrate', 0.0)
                }
                result_wallets.append(result_wallet)
            else:
                # 如果没有统计数据，设置默认值
                result_wallet = {
                    'chain': chain,
                    'address': address,
                    'store_date': current_bg_date,
                    'pnl': 0.0,
                    'winrate': 0.0,
                    'token_winrate': 0.0
                }
                result_wallets.append(result_wallet)
        
        logging.info(f"返回 {len(result_wallets)} 个包含统计数据的钱包记录")
        return result_wallets


if __name__ == '__main__':
    setup_logging()
    print(SMWDailyManager.get_daily_incremental_wallets())