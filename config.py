from dotenv import load_dotenv
import os
import json

load_dotenv()

def load_deposit_addresses():
    """Load deposit addresses from secret files or environment"""
    # Пути, где Render размещает secret files
    secret_paths = [
        '/etc/secrets/deposit_addresses.json',  # Основной путь для secret files
        'deposit_addresses.json',               # Резервный путь
        './deposit_addresses.json'              # Текущая директория
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
    
    # Попробуем загрузить из переменной окружения как запасной вариант
    env_json = os.getenv('DEPOSIT_ADDRESSES_JSON')
    if env_json:
        try:
            addresses = json.loads(env_json)
            print("✅ Deposit addresses loaded from environment variable")
            return addresses
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON from environment: {e}")
    
    # Если файл не найден, создаем пустой
    print("⚠️ Warning: deposit_addresses.json not found, using empty dict")
    return {}

class Config:
    bot_token = os.getenv("BOT_TOKEN", "")
    encryption_key = os.getenv("ENCRYPTION_KEY", "")
    
    # Загружаем deposit addresses
    deposit_addresses = load_deposit_addresses()
    
    # Safe admin ID parsing
    admin_telegram_ids = []
    admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "")
    if admin_ids_str:
        try:
            admin_telegram_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
        except ValueError:
            print("⚠️ Invalid ADMIN_TELEGRAM_IDS format. Using empty list")
    
    admin_username = os.getenv("ADMIN_USERNAME", "")
    blockcypher_api_key = os.getenv("BLOCKCYPHER_API_KEY", "")
    
    # Database configuration - auto-detect environment
    is_render = os.getenv("RENDER") == "true"
    
    if is_render:
        # Render.com uses PostgreSQL
        database_url = os.getenv("DATABASE_URL", "")
        database_path = None  # Not used in Render
    else:
        # Local development uses SQLite
        database_path = os.getenv("DATABASE_PATH", "escrow_data.db").strip('"').strip("'")
        database_url = None  # Not used locally

def load_config():
    config = Config()
    
    # Critical settings validation
    if not config.bot_token:
        raise ValueError("❌ BOT_TOKEN is not set in .env")
    if not config.encryption_key:
        raise ValueError("❌ ENCRYPTION_KEY is not set in .env")
    
    # Environment-specific validation
    if config.is_render and not config.database_url:
        raise ValueError("❌ DATABASE_URL is required for Render.com deployment")
    if not config.is_render and not config.database_path:
        raise ValueError("❌ DATABASE_PATH is required for local development")
    
    return config