from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    bot_token = os.getenv("BOT_TOKEN", "")
    encryption_key = os.getenv("ENCRYPTION_KEY", "")
    
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