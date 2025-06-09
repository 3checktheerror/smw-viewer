import logging
import sys
import os
from typing import List

# 添加路径以便导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.tasks.base_wallet_finder_tasks import BaseWalletFinderTask
from backend.app.services.smw.smw_filter_utils import SMWFilterUtils
from backend.app.utils.log_utils import setup_logging
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.domain.models.wallet import WalletModel
from backend.app.core.config import settings
from backend.app.utils.time_utils import TimeUtils


def load_wallets_from_mongodb() -> List[WalletModel]:
    """从MongoDB的daily_wallet集合中读取钱包数据并转换为WalletModel"""
    mongo_client = MongoDBClient()
    
    try:
        # 从daily_wallet集合读取钱包数据
        wallet_docs = mongo_client.find_many(
            db_name='test',
            collection_name='phase1',
            filter_dict={},  # 获取所有钱包
        )
        
        logging.info(f"从MongoDB读取到 {len(wallet_docs)} 个钱包文档")
        
        # 转换为WalletModel列表
        wallet_models = []
        for doc in wallet_docs:
            try:
                # 从MongoDB文档构建WalletModel
                wallet_model = WalletModel(
                    chain=doc.get('chain', ''),
                    address=doc.get('address', ''),
                    group_id=doc.get('group', 111),
                    priority=doc.get('priority', 1)
                )
                wallet_models.append(wallet_model)
            except Exception as e:
                logging.warning(f"跳过无效钱包文档: {doc}, 错误: {str(e)}")
                continue
        
        # 按链类型统计
        chain_counts = {}
        for wallet in wallet_models:
            chain_counts[wallet.chain] = chain_counts.get(wallet.chain, 0) + 1
        
        logging.info(f"成功加载 {len(wallet_models)} 个钱包模型")
        logging.info(f"按链分布: {chain_counts}")
        
        return wallet_models
        
    except Exception as e:
        logging.error(f"从MongoDB加载钱包数据失败: {str(e)}")
        return []
    finally:
        mongo_client.close()


def save_filtered_wallets_to_test_db(filtered_wallets: List[WalletModel]) -> bool:
    """将过滤后的钱包保存到test数据库的test2集合"""
    mongo_client = MongoDBClient()
    
    try:
        current_ts = TimeUtils.get_current_ts()
        
        # 准备要插入的文档
        documents = []
        for wallet in filtered_wallets:
            documents.append({
                'chain': wallet.chain,
                'address': wallet.address,
                'group': wallet.group_id,
                'priority': wallet.priority,
                'filtered_time': current_ts
            })
        
        if documents:
            # 插入过滤后的钱包
            result_ids = mongo_client.insert_many(
                collection_name="phase2",
                documents=documents,
                db_name="test"
            )
            
            success = len(result_ids) == len(documents)
            if success:
                logging.info(f"成功将 {len(documents)} 个过滤后的钱包保存到集合")
            else:
                logging.error(f"保存失败，期望保存 {len(documents)} 个，实际保存 {len(result_ids)} 个")
            
            return success
        else:
            logging.warning("没有钱包需要保存")
            return True
            
    except Exception as e:
        logging.error(f"保存过滤后的钱包到测试数据库失败: {str(e)}")
        return False
    finally:
        mongo_client.close()


def main():
    """主函数"""
    # 设置日志
    setup_logging()
    
    logging.info("=== 钱包过滤器测试开始 ===")
    
    try:
        # 第一步：运行BaseWalletFinderTask获取钱包入库
        # logging.info("第一步：运行BaseWalletFinderTask获取钱包入库")
        # wallet_finder = BaseWalletFinderTask()
        # wallet_finder.run()
        # logging.info("BaseWalletFinderTask执行完成")
        
        # 第二步：从数据库加载钱包数据
        logging.info("第二步：从数据库加载钱包数据")
        wallet_models = load_wallets_from_mongodb()
        
        if not wallet_models:
            logging.warning("没有找到钱包数据，测试结束")
            return

        # 第三步：应用SMW过滤器
        logging.info("第三步：开始SMW过滤")
        filtered_wallets = SMWFilterUtils.start_filter(wallet_models)

        logging.info(f"过滤完成:")
        logging.info(f"  输入钱包数量: {len(wallet_models)}")
        logging.info(f"  输出有效钱包数量: {len(filtered_wallets)}")

        # 按链统计过滤后的钱包
        filtered_chain_counts = {}
        for wallet in filtered_wallets:
            filtered_chain_counts[wallet.chain] = filtered_chain_counts.get(wallet.chain, 0) + 1
        logging.info(f"  过滤后钱包按链分布: {filtered_chain_counts}")

        # 第四步：保存到测试数据库
        logging.info("第四步：保存过滤结果到集合")
        save_success = save_filtered_wallets_to_test_db(filtered_wallets)

        if save_success:
            logging.info("=== 钱包过滤器测试成功完成 ===")
        else:
            logging.error("=== 钱包过滤器测试失败：保存结果时出错 ===")

    except Exception as e:
        logging.error(f"钱包过滤器测试过程中发生错误: {str(e)}", exc_info=True)
        logging.error("=== 钱包过滤器测试失败 ===")


if __name__ == "__main__":
    main()
