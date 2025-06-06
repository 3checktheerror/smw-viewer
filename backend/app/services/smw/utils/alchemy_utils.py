import logging
from typing import Optional

from backend.app.core.config import settings
from backend.app.utils.http_utils import DebotHTTPUtils, ThirdPartyHTTPUtils


class AlchemyUtils:

    CHAIN_CONFIG = {
        "solana": {
            "url": "https://solana-mainnet.g.alchemy.com/v2/alcht_tbRnpTBkuBErvy54MUfbc8Kc3mwLB6",
            "payload_generator": lambda w: {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [w]
            },
            "response_parser": lambda r: r.get("result", {}).get("value", 0) / 10 ** 9
        },
        "bsc": {
            "url": "https://bnb-mainnet.g.alchemy.com/v2/TmD4Q_fYmD_UkRcMKbIOVJRLE48Teqn7",
            "payload_generator": lambda w: {
                "method": "eth_getBalance",
                "params": [w, "latest"],
                "id": 1,
                "jsonrpc": "2.0"
            },
            "response_parser": lambda r: int(r.get("result", "0x0"), 16) / 10 ** 18
        },
        "base": {
            "url": "https://base-mainnet.g.alchemy.com/v2/alcht_tbRnpTBkuBErvy54MUfbc8Kc3mwLB6/",
            "payload_generator": lambda w: {
                "method": "eth_getBalance",
                "params": [w, "latest"],
                "id": 1,
                "jsonrpc": "2.0"
            },
            "response_parser": lambda r: int(r.get("result", "0x0"), 16) / 10 ** 18
        }
    }

    @staticmethod
    def get_wallet_balance(wallet: str, chain: str) -> Optional[float]:
        config = AlchemyUtils.CHAIN_CONFIG.get(chain)
        if not config:
            logging.warning(f"Unsupported chain: {chain}")
            return None

        response = ThirdPartyHTTPUtils.post(
            config["url"],
            json_data=config["payload_generator"](wallet)
        )

        if response:
            return config["response_parser"](response)
        return None