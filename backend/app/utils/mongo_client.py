"""
MongoDB客户端工具类
"""
import logging
import time
from typing import Optional, Dict, Any, List
from pymongo import MongoClient as PyMongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError
from backend.app.core.config import settings



class MongoDBClient:
    """MongoDB客户端封装类"""
    
    def __init__(self):
        self._client: Optional[PyMongoClient] = None
        self._db: Optional[Database] = None
    
    def get_client(self) -> Optional[PyMongoClient]:
        """获取MongoDB客户端连接"""
        if self._client is None:
            self._client = self._create_connection()
        return self._client
    
    def _create_connection(self) -> Optional[PyMongoClient]:
        """创建MongoDB连接"""
        try:
            client = PyMongoClient(settings.mongodb_url)
            # logging.info("Successfully connected to MongoDB")
            return client
        except PyMongoError as e:
            logging.error(f"Error connecting to MongoDB: {e}")
            return None

    def _get_database(self, db_name: str) -> Optional[Database]:
        """获取数据库"""
        client = self.get_client()
        if client is None:
            return None

        db_name = db_name
        try:
            return client[db_name]
        except PyMongoError as e:
            logging.error(f"Error getting database {db_name}: {e}")
            return None
    
    def get_collection(self, collection_name: str, db_name: str = None) -> Optional[Collection]:
        """获取集合"""
        db = self._get_database(db_name)
        if db is None:
            return None
        
        try:
            return db[collection_name]
        except PyMongoError as e:
            logging.error(f"Error getting collection {collection_name}: {e}")
            return None
    
    def insert_one(self, collection_name: str, document: Dict[str, Any], db_name: str = None) -> Optional[str]:
        """插入单个文档"""
        collection = self.get_collection(collection_name, db_name)
        if collection is None:
            return None
        
        try:
            result = collection.insert_one(document)
            return str(result.inserted_id)
        except PyMongoError as e:
            # logging.error(f"Error inserting document to {collection_name}: {e}")
            return None
    
    def insert_many(self, collection_name: str, documents: List[Dict[str, Any]], db_name: str = None) -> List[str]:
        """插入多个文档"""
        collection = self.get_collection(collection_name, db_name)
        if collection is None:
            return []
        
        try:
            result = collection.insert_many(documents)
            return [str(id_) for id_ in result.inserted_ids]
        except PyMongoError as e:
            logging.error(f"Error inserting documents to {collection_name}: {e}")
            return []
    
    def find_one(self, collection_name: str, filter_dict: Dict[str, Any] = None, db_name: str = None) -> Optional[Dict]:
        """查找单个文档"""
        collection = self.get_collection(collection_name, db_name)
        if collection is None:
            return None
        
        try:
            return collection.find_one(filter_dict or {})
        except PyMongoError as e:
            logging.error(f"Error finding document in {collection_name}: {e}")
            return None
    
    def find_many(self, collection_name: str, filter_dict: Dict[str, Any] = None, 
                  limit: int = None, db_name: str = None) -> List[Dict]:
        """查找多个文档"""
        collection = self.get_collection(collection_name, db_name)
        if collection is None:
            return []
        
        try:
            cursor = collection.find(filter_dict or {})
            if limit:
                cursor = cursor.limit(limit)
            return list(cursor)
        except PyMongoError as e:
            logging.error(f"Error finding documents in {collection_name}: {e}")
            return []

    
    def update_one(self, collection_name: str, filter_dict: Dict[str, Any], 
                   update_dict: Dict[str, Any], db_name: str = None) -> bool:
        """更新单个文档"""
        collection = self.get_collection(collection_name, db_name)
        if collection is None:
            return False
        
        try:
            # 检查update_dict是否已经包含MongoDB操作符
            has_operators = any(key.startswith('$') for key in update_dict.keys())
            if has_operators:
                result = collection.update_one(filter_dict, update_dict)
            else:
                result = collection.update_one(filter_dict, {"$set": update_dict})
            
            return result.modified_count > 0
        except PyMongoError as e:
            logging.error(f"Error updating document in {collection_name}: {e}")
            return False
    
    def delete_one(self, collection_name: str, filter_dict: Dict[str, Any], db_name: str = None) -> bool:
        """删除单个文档"""
        collection = self.get_collection(collection_name, db_name)
        if collection is None:
            return False
        
        try:
            result = collection.delete_one(filter_dict)
            return result.deleted_count > 0
        except PyMongoError as e:
            logging.error(f"Error deleting document from {collection_name}: {e}")
            return False
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None 