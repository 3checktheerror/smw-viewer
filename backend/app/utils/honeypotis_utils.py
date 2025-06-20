class HoneyPotIsUtils:
    @staticmethod
    def is_honeypot(token: str, pair: str, timeout: float = 20.0) -> bool:
        """
        Query honeypot.is public API to determine whether the token is a honeypot.

        Args:
            token: The token (contract) address.
            pair:  The liquidity pair address associated with the token.
            timeout: HTTP timeout in seconds.

        Returns:
            True  -> the token *is* a honeypot (cannot sell / scam).
            False -> the token is *not* a honeypot.
        """
        from backend.app.utils.http_utils import ThirdPartyHTTPUtils  # local import to avoid circular dependency
        import logging

        if not token or not pair:
            logging.warning("HoneyPotIsUtils.is_honeypot called with empty token or pair")
            return False

        try:
            url = f"https://api.honeypot.is/v2/IsHoneypot?address={token}&pair={pair}"
            response = ThirdPartyHTTPUtils.get(url=url, timeout=timeout)

            # Successful response is expected to be a dict containing "honeypotResult"
            if isinstance(response, dict):
                honeypot_result = response.get("honeypotResult") or {}
                is_honeypot_flag = honeypot_result.get("isHoneypot")
                # Explicitly return bool if flag is bool, else False
                if isinstance(is_honeypot_flag, bool):
                    return is_honeypot_flag

            # If response is not in expected format, treat as not honeypot (fail-open)
            logging.warning(f"Unexpected response from honeypot.is for {token}: {response}")
            return False
        except Exception as e:
            # Log and fallback to conservative assumption that token might be a honeypot
            logging.error(f"Error querying honeypot.is for {token}: {e}")
            return True