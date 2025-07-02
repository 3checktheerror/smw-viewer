import logging
from pymongo import ASCENDING
from pymongo.errors import BulkWriteError

from backend.app.utils.mongo_client import MongoDBClient
from backend.app.utils.time_utils import TimeUtils

logging.basicConfig(level=logging.INFO)


def initialize_bad_tokens_collection():
    """
    Initializes the 'bad_tokens' collection in the 'token' database,
    and creates a unique index on 'address' and 'chain'.
    """
    try:
        mongo_client = MongoDBClient()
        db_name = 'history'
        collection_name = 'smw_incremental'
        
        db = mongo_client._get_database(db_name)
        if db is None:
            logging.error(f"Failed to get database: {db_name}")
            return

        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name)
            logging.info(f"Collection '{collection_name}' created in db '{db_name}'.")

        collection = mongo_client.get_collection(collection_name, db_name)
        if collection is None:
            logging.error(f"Failed to get collection: {collection_name}")
            return
            
        index_name = "address_1_chain_1"
        if index_name not in collection.index_information():
            collection.create_index([("address", ASCENDING), ("chain", ASCENDING)], unique=True, name=index_name)
            logging.info(f"Created unique index on ('address', 'chain') for collection '{collection_name}'.")
        else:
            logging.info(f"Index '{index_name}' already exists on collection '{collection_name}'.")

    except Exception as e:
        logging.error(f"Error initializing 'bad_tokens' collection: {e}")


def insert_mock_data():
    """Inserts mock data into the 'bad_tokens' collection."""
    logging.info("Attempting to insert mock bad tokens...")
    try:
        mongo_client = MongoDBClient()
        collection = mongo_client.get_collection("smw_incremental", db_name="history")
        if collection is None:
            logging.error("Failed to get 'bad_tokens' collection for mock data insertion.")
            return

        mock_tokens = [
            {"address": "4pu2UjYKCMqqg79gx5bG8qG5nvqfp3iQBEjH2UstnVWs", "chain": "solana"},
            {"address": "Fvh4Hy8BrMX64TYSYTpHe2KSHeocRbTjaBMjaiwVqio", "chain": "solana"},
            {"address": "56S9p39Mw8iyNJM9FhBpkZsbFXteUh6GgCuNWzkNc7Qw", "chain": "solana"},
            {"address": "BFPLjqdwtBxQT1hL3aam6qRzbLykNnjLTpwwfyzBZaim", "chain": "solana"},
        ]

        documents = [{**token, "store_date": TimeUtils.get_cur_bg_date()} for token in mock_tokens]

        try:
            result = collection.insert_many(documents, ordered=False)
            logging.info(f"Successfully inserted {len(result.inserted_ids)} mock tokens.")
        except BulkWriteError as e:
            inserted_count = e.details.get('nInserted', 0)
            if inserted_count > 0:
                logging.info(f"Inserted {inserted_count} new mock tokens. Some duplicates were ignored.")
            else:
                logging.info("All mock tokens already exist in the blacklist.")

    except Exception as e:
        logging.error(f"Error inserting mock data: {e}")


if __name__ == "__main__":
    logging.info("Running bad_tokens collection initialization script...")
    # initialize_bad_tokens_collection()
    insert_mock_data()
    logging.info("Script finished.")
