from typing import List

from backend.app.api.schemas.wallet_schemas import SMWHistoryModel
from backend.app.domain.models.wallet import WalletModel
from backend.app.services.smw.utils.wallet_utils import WalletUtils
from backend.app.utils.mongo_client import MongoDBClient


DB_NAME = "history"
COLLECTION_NAME = "smw_history"


class SMWHistoryManager:

    @classmethod
    def get_smw_history_wallets(cls) -> List[SMWHistoryModel]:
        mongo_client = MongoDBClient()
        
        # 1. 从smw_history集合中读取所有数据
        history_data = mongo_client.find_many(
            COLLECTION_NAME,
            {},
            projection={"chain": 1, "address": 1, "store_date": 1, "out_tag": 1},
            db_name=DB_NAME
        )
        
        if not history_data:
            return []
        
        # 2. 转换为WalletModel列表用于获取统计数据
        wallet_models = []
        for record in history_data:
            chain = record.get('chain')
            address = record.get('address')
            if chain and address:
                wallet_models.append(WalletModel(
                    chain=chain,
                    address=address
                ))
        
        # 3. 获取钱包统计数据
        wallet_stats = WalletUtils.get_wallet_daily_statistics(wallet_models)
        
        # 4. 组合结果数据并转换为SMWHistoryModel
        result_wallets = []
        for record in history_data:
            address = record.get('address')
            chain = record.get('chain')
            store_date = record.get('store_date')
            out_tag = record.get('out_tag', 1)
            
            # 获取统计数据
            stats = wallet_stats.get(address, {})
            pnl = stats.get('pnl', 0.0)
            winrate = stats.get('winrate', 0.0)
            token_winrate = stats.get('token_winrate', 0.0)
            
            # 创建SMWHistoryModel对象
            history_wallet = SMWHistoryModel(
                address=address,
                chain=chain,
                pnl=pnl,
                winrate=winrate,
                token_winrate=token_winrate,
                store_date=store_date,
                out_tag=out_tag
            )
            result_wallets.append(history_wallet)
        
        return result_wallets