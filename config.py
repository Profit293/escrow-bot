from dotenv import load_dotenv
import os
import json

load_dotenv()

def load_deposit_addresses():
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

class Config:
    bot_token = os.getenv("BOT_TOKEN", "")
    encryption_key = os.getenv("ENCRYPTION_KEY", "")
    
    deposit_addresses = load_deposit_addresses()
    
    admin_telegram_ids = []
    admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "")
    if admin_ids_str:
        try:
            admin_telegram_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
        except ValueError:
            print("⚠️ Invalid ADMIN_TELEGRAM_IDS format. Using empty list")
    
    admin_username = os.getenv("ADMIN_USERNAME", "")
    blockcypher_api_key = os.getenv("BLOCKCYPHER_API_KEY", "")
    
    is_render = os.getenv("RENDER") == "true"
    
    # ВСЕГДА используем SQLite
    database_path = os.getenv("DATABASE_PATH", "escrow_data.db")
    database_url = None  # Не используем PostgreSQL

def load_config():
    config = Config()
    
    if not config.bot_token:
        raise ValueError("❌ BOT_TOKEN is not set in .env")
    if not config.encryption_key:
        raise ValueError("❌ ENCRYPTION_KEY is not set in .env")
    
    # УБРАЛИ проверку DATABASE_URL - используем только SQLite
    if not config.database_path:
        raise ValueError("❌ DATABASE_PATH is required")
    
    return config