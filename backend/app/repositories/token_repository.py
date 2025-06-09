"""
代币仓储类
"""
import logging
import time
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, InvalidOperation
from pymongo.errors import DuplicateKeyError

from backend.app.domain.models.wallet import WalletModel
from backend.app.utils import RedisSentinelClient, MongoDBClient
from backend.app.utils.pg_client import PostgreSQLClient
from backend.app.utils.thread_pool import ThreadPoolManager
from backend.app.core.config import settings
from backend.app.utils.time_utils import TimeUtils
from backend.app.services.smw.utils.debot_utils import DebotAPIUtils


class HotTokenRepository:
    """热门代币仓储类"""
    
    def __init__(self):
        self.redis_client = RedisSentinelClient()
        self.mongodb_client = MongoDBClient()
        self.pg_client = PostgreSQLClient()
    
    def get_token_streams(self) -> List[str]:
        """获取要扫描的代币流列表"""
        return settings.hot_token_streams
    
    def _get_chain_for_source(self, source: str) -> str:
        """根据数据源获取对应的链"""
        return settings.hot_token_chain_mapping.get(source)
    
    def _extract_source_from_stream(self, stream_key: str) -> str:
        """从流键名提取数据源名称"""
        # 从 "new_token_stream:pump" 提取 "pump"
        return stream_key.split(":")[-1] if ":" in stream_key else stream_key
    
    def get_previous_day_tokens(self) -> Dict[str, List[str]]:
        prev_date = TimeUtils.get_prev_date()
        
        onchain_tokens = self.mongodb_client.find_many(
            settings.daily_onchain_token_collection,
            {"date": prev_date},
            db_name=settings.mongodb_token_db,
        )
        
        rank_tokens = self.mongodb_client.find_many(
            settings.daily_rank_token_collection,
            {"date": prev_date},
            db_name=settings.mongodb_token_db,
        )
        
        chain_tokens = {}
        
        for token_doc in onchain_tokens:
            chain = token_doc.get("chain")
            token = token_doc.get("token")
            if chain and token:
                if chain not in chain_tokens:
                    chain_tokens[chain] = set()
                chain_tokens[chain].add(token)
        
        for token_doc in rank_tokens:
            chain = token_doc.get("chain")
            token = token_doc.get("token")
            if chain and token:
                if chain not in chain_tokens:
                    chain_tokens[chain] = set()
                chain_tokens[chain].add(token)
        
        return {chain: list(tokens) for chain, tokens in chain_tokens.items()}
    
    def read_tokens_from_stream(self, stream_key: str) -> List[Tuple[str, str, str]]:
        """
        从Redis流中读取代币信息
        
        Args:
            stream_key: 流键名
            
        Returns:
            代币信息列表，每个元素为 (chain, token_address, source)
        """
        tokens = []
        source = self._extract_source_from_stream(stream_key)
        chain = self._get_chain_for_source(source)
        
        try:
            messages = self.redis_client.xrevrange(
                stream_key, 
                '+', 
                '-', 
                count=settings.hot_token_stream_read_count
            )
            
            if not messages:
                logging.debug(f"No messages found in stream: {stream_key}")
                return tokens
            
            processed_tokens = set()
            
            for message_id, message_data in messages:
                token_address_bytes = message_data.get(b'token')
                if not token_address_bytes:
                    continue
                try:
                    token_address = token_address_bytes.decode('utf-8')
                    
                    # 避免重复处理同一个代币
                    token_key = f"{chain}:{token_address}"
                    if token_key in processed_tokens:
                        continue
                    processed_tokens.add(token_key)
                    tokens.append((chain, token_address, source))
                except UnicodeDecodeError:
                    logging.warning(f"Could not decode token address from stream {stream_key}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error reading from stream {stream_key}: {e}")
        
        return tokens


    def get_token_status(self, tokens_info: List[Tuple[str, str, str]]) -> Dict[Tuple[str, str, str], Optional[Dict]]:
        stats_keys = []
        token_key_mapping = {}
        for token_info in tokens_info:
            chain, token_address, source = token_info
            token_composite_id = f"{chain}:{token_address}"
            stats_key = f"{settings.hot_token_stats_key_prefix}{token_composite_id}"
            stats_keys.append(stats_key)
            token_key_mapping[stats_key] = token_info
        
        try:
            tokens_info = self.redis_client.pool_hgetall(stats_keys, pool_size=settings.lookup_worker_size)
            result_dict = {}
            
            for stats_key, token_data_raw in tokens_info.items():
                token_info = token_key_mapping[stats_key]
                
                if not token_data_raw:
                    result_dict[token_info] = None
                    continue
                
                try:
                    def to_decimal(value, default=Decimal(0)):
                        if value is None:
                            return default
                        try:
                            if isinstance(value, bytes):
                                value = value.decode('utf-8')
                            return Decimal(value)
                        except (InvalidOperation, ValueError, TypeError):
                            logging.warning(f"Could not convert '{value}' to Decimal. Using default: {default}")
                            return default
                    
                    total_supply = to_decimal(token_data_raw.get(b'totalSupply'))
                    last_price = to_decimal(token_data_raw.get(b'lastPrice'))
                    dev_holds = to_decimal(token_data_raw.get(b'devHolds'))
                    top10_holds = to_decimal(token_data_raw.get(b'top10Holds'))
                    volume = to_decimal(token_data_raw.get(b'volume'))
                    
                    if total_supply == Decimal(0):
                        result_dict[token_info] = None
                        continue
                    
                    market_cap = total_supply * last_price
                    dev_ratio = dev_holds / total_supply
                    top10_ratio = top10_holds / total_supply
                    
                    result_dict[token_info] = {
                        'market_cap': float(market_cap),
                        'dev_ratio': float(dev_ratio),
                        'top10_ratio': float(top10_ratio),
                        'volume': float(volume),
                        'total_supply': float(total_supply),
                        'last_price': float(last_price),
                        'dev_holds': float(dev_holds),
                        'top10_holds': float(top10_holds)
                    }
                    
                except Exception as e:
                    chain, token_address, source = token_info
                    logging.error(f"Error parsing token stats for {chain}:{token_address}: {e}")
                    result_dict[token_info] = None
            
            for token_info in tokens_info:
                if token_info not in result_dict:
                    result_dict[token_info] = None
            
            return result_dict
            
        except Exception as e:
            logging.error(f"Error in _batch_get_token_stats_chunk: {e}")
            return {token_info: None for token_info in tokens_info}

    @staticmethod
    def is_token_qualified(stats: Dict) -> bool:
        return (
            stats['market_cap'] >= settings.hot_token_market_cap_threshold and
            stats['dev_ratio'] < settings.hot_token_dev_share_threshold and
            stats['top10_ratio'] < settings.hot_token_top10_share_threshold and
            stats['volume'] > settings.hot_token_volume_threshold
        )
    
    def save_qualified_token(self, chain: str, token_address: str, source: str, stats: Dict) -> bool:
        try:
            current_date = TimeUtils.get_cur_bg_date()
            current_ts = TimeUtils.get_current_ts()

            # 先尝试插入新记录
            document_to_insert = {
                'chain': chain,
                'token': token_address,
                'date': current_date,
                'source': source,
                'market_cap': stats['market_cap'],
                'dev_ratio': stats['dev_ratio'],
                'top10_ratio': stats['top10_ratio'],
                'volume': stats['volume'],
                'stored_ts': current_ts,
                "updated_ts": current_ts
            }
            
            try:
                result = self.mongodb_client.insert_one(
                    collection_name=settings.daily_onchain_token_collection,
                    document=document_to_insert,
                    db_name=settings.mongodb_token_db
                )
                return True if result else False
            except DuplicateKeyError:
                # 如果插入失败（重复键），则查询现有记录并比较market_cap
                query = {
                    'chain': chain,
                    'token': token_address,
                    'date': current_date
                }
                
                existing_record = self.mongodb_client.find_one(
                    collection_name=settings.daily_onchain_token_collection,
                    filter_dict=query,
                    db_name=settings.mongodb_token_db
                )
                
                if existing_record:
                    existing_market_cap = existing_record.get('market_cap', 0)
                    current_market_cap = stats['market_cap']

                    if current_market_cap > existing_market_cap:
                        update_fields = {
                            'source': source,
                            'market_cap': stats['market_cap'],
                            'dev_ratio': stats['dev_ratio'],
                            'top10_ratio': stats['top10_ratio'],
                            'volume': stats['volume'],
                            "updated_ts": current_ts
                        }

                        update_result = self.mongodb_client.update_one(
                            collection_name=settings.daily_onchain_token_collection,
                            filter_dict ={'_id': existing_record['_id']},
                            update_dict={'$set': update_fields}
                        )
                        return True if update_result else False
                    else:
                        return True
                return False
                
        except Exception as e:
            logging.error(f"Error saving token {chain}:{token_address}: {e}")
            return False

    def save_rank_token(self, chain: str, documents: List[Dict]) -> bool:
        if not documents:
            logging.warning(f"No documents provided for chain {chain}")
            return False
            
        try:
            current_date = TimeUtils.get_cur_bg_date()
            current_ts = TimeUtils.get_current_ts()
            
            success_count = 0
            total_count = len(documents)
            
            for doc in documents:
                token_address = doc.get('token')
                if not token_address:
                    logging.warning(f"Document missing 'token' field: {doc}")
                    continue
                    
                document_to_insert = {
                    'chain': chain,
                    'token': token_address,
                    'date': current_date,
                    'stored_ts': current_ts,
                }
                
                try:
                    result = self.mongodb_client.insert_one(
                        collection_name=settings.daily_rank_token_collection,
                        document=document_to_insert,
                        db_name=settings.mongodb_token_db
                    )
                    if result:
                        success_count += 1
                except DuplicateKeyError:
                    # 如果是重复键错误，认为插入成功（因为记录已存在）
                    success_count += 1

            # logging.info(f"Successfully saved {success_count}/{total_count} rank tokens for chain {chain}")
            return success_count == total_count

        except Exception as e:
            logging.error(f"Error saving rank tokens for chain {chain}: {e}")
            return False



    def get_wallet_2d_trade_tokens(self, wallet: str, chain: str) -> List[Tuple[str, str]]:
        """
        获取钱包在指定链上的买入操作涉及的所有token和pair（去重）
        
        Args:
            wallet: 钱包地址
            chain: 链名称
            
        Returns:
            List[Tuple[str, str]]: token和pair的元组列表 [(token, pair), ...]
        """
        try:
            table_name = f"t_transaction_daily_{chain}"
            
            query = f"""
                SELECT DISTINCT token, pair 
                FROM {table_name} 
                WHERE wallet = %(wallet)s AND op = 'buy'
            """
            
            result = self.pg_client.execute(query, params={'wallet': wallet})
            return [(row[0], row[1]) for row in result if row[0] and row[1]]
            
        except Exception as e:
            logging.error(f"Error querying trade tokens for wallet {wallet} on {chain}: {e}")
            return []


    def get_wallet_group_2d_trade_tokens(self, wallet_list: List[str], chain: str) -> List[Tuple[str, str]]:
        """
        批量获取钱包组在指定链上的买入操作涉及的所有token和pair（按token去重）
        
        Args:
            wallet_list: 钱包地址列表
            chain: 链名称
            
        Returns:
            List[Tuple[str, str]]: 去重后的token和pair元组列表
        """
        if not wallet_list:
            return []
            
        try:
            def get_wallet_tokens(wallet: str) -> Tuple[str, List[Tuple[str, str]]]:
                """获取单个钱包的token-pair信息"""
                try:
                    tokens_pairs = self.get_wallet_2d_trade_tokens(wallet, chain)
                    return wallet, tokens_pairs
                except Exception as e:
                    logging.error(f"Error getting tokens for wallet {wallet}: {e}")
                    return wallet, []
            
            total_wallets = len(wallet_list)
            logging.info(f"Starting to get trade tokens for {total_wallets} wallets on chain {chain}")
            
            # 使用20个线程并发查询
            with ThreadPoolManager(max_workers=40) as pool:
                tasks_args = [(wallet,) for wallet in wallet_list]
                results = pool.execute_tasks_and_wait(get_wallet_tokens, tasks_args)
                
                # 收集所有token-pair，按token去重
                token_pair_dict = {}  # {token: pair}
                completed = 0
                
                for result in results:
                    try:
                        if result is not None:
                            wallet, tokens_pairs = result
                            for token, pair in tokens_pairs:
                                if token not in token_pair_dict:
                                    token_pair_dict[token] = pair
                        
                        completed += 1
                        if completed % 100 == 0 or completed == total_wallets:
                            progress = (completed / total_wallets) * 100
                            logging.info(f"Progress: {completed}/{total_wallets} ({progress:.1f}%) wallets processed for trade tokens")
                            
                    except Exception as e:
                        logging.error(f"Error processing wallet trade tokens result: {e}")
                        completed += 1
            
            result = list(token_pair_dict.items())
            logging.info(f"Completed getting trade tokens for {total_wallets} wallets. Found {len(result)} unique tokens")
            return result
            
        except Exception as e:
            logging.error(f"Error in _get_wallet_group_2d_trade_tokens: {e}")
            return []


    def close_connections(self):
        try:
            self.mongodb_client.close()
        except Exception as e:
            logging.error(f"Error closing MongoDB connection: {e}")
        
        try:
            self.pg_client.close()
        except Exception as e:
            logging.error(f"Error closing PostgreSQL connection: {e}")
