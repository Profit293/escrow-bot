from dotenv import load_dotenv
import os
import json
from dataclasses import dataclass
from typing import Dict, List, Any

load_dotenv()

@dataclass
class Config:
    telegram_bot_token: str
    encryption_key: str
    deposit_addresses: Dict[str, Any]
    admin_telegram_ids: List[int]
    admin_username: str
    blockcypher_api_key: str
    is_render: bool
    database_path: str
    webhook_url: str
    webhook_path: str
    port: int
    webhook_secret: str

def load_deposit_addresses() -> Dict[str, Any]:
    """Load deposit addresses from secret files or environment"""
    secret_paths = [
        '/etc/secrets/deposit_addresses.json',
        'deposit_addresses.json',
        './deposit_addresses.json'
    ]
    
    for path in secret_paths:
        try:
            with open(path, 'r') as f:
                addresses = json.load(f)
                print(f"✅ Deposit addresses loaded from {path}")
                return addresses
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON from {path}: {e}")
            continue
    
    env_json = os.getenv('DEPOSIT_ADDRESSES_JSON')
    if env_json:
        try:
            addresses = json.loads(env_json)
            print("✅ Deposit addresses loaded from environment variable")
            return addresses
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON from environment: {e}")
    
    print("⚠️ Warning: deposit_addresses.json not found, using empty dict")
    return {}

def load_config() -> Config:
    """Load configuration from environment variables"""
    
    # Parse admin IDs
    admin_telegram_ids = []
    admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "")
    if admin_ids_str:
        try:
            admin_telegram_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
        except ValueError:
            print("⚠️ Invalid ADMIN_TELEGRAM_IDS format. Using empty list")
    
    # Get required values
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    encryption_key = os.getenv("ENCRYPTION_KEY", "")
    
    if not telegram_bot_token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN is not set in environment")
    if not encryption_key:
        raise ValueError("❌ ENCRYPTION_KEY is not set in environment")
    
    return Config(
        telegram_bot_token=telegram_bot_token,
        encryption_key=encryption_key,
        deposit_addresses=load_deposit_addresses(),
        admin_telegram_ids=admin_telegram_ids,
        admin_username=os.getenv("ADMIN_USERNAME", ""),
        blockcypher_api_key=os.getenv("BLOCKCYPHER_API_KEY", ""),
        is_render=os.getenv("RENDER") == "true",
        database_path=os.getenv("DATABASE_PATH", "escrow_data.db"),
        webhook_url=os.getenv("WEBHOOK_URL", ""),
        webhook_path=os.getenv("WEBHOOK_PATH", "/webhook"),
        port=int(os.getenv("PORT", "10000")),
        webhook_secret=os.getenv("WEBHOOK_SECRET", "secret")
    )