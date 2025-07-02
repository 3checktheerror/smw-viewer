from typing import List
import logging
from collections import defaultdict

from backend.app.api.schemas.wallet_schemas import WalletOperation
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.time_utils import TimeUtils


class SMWDailyService:
    @staticmethod
    def sync_incremental_wallets(operations: List[WalletOperation]):
        """
        同步增量钱包操作
        op==1: 将钱包添加到smw_history集合
        op==2: 从history数据库中删除对应address的条目
        """
        if not operations:
            logging.info("没有增量钱包操作需要处理")
            return

        mongo_client = MongoDBClient()
        current_bg_date = TimeUtils.get_cur_bg_date()
        
        # 按操作类型分组
        operations_by_type = defaultdict(list)
        for op in operations:
            if op.op and op.address:
                operations_by_type[op.op].append(op)
        
        logging.info(f"增量钱包操作分组: {dict((k, len(v)) for k, v in operations_by_type.items())}")
        
        # 处理op==1: 添加到smw_history
        if 1 in operations_by_type:
            add_operations = operations_by_type[1]
            
            # 构建查询条件：查找已存在的chain+address组合
            existing_query = {
                "$or": [
                    {"address": op.address, "chain": op.chain} 
                    for op in add_operations if op.address and op.chain
                ]
            }
            
            existing_records = mongo_client.find_many(
                "smw_history",
                existing_query,
                projection={"address": 1, "chain": 1},
                db_name="history"
            )
            
            # 创建已存在记录的集合，用于快速查找
            existing_combinations = set()
            for record in existing_records:
                combination = f"{record.get('chain')}:{record.get('address')}"
                existing_combinations.add(combination)
            
            # 准备新增记录，排除已存在的
            new_records = []
            for op in add_operations:
                if op.address and op.chain:
                    combination = f"{op.chain}:{op.address}"
                    if combination not in existing_combinations:
                        new_record = {
                            "chain": op.chain,
                            "address": op.address,
                            "store_date": current_bg_date,
                            "out_tag": 1
                        }
                        new_records.append(new_record)
            
            # 批量插入新记录
            if new_records:
                mongo_client.insert_many("smw_history", new_records, db_name="history")
                logging.info(f"成功添加 {len(new_records)} 个钱包到smw_history集合")
            else:
                logging.info("没有新的钱包需要添加到smw_history集合")
        
        # 处理op==2: smw_incremental
        if 2 in operations_by_type:
            delete_operations = operations_by_type[2]
            addresses_to_delete = [op.address for op in delete_operations if op.address]
            
            if addresses_to_delete:
                # 批量删除
                delete_filter = {"address": {"$in": addresses_to_delete}}
                deleted_count = mongo_client.delete_many("smw_incremental", delete_filter, db_name="history")
                logging.info(f"从smw_incremental集合中删除了 {deleted_count} 个钱包记录")

    @staticmethod
    def sync_smart_wallets(operations: List[WalletOperation]):
        """
        同步智能钱包操作
        op==1: 将out_tag设置为4 (白名单)
        op==2: 将out_tag设置为1 (默认)
        op==3: 删除记录
        """
        if not operations:
            logging.info("没有智能钱包操作需要处理")
            return

        mongo_client = MongoDBClient()
        
        # 按操作类型分组
        operations_by_type = defaultdict(list)
        for op in operations:
            if op.op and op.address:
                operations_by_type[op.op].append(op)
        
        logging.info(f"智能钱包操作分组: {dict((k, len(v)) for k, v in operations_by_type.items())}")
        
        # 处理op==1: 设置out_tag为4 (白名单)
        if 1 in operations_by_type:
            whitelist_operations = operations_by_type[1]
            addresses_to_whitelist = [op.address for op in whitelist_operations if op.address]
            
            if addresses_to_whitelist:
                update_filter = {"address": {"$in": addresses_to_whitelist}}
                update_data = {"out_tag": 4}
                updated_count = mongo_client.update_many("smw_history", update_filter, update_data, db_name="history")
                logging.info(f"将 {updated_count} 个钱包设置为白名单 (out_tag=4)")
        
        # 处理op==2: 设置out_tag为1 (默认)
        if 2 in operations_by_type:
            default_operations = operations_by_type[2]
            addresses_to_default = [op.address for op in default_operations if op.address]
            
            if addresses_to_default:
                update_filter = {"address": {"$in": addresses_to_default}}
                update_data = {"out_tag": 1}
                updated_count = mongo_client.update_many("smw_history", update_filter, update_data, db_name="history")
                logging.info(f"将 {updated_count} 个钱包设置为默认状态 (out_tag=1)")
        
        # 处理op==3: 删除记录
        if 3 in operations_by_type:
            delete_operations = operations_by_type[3]
            addresses_to_delete = [op.address for op in delete_operations if op.address]
            
            if addresses_to_delete:
                delete_filter = {"address": {"$in": addresses_to_delete}}
                deleted_count = mongo_client.delete_many("smw_history", delete_filter, db_name="history")
                logging.info(f"从smw_history集合中删除了 {deleted_count} 个钱包记录")

