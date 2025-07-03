import logging
from collections import defaultdict
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import BulkWriteError
from backend.app.api.schemas.common_schemas import CommonResult
from backend.app.api.schemas.token_schemas import BadTokenAddRequest, BadTokenDeleteRequest, BadTokenInfo
from backend.app.api.schemas.wallet_schemas import WalletOperation, SMWHistoryModel, SMWIncrementalModel, WalletAddress
from backend.app.api.schemas.kol_schemas import KOLInfo
from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.time_utils import TimeUtils
from backend.app.services.smw.smw_daily_service import SMWDailyService
from backend.app.services.smw.smw_history_manager import SMWHistoryManager
from backend.app.services.smw.smw_incremental_manager import SMWIncrementalManager
from backend.app.services.smw.smw_statistic_manager import SMWStatisticManager

router = APIRouter(prefix="/smw", tags=["SMW"])



@router.post("/bad_tokens/add", summary="Add bad tokens", response_model=CommonResult)
def add_bad_tokens(
    request: BadTokenAddRequest,
):
    """
    Adds one or more tokens to the bad tokens blacklist.
    - **tokens**: A list of token objects, each with `address` and `chain`.
    """
    collection = MongoDBClient().get_collection(collection_name="bad_tokens", db_name="token")
    if not request.tokens:
        raise HTTPException(status_code=400, detail="No tokens provided to add.")

    documents = [{**token.dict(), "store_time": TimeUtils.get_current_ts()} for token in request.tokens]
    
    try:
        result = collection.insert_many(documents, ordered=False)
        return CommonResult().success(data={"message": f"Successfully inserted {len(result.inserted_ids)} tokens."})
    except BulkWriteError as e:
        if e.details['nInserted'] > 0:
             return CommonResult().success(data={"message": f"Inserted {e.details['nInserted']} new tokens. Some duplicates were ignored."})
        else:
            raise HTTPException(status_code=400, detail="All provided tokens are already in the blacklist.")
    except Exception as e:
        logging.error(f"Error adding bad tokens: {e}")
        raise HTTPException(status_code=500, detail="Failed to add bad tokens.")

@router.post("/bad_tokens/delete", summary="Delete bad tokens", response_model=CommonResult)
def delete_bad_tokens(
    request: BadTokenDeleteRequest,
):
    """
    Deletes one or more tokens from the bad tokens blacklist.
    - **tokens**: A list of token objects, each with `address` and `chain`.
    """
    collection = MongoDBClient().get_collection(collection_name="bad_tokens", db_name="token")
    if not request.tokens:
        raise HTTPException(status_code=400, detail="No tokens provided to delete.")

    conditions = [{"address": token.address, "chain": token.chain} for token in request.tokens]
    
    try:
        result = collection.delete_many({"$or": conditions})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="No matching tokens found to delete.")
        return CommonResult().success(data={"message": f"Successfully deleted {result.deleted_count} tokens."})
    except Exception as e:
        logging.error(f"Error deleting bad tokens: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete bad tokens.")

@router.get("/bad_tokens/list", summary="List all bad tokens", response_model=CommonResult[List[BadTokenInfo]])
def list_bad_tokens():
    """
    Retrieves a list of all blacklisted tokens, including their chain, address, and store time.
    """
    mongo_client = MongoDBClient()
    try:
        tokens = mongo_client.find_many(
            collection_name="bad_tokens",
            db_name="token",
            projection={"address": 1, "chain": 1, "store_time": 1, "_id": 0}
        )
        return CommonResult().success(data=tokens)
    except Exception as e:
        logging.error(f"Error fetching bad tokens: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch bad tokens.")

@router.post("/sync_incr_wallets", summary="Sync all incremental wallets", response_model=CommonResult)
def sync_incr_wallets(request: List[WalletOperation]):
    """Synchronize incremental wallets based on the provided operations."""
    try:
        SMWDailyService.sync_incremental_wallets(request)
        return CommonResult().success(data={"message": "Incremental wallets synchronized successfully."})
    except Exception as e:
        logging.error(f"Error syncing incremental wallets: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync incremental wallets.")

@router.post("/sync_smw", summary="Sync all smart wallets", response_model=CommonResult)
def sync_smw(request: List[WalletOperation]):
    """Synchronize smart wallets based on the provided operations."""
    try:
        SMWDailyService.sync_smart_wallets(request)
        return CommonResult().success(data={"message": "Smart wallets synchronized successfully."})
    except Exception as e:
        logging.error(f"Error syncing smart wallets: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync smart wallets.")

@router.get("/history_wallets/list", summary="List all history smart wallets", response_model=CommonResult[List[SMWHistoryModel]])
def list_history_wallets():
    """Retrieve all wallets from smw_history collection with daily statistics."""
    try:
        wallets = SMWHistoryManager.get_smw_history_wallets()
        return CommonResult().success(data=wallets)
    except Exception as e:
        logging.error(f"Error fetching history wallets: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history wallets.")

@router.get("/incremental_wallets/list", summary="List today's incremental wallets", response_model=CommonResult[List[SMWIncrementalModel]])
def list_incremental_wallets():
    """Retrieve today's incremental wallets with daily statistics."""
    try:
        wallets = SMWIncrementalManager.get_daily_incremental_wallets()
        return CommonResult().success(data=wallets)
    except Exception as e:
        logging.error(f"Error fetching incremental wallets: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch incremental wallets.")

@router.get("/get_avg_buy_stats", summary="Average buy volume statistics for smart wallets", response_model=CommonResult)
def get_avg_buy_stats():
    """Generate and get average buy volume statistics for all smart wallets."""
    try:
        mongo_client = MongoDBClient()
        wallet_docs = mongo_client.find_many(
            collection_name="smw_history",
            db_name="history",
            projection={"chain": 1, "address": 1, "_id": 0},
        )
        stats = SMWStatisticManager.get_smw_avg_buy_statistics(wallet_docs)
        return CommonResult().success(data=stats)
    except Exception as e:
        logging.error(f"Error generating avg buy statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate avg buy statistics.")


@router.post("/history_wallets/add", summary="Add history smart wallets", response_model=CommonResult)
def add_history_wallets(request: List[WalletAddress]):
    """Add smart wallets to the smw_history collection after deduplicating by chain."""
    if not request:
        raise HTTPException(status_code=400, detail="No wallets provided to add.")

    unique_by_chain = defaultdict(set)
    for wallet in request:
        if wallet.chain and wallet.address:
            unique_by_chain[wallet.chain].add(wallet.address)

    if not unique_by_chain:
        raise HTTPException(status_code=400, detail="No valid wallet data found.")

    current_bg_date = TimeUtils.get_cur_bg_date()

    documents = [
        {
            "chain": chain,
            "address": addr,
            "store_date": current_bg_date,
            "out_tag": 1,
        }
        for chain, addr_set in unique_by_chain.items()
        for addr in addr_set
    ]

    if not documents:
        raise HTTPException(status_code=400, detail="No valid documents to insert.")

    mongo_client = MongoDBClient()
    try:
        inserted_ids = mongo_client.insert_many(
            collection_name="smw_history",
            documents=documents,
            db_name="history",
        )
        return CommonResult().success(data={"inserted_count": len(inserted_ids)})
    except Exception as e:
        logging.error(f"Error adding history wallets: {e}")
        raise HTTPException(status_code=500, detail="Failed to add history wallets.")

@router.post("/history_wallets/delete", summary="Delete history smart wallets", response_model=CommonResult)
def delete_history_wallets(request: List[WalletAddress]):
    """Batch delete smart wallets from the smw_history collection."""
    if not request:
        raise HTTPException(status_code=400, detail="No wallets provided to delete.")

    conditions = [
        {"address": wallet.address, "chain": wallet.chain}
        for wallet in request
        if wallet.address and wallet.chain
    ]

    if not conditions:
        raise HTTPException(status_code=400, detail="No valid wallet data provided.")

    mongo_client = MongoDBClient()
    try:
        deleted_count = mongo_client.delete_many(
            collection_name="smw_history",
            filter_dict={"$or": conditions},
            db_name="history",
        )
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="No matching wallets found to delete.")
        return CommonResult().success(data={"deleted_count": deleted_count})
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting history wallets: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete history wallets.")

@router.get("/kol_info/list", summary="List all KOL info", response_model=CommonResult[List[KOLInfo]])
def list_kol_info():
    """Retrieve all KOL information records from the kol_info collection."""
    mongo_client = MongoDBClient()
    try:
        infos = mongo_client.find_many(
            collection_name="kol_info",
            db_name="kol",
            projection={
                "chain": 1,
                "address": 1,
                "twitter_username": 1,
                "twitter_name": 1,
                "avatar": 1,
                "followers_count": 1,
                "statuses_count": 1,
                "_id": 0,
            },
        )
        return CommonResult().success(data=infos)
    except Exception as e:
        logging.error(f"Error fetching KOL info: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch KOL info.")