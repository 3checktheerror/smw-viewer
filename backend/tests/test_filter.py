import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app.utils.mongo_client import MongoDBClient

def rename_listed_count_to_statuses_count():
    """
    Renames 'listed_count' to 'statuses_count' in all documents in 'kol_info' collection.
    """
    mongo_client = MongoDBClient()
    collection_name = "kol_info"
    db_name = "kol"

    filter_dict = {"listed_count": {"$exists": True}}
    update_dict = {"$rename": {"listed_count": "statuses_count"}}

    updated_count = mongo_client.update_many(
        collection_name=collection_name,
        db_name=db_name,
        filter_dict=filter_dict,
        update_dict=update_dict
    )

    print(f"Updated {updated_count} documents in '{collection_name}' collection.")

if __name__ == "__main__":
    rename_listed_count_to_statuses_count()
