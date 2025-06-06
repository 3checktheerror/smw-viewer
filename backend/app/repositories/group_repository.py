"""
钱包分组仓储类
"""
import motor.motor_asyncio


class GroupRepository():
    """钱包分组仓储类"""
    
    def __init__(self, database: motor.motor_asyncio.AsyncIOMotorDatabase):
        super().__init__(database, "wallet_groups")
