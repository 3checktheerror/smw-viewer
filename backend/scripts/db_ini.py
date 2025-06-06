"""
数据库索引初始化脚本
"""
import logging
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.core.config import settings
from backend.app.utils.log_utils import get_logger

logger = get_logger(__name__)


def init_token_collections():
    """初始化代币相关集合的索引"""
    mongo_client = MongoDBClient()
    
    try:
        
        # # 初始化 daily_onchain_token_collection 集合索引
        # onchain_collection = mongo_client.get_collection(settings.daily_onchain_token_collection, 'token')
        # if onchain_collection is not None:
        #     # 创建复合唯一索引 {chain, date, token}
        #     onchain_collection.create_index(
        #         [("chain", 1), ("date", 1), ("token", 1)],
        #         unique=True,
        #         name="idx_chain_date_token_unique"
        #     )
        #     logger.info(f"Created unique compound index for {settings.daily_onchain_token_collection}")
        # else:
        #     logger.error(f"Failed to get collection {settings.daily_onchain_token_collection}")
        #
        # # 初始化 daily_rank_token_collection 集合索引
        # rank_collection = mongo_client.get_collection(settings.daily_rank_token_collection, 'token')
        # if rank_collection is not None:
        #     # 创建复合唯一索引 {chain, date, token}
        #     rank_collection.create_index(
        #         [("chain", 1), ("date", 1), ("token", 1)],
        #         unique=True,
        #         name="idx_chain_date_token_unique"
        #     )
        #     logger.info(f"Created unique compound index for {settings.daily_rank_token_collection}")
        #
        # else:
        #     logger.error(f"Failed to get collection {settings.daily_rank_token_collection}")
        #
        # logger.info("Database indexes initialized successfully")
        # return True

        # 初始化 daily_rank_token_collection 集合索引
        rank_collection = mongo_client.get_collection('daily_wallet','wallet')
        if rank_collection is not None:
            # 创建复合唯一索引 {chain, date, token}
            rank_collection.create_index(
                [("chain", 1), ("wallet", 1)],
                unique=True,
                name="idx_chain_wallet_unique"
            )
            logger.info(f"Created unique compound index for {settings.daily_rank_token_collection}")

        else:
            logger.error(f"Failed to get collection {settings.daily_rank_token_collection}")

        logger.info("Database indexes initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database indexes: {e}")
        return False
    finally:
        mongo_client.close()


def main():
    """主函数"""
    logger.info("Starting database initialization...")
    
    if init_token_collections():
        logger.info("Database initialization completed successfully")
    else:
        logger.error("Database initialization failed")


if __name__ == "__main__":
    main()
