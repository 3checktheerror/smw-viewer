import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool


class PostgreSQLClient:
    
    def __init__(self):
        self.pool = None
        self._create_pool()

    def _create_pool(self):
        try:
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=50,
                user="postgres",
                password="ng5tUYb9k0H1fAD7",
                host="23.239.109.74",
                port=5432,
                database="diting_database"
            )
        except Exception as e:
            logging.error(f"Error creating PostgreSQL pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """返回 PostgreSQL 连接实例"""
        connection = None
        try:
            if not self.pool:
                self._create_pool()
            connection = self.pool.getconn()
            yield connection
        except Exception as e:
            logging.error(f"Database operation error: {e}")
            raise
        finally:
            if connection:
                self.pool.putconn(connection)

    def execute(self, query: str, params: Optional[Dict] = None) -> List[Tuple]:
        """执行 PostgreSQL 查询并返回结果"""
        with self.get_connection() as connection:
            try:
                cursor = connection.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                result = cursor.fetchall()
                cursor.close()
                return result
            except Exception as e:
                logging.error(f"PostgreSQL query execution failed: {e}")
                raise

    
    def get_distinct_wallets_by_token(self, chain: str, token: str, start_time: int, end_time: int) -> List[str]:
        table_name = f"t_transaction_daily_{chain}"
        query = f"""
            SELECT DISTINCT wallet 
            FROM {table_name}
            WHERE token = %(token)s AND op = 'buy' AND unix_time >= %(start_time)s AND unix_time <= %(end_time)s
        """
        
        params_dict = {
            'token': token,
            'start_time': start_time, 
            'end_time': end_time
        }
        
        try:
            result = self.execute(query, params_dict)
            return [row[0] for row in result]
        except Exception as e:
            logging.error(f"Error querying wallets for token {token} on {chain}: {e}")
            return []

    def get_distinct_wallets_by_tokens(self, chain: str, tokens: List[str], start_time: int, end_time: int) -> Dict[str, List[str]]:
        if not tokens:
            return {}
            
        table_name = f"t_transaction_daily_{chain}"
        tokens_tuple = tuple(tokens)
        
        query = f"""
            SELECT DISTINCT token, wallet
            FROM {table_name}
            WHERE token IN %(tokens)s AND op = 'buy' AND unix_time >= %(start_time)s AND unix_time <= %(end_time)s
        """
        
        params_dict = {
            'tokens': tokens_tuple,
            'start_time': start_time, 
            'end_time': end_time
        }
        
        try:
            result = self.execute(query, params_dict)
            
            token_wallets = {token: [] for token in tokens}
            for token, wallet in result:
                if token in token_wallets:
                    token_wallets[token].append(wallet)
            return token_wallets
        except Exception as e:
            logging.error(f"Error querying wallets for tokens on {chain}: {e}")
            return {}

    def close(self):
        """关闭连接池"""
        try:
            if self.pool:
                self.pool.closeall()
        except Exception as e:
            logging.error(f"Error closing PostgreSQL pool: {e}")
