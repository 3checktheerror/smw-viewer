import logging
import uuid
from typing import List

from backend.app.domain.models.token import TokenModel
from backend.app.domain.models.wallet import WalletModel
from backend.app.repositories.token_repository import HotTokenRepository
from backend.app.services.smw.utils.debot_utils import DebotAPIUtils
from backend.app.services.smw.utils.wallet_utils import WalletUtils
from backend.app.utils.log_utils import setup_logging
from backend.app.utils.time_utils import TimeUtils


class TokenUtils:

    # 新老币 + 貔貅
    @staticmethod
    def get_wallet_group_bad_tokens(wallet_list: List[WalletModel]) -> List[TokenModel]:

        # 获得钱包代币集合
        chains = ['bsc', 'solana', 'base']
        wallet_groups, wallet_mapping = WalletUtils.group_wallet_by_chain(wallet_list)

        all_bad_tokens: List[TokenModel] = []
        for chain in chains:
            if chain not in wallet_groups:
                logging.info(f"链 {chain} 没有钱包数据，跳过")
                continue

            chain_wallets = wallet_groups[chain]
            logging.info(f"开始处理链 {chain}，钱包数量: {len(chain_wallets)}")
            trade_tokens_with_pair = HotTokenRepository().get_wallet_group_2d_trade_tokens(chain_wallets, chain)
            logging.info(f"钱包组token数量：{len(trade_tokens_with_pair)}")

            if not trade_tokens_with_pair:
                continue

            token_addresses = [item[0] for item in trade_tokens_with_pair]

            honeypot_tokens = set()
            if chain == 'bsc':
                # 貔貅
                tokens_for_honeypot_check = [token for token in token_addresses]
                honeypot_tokens = set(DebotAPIUtils.get_honeypot_tokens(tokens_for_honeypot_check, chain))
                logging.info(f"bsc貔貅token数量：{len(honeypot_tokens)}")
            elif chain == 'base':
                # 对于 base 链，需要 token 和 pair 地址一起判断貔貅
                honeypot_tokens = set(
                    DebotAPIUtils.get_honeypot_tokens(trade_tokens_with_pair, chain)
                )
                logging.info(f"base貔貅token数量：{len(honeypot_tokens)}")

            # 老币
            old_token_results = DebotAPIUtils.get_token_age(chain, token_addresses)
            old_tokens = {item['token'] for item in old_token_results if item['is_old']}
            logging.info(f"老币token数量：{len(old_tokens)}")

            # --- 新增日志 ---
            total_tokens_in_chain = len(token_addresses)
            if total_tokens_in_chain > 0:
                old_pct = (len(old_tokens) / total_tokens_in_chain) * 100
                if chain != 'solana':
                    honeypot_pct = (len(honeypot_tokens) / total_tokens_in_chain) * 100
                    logging.info(f"链 {chain} 统计: "
                                 f"貔貅: {len(honeypot_tokens)} ({honeypot_pct:.2f}%), "
                                 f"老币: {len(old_tokens)} ({old_pct:.2f}%)")
                else:
                    logging.info(f"链 {chain} 统计: "
                                 f"老币: {len(old_tokens)} ({old_pct:.2f}%)")

            processed_tokens = set()

            for token_address in token_addresses:
                if token_address in processed_tokens:
                    continue
                
                is_honeypot = token_address in honeypot_tokens
                is_old = token_address in old_tokens

                if is_honeypot or is_old:
                    token = TokenModel(
                        chain=chain,
                        address=token_address,
                        is_honeypot=is_honeypot,
                        is_old=is_old                    )
                    all_bad_tokens.append(token)
                
                processed_tokens.add(token_address)

        return all_bad_tokens


if __name__ == '__main__':
    from backend.app.utils.mongo_client import MongoDBClient
    setup_logging()
    mongodb_client = MongoDBClient()

    # 1. 从MongoDB读取钱包
    wallet_docs = mongodb_client.find_many(
        collection_name='phase1',
        db_name='test'
    )

    if not wallet_docs:
        logging.info("No wallets found in test.phase1 collection.")
    else:
        logging.info(f"Found {len(wallet_docs)} wallets in test.phase1 collection.")
        # 2. 转换为WalletModel列表
        wallet_list = []
        for doc in wallet_docs:
            if 'chain' in doc and 'address' in doc:
                wallet_list.append(WalletModel(
                    chain=doc['chain'],
                    address=doc['address'],
                    group_id= 111,
                    priority=0
                ))
            else:
                logging.warning(f"Skipping document due to missing 'chain' or 'address': {doc}")

        # 3. 调用函数
        if wallet_list:
            bad_tokens = TokenUtils.get_wallet_group_bad_tokens(wallet_list)
            logging.info(f"Found {len(bad_tokens)} bad tokens.")

            # 4. 结果入库
            if bad_tokens:
                # 将TokenModel转换为字典
                documents_to_insert = [token.model_dump() for token in bad_tokens]

                # 插入到phase2集合
                inserted_ids = mongodb_client.insert_many(
                    collection_name='phase2',
                    documents=documents_to_insert,
                    db_name='test'
                )
                if inserted_ids:
                    logging.info(f"Successfully inserted {len(inserted_ids)} bad tokens into test.phase2 collection.")
                else:
                    logging.error("Failed to insert bad tokens into test.phase2 collection.")
            else:
                logging.info("No bad tokens to insert.")
        else:
            logging.info("Wallet list is empty after processing, skipping token check.")
