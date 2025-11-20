import requests

BLOCKCHAIN_APIS = {
    "BTC": "https://api.blockcypher.com/v1/btc/main",
    "LTC": "https://api.blockcypher.com/v1/ltc/main",
    "ETH": "https://api.etherscan.io/api"
}

def check_transaction(crypto_type: str, address: str, expected_amount: float) -> dict:
    try:
        if crypto_type in ["BTC", "LTC"]:
            url = f"{BLOCKCHAIN_APIS[crypto_type]}/addrs/{address}/full?limit=50"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for tx in data.get("txs", []):
                if tx.get("confirmations", 0) >= 3:
                    received = sum(
                        output["value"] for output in tx["outputs"]
                        if any(addr == address for addr in output["addresses"])
                    ) / 1e8
                    
                    if received >= expected_amount:
                        return {
                            "confirmed": True,
                            "tx_hash": tx["hash"],
                            "amount": received,
                            "confirmations": tx["confirmations"]
                        }
        
        elif crypto_type == "ETH":
            # For ETH, Etherscan API key is required (add to .env if needed)
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "sort": "desc"
            }
            response = requests.get(BLOCKCHAIN_APIS["ETH"], params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "1":
                for tx in data["result"]:
                    if int(tx["confirmations"]) >= 12:
                        value = int(tx["value"]) / 1e18
                        if value >= expected_amount:
                            return {
                                "confirmed": True,
                                "tx_hash": tx["hash"],
                                "amount": value,
                                "confirmations": int(tx["confirmations"])
                            }
        
        return {"confirmed": False}
    except Exception as e:
        return {"confirmed": False, "error": str(e)}