"""
数据库连接管理
"""
import motor.motor_asyncio
import redis.asyncio as redis
from typing import AsyncGenerator
from motor.motor_asyncio import AsyncIOMotorClient
from backend.app.core.config import settings


class DatabaseManager:
    def __init__(self):
        self.mongodb_client: motor.motor_asyncio.AsyncIOMotorClient = None
        self.redis_client: redis.Redis = None
        self.redis_cache_client: redis.Redis = None
    
    async def connect_to_mongo(self):
        if self.mongodb_client is None:
            self.mongodb_client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_url)
    
    async def close_mongo_connection(self):
        if self.mongodb_client:
            self.mongodb_client.close()
    
    async def connect_to_redis(self):
        self.redis_client = redis.from_url(settings.redis_url)
    
    async def close_redis_connection(self):
        if self.redis_client:
            await self.redis_client.close()


database_manager = DatabaseManager()


async def get_mongo() -> AsyncGenerator[AsyncIOMotorClient, None]:
    yield database_manager.mongodb_client


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    yield database_manager.redis_client