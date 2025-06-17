"""
应用配置管理
"""
from typing import Optional, List, Tuple, Dict
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用设置"""
    
    # 应用配置
    app_name: str = Field(default="Smart Wallet Dashboard", description="APP_NAME")
    app_version: str = Field(default="1.0.0", description="APP_VERSION")
    debug: bool = Field(default=True, description="DEBUG")

    # 3级队列配置
    queue_db: str = Field(default="smw", description="smw 3 layer queue db")
    queue_1: str = Field(default="que_1", description="Top smart wallet queue")
    queue_2: str = Field(default="que_2", description="Middle smart wallet queue")
    queue_3: str = Field(default="que_3", description="Down smart wallet queue")
    
    # MongoDB 配置
    mongodb_url: str = Field(default="mongodb://debot_wallet:debot_wallet_123@23.239.109.74:27017/?retryWrites=true&w=majority&appName=Cluster0")
    mongodb_token_db: str = Field(default="token")
    mongodb_wallet_db: str = Field(default="wallet")
    daily_onchain_token_collection: str = Field(default="onchain_token")
    daily_rank_token_collection: str = Field(default="rank_token")
    daily_wallet_collection: str = Field(default="daily_wallet")
    
    # PostgreSQL 配置
    postgres_user: str = Field(default="postgres", description="PostgreSQL username")
    postgres_password: str = Field(default="ng5tUYb9k0H1fAD7", description="PostgreSQL password")
    postgres_host: str = Field(default="23.239.109.74", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_db: str = Field(default="diting_database", description="PostgreSQL database name")
    
    # Redis 配置
    redis_url: str = Field(default="redis://localhost:6379/0", description="REDIS_URL")
    
    # Redis Sentinel 配置 (用于热门代币查找器)
    redis_sentinel_addrs: List[Tuple[str, int]] = Field(
        default=[
            ("107.181.245.6", 26379),
            ("23.239.109.70", 26379),
            ("23.239.109.74", 26379),
        ]
    )
    redis_sentinel_password: str = Field(default="P@mao123", description="REDIS_SENTINEL_PASSWORD")
    redis_master_password: str = Field(default="P@mao123", description="REDIS_MASTER_PASSWORD")
    redis_master_name: str = Field(default="mymaster", description="REDIS_MASTER_NAME")
    redis_db_num: int = Field(default=0, description="REDIS_DB_NUM")
    
    # 热门代币查找器配置
    hot_token_scan_interval_seconds: int = Field(default=120, description="HOT_TOKEN_SCAN_INTERVAL_SECONDS")  # 2分钟
    hot_token_stream_read_count: int = Field(default=100, description="HOT_TOKEN_STREAM_READ_COUNT")
    hot_token_thread_pool_size: int = Field(default=5, description="HOT_TOKEN_THREAD_POOL_SIZE")
    lookup_worker_size: int = Field(default=25, description="HOT_TOKEN_BATCH_SIZE")  # Redis批量查询大小
    
    # 热门代币过滤阈值
    hot_token_market_cap_threshold: int = Field(default=100000, description="HOT_TOKEN_MARKET_CAP_THRESHOLD")
    hot_token_dev_share_threshold: float = Field(default=0.5, description="HOT_TOKEN_DEV_SHARE_THRESHOLD")
    hot_token_top10_share_threshold: float = Field(default=0.5, description="HOT_TOKEN_TOP10_SHARE_THRESHOLD")
    hot_token_volume_threshold: int = Field(default=200000, description="HOT_TOKEN_VOLUME_THRESHOLD")
    
    # 热门代币数据源配置
    hot_token_streams: List[str] = Field(
        default=[
            "new_token_stream:four_meme",
            "new_token_stream:boopfun", 
            "new_token_stream:pump",
            "new_token_stream:believe"
        ]
    )
    hot_token_chain_mapping: dict = Field(
        default={
            "four_meme": "bsc",
            "boopfun": "solana", 
            "pump": "solana",
            "believe": "solana"
        }
    )
    hot_token_stats_key_prefix: str = Field(default="token_tag_stats:", description="HOT_TOKEN_STATS_KEY_PREFIX")
    
    # Debot 平台配置
    debot_api_url: str = Field(default="https://preapi.debot.ai", description="DEBOT_API_URL")
    
    # 日志配置
    log_level: str = Field(default="INFO", description="LOG_LEVEL")
    log_format: str = Field(default="json", description="LOG_FORMAT")
    
    # 监控配置
    metrics_enabled: bool = Field(default=True, description="METRICS_ENABLED")
    metrics_port: int = Field(default=9090, description="METRICS_PORT")
    
    # 定时任务调度器配置
    scheduler_timezone: str = Field(default="UTC", description="SCHEDULER_TIMEZONE")
    find_daily_token_interval_minutes: int = Field(default=2, description="FIND_DAILY_TOKEN_INTERVAL_MINUTES")

    # PNL Map
    daily_pnl_map: Dict[str, float] = Field(default={
        'bsc': 0.35,
        'base': 0.50,
        'solana': 0.35
    })

    non_daily_pnl_map: Dict[str, float] = Field(default={
        'bsc': 0.3,
        'base': 0.45,
        'solana': 0.3
    })




    
    class Config:
        description_file = ".description"
        case_sensitive = False


# 全局配置实例
settings = Settings() 