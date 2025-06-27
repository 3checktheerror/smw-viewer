import asyncio
import json
import logging
import math
from typing import List, Dict
from backend.app.api.schemas.kol_schemas import KOLResultModel
from backend.app.utils.http_utils import ThirdPartyHTTPUtils
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.redis_client import RedisClient
from backend.app.utils.thread_pool import ThreadPoolManager
from backend.app.utils.time_utils import TimeUtils


class KOLService:
    @classmethod
    def get_gmgn_daily_hot_tokens(cls) -> Dict[str, List[str]]:
        mongo_client = MongoDBClient()
        today_str = TimeUtils.get_cur_bg_date()
        dune_filter_dict = {
            "store_time": today_str,
            "rank": {"$gte": 1, "$lte": 20}
        }
        debot_filter_dict = {
            "store_time": today_str,
            "dog": {"$ne": None}
        }
        projection = {"token": 1, "chain": 1, "_id": 0}

        dune_docs = mongo_client.find_many(
            collection_name="dune_5047660",
            db_name="graph",
            filter_dict=dune_filter_dict,
            projection=projection
        )

        debot_docs = mongo_client.find_many(
            collection_name="debot_signal",
            db_name="graph",
            filter_dict=debot_filter_dict,
            projection=projection
        )

        all_docs = dune_docs + debot_docs

        if not all_docs:
            return {}

        result = {}
        for doc in all_docs:
            chain = doc.get("chain")
            token = doc.get("token")
            if chain and token:
                if chain not in result:
                    result[chain] = set()
                result[chain].add(token)

        for chain in result:
            result[chain] = list(result[chain])

        return result

    @classmethod
    async def process_kol_data(cls, kol_list: List[KOLResultModel]):
        """
        Processes a list of KOLs: upserts to MongoDB, updates info from an external API, and pushes to Redis.
        """
        cls._upsert_kol_data_to_mongo(kol_list)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, cls._update_kol_data_from_debot)
        await cls._push_kol_data_to_redis()

    @classmethod
    def _upsert_kol_data_to_mongo(cls, kol_list: List[KOLResultModel]):
        """Upserts KOL data into MongoDB using a thread pool."""
        mongo_client = MongoDBClient()
        today_str = TimeUtils.get_cur_bg_date()

        # De-duplicate KOL list based on (chain, address) to avoid unique constraint violations
        seen_keys = set()
        unique_kols = []
        for kol in reversed(kol_list):
            key = (kol.chain, kol.address)
            if key not in seen_keys:
                unique_kols.append(kol)
                seen_keys.add(key)
        unique_kols.reverse()

        def upsert_one_kol(kol: KOLResultModel):
            if not kol.address or not kol.chain or not kol.twitter_username or not kol.twitter_name or not kol.avatar:
                return
            
            update_data = {
                "chain": kol.chain,
                "avatar": kol.avatar,
                "address": kol.address,
                "twitter_username": kol.twitter_username,
                "twitter_name": kol.twitter_name,
                "store_time": today_str
            }
            
            update_payload = {
                "$set": {k: v for k, v in update_data.items() if v is not None},
                "$setOnInsert": {"followers_count": 0, "statuses_count": 0}
            }
            
            mongo_client.update_one(
                collection_name="kol_info",
                db_name="kol",
                filter_dict={"chain": kol.chain, "address": kol.address},
                update_dict=update_payload,
                upsert=True
            )

        with ThreadPoolManager(max_workers=30) as executor:
            executor.execute_tasks_and_wait(upsert_one_kol, [(kol,) for kol in unique_kols])

    @classmethod
    def _update_kol_data_from_debot(cls):
        """Fetches additional KOL info from Debot API and updates the database."""
        mongo_client = MongoDBClient()
        all_kols = mongo_client.find_many(
            collection_name="kol_info",
            db_name="kol",
            projection={"_id": 1, "twitter_username": 1, "twitter_name": 1, "address": 1, "chain": 1, "avatar": 1, "followers_count": 1}
        )
        if not all_kols:
            logging.info("No kols found to update from debot.")
            return

        def update_one_kol_sync(kol_doc: Dict):
            username = kol_doc.get("twitter_username")
            name = kol_doc.get("twitter_name")
            address = kol_doc.get("address")
            chain = kol_doc.get("chain")
            avatar = kol_doc.get("avatar")
            if not username or not name or not address or not chain or not avatar:
                return

            try:
                url = f"https://app.debot.ai/api/v1/nitter/userInfo/query?username={username}"
                data = ThirdPartyHTTPUtils.get(url=url)
                
                if data["code"] == 0:
                    profile_info = data["profileInfo"]
                    update_payload = {}

                    # Update avatar if current is invalid
                    current_avatar = kol_doc.get("avatar")
                    new_avatar = profile_info.get("avatar")
                    if new_avatar:
                        update_payload["avatar"] = new_avatar
                    
                    # Update followers count
                    followers_count = profile_info.get("followers_count")
                    statuses_count = profile_info.get("statuses_count")
                    if followers_count is not None:
                        update_payload["followers_count"] = followers_count
                    if statuses_count is not None:
                        update_payload["statuses_count"] = statuses_count
                    if update_payload:
                        mongo_client.update_one(
                            collection_name="kol_info",
                            db_name="kol",
                            filter_dict={"_id": kol_doc["_id"]},
                            update_dict={"$set": update_payload}
                        )
            except Exception as e:
                logging.error(f"Failed to update KOL data for {username}: {e}", exc_info=True)

        with ThreadPoolManager(max_workers=10) as executor:
            tasks_args = [(kol,) for kol in all_kols]
            executor.execute_tasks_and_wait(update_one_kol_sync, tasks_args)

    @classmethod
    async def _push_kol_data_to_redis(cls):
        """Pushes KOLs with followers > 5000 and statuses_count > 100 to a Redis queue."""
        mongo_client = MongoDBClient()
        kols_to_push = mongo_client.find_many(
            collection_name="kol_info",
            db_name="kol",
            filter_dict={"followers_count": {"$gt": 5000}, "statuses_count": {"$gt": 100}},
            projection={"chain": 1, "avatar": 1, "address": 1, "twitter_username": 1, "twitter_name": 1, "followers_count": 1, "statuses_count": 1, "_id": 0}
        )

        if not kols_to_push:
            logging.warning("No KOL data to push to Redis.")
            return

        redis_client = RedisClient.get_client()
        list_key = "kol_created_queue"
        expire_seconds = 86400

        try:
            async with redis_client.pipeline() as pipe:
                for item in kols_to_push:
                    json_str = json.dumps(item, ensure_ascii=False)
                    await pipe.rpush(list_key, json_str)
                if expire_seconds > 0:
                    await pipe.expire(list_key, expire_seconds)
                await pipe.execute()
            logging.info(f"Pushed {len(kols_to_push)} items to Redis list '{list_key}'.")
        except Exception as e:
            logging.error(f"Failed to push KOL data to Redis: {e}")

if __name__ == '__main__':
    asyncio.run(KOLService()._push_kol_data_to_redis())