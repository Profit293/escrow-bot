import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from database.db import init_db
from config import load_config

# Logger configuration with console output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("escrow_bot")

load_dotenv()

async def main():
    try:
        logger.info("🚀 Starting bot launch...")
        
        config = load_config()
        logger.debug(f"Settings loaded: {config.__dict__}")
        
        # ✅ ДОБАВЛЕНО: Проверяем загруженные адреса
        if config.deposit_addresses:
            logger.info(f"✅ Loaded {len(config.deposit_addresses)} deposit addresses")
            # Логируем какие валюты загружены (без самих адресов для безопасности)
            currencies = list(config.deposit_addresses.keys())
            logger.info(f"✅ Available currencies: {currencies}")
        else:
            logger.warning("⚠️ No deposit addresses loaded")
        
        # Token validation
        if not config.bot_token or len(config.bot_token) < 10:
            logger.error("❌ ERROR: Invalid bot token. Check .env file")
            return
        
        logger.info("🔄 Initializing database...")
        await init_db()
        
        bot = Bot(token=config.bot_token)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Dynamic handlers import
        try:
            logger.info("🔄 Connecting handlers...")
            from handlers import start, deal_creation, deal_verification, admin, main_menu, user_actions
            
            # Checking router availability
            for handler_name, handler in [
                ("start", start),
                ("deal_creation", deal_creation),
                ("deal_verification", deal_verification),
                ("admin", admin),
                ("main_menu", main_menu),
                ("user_actions", user_actions)
            ]:
                if hasattr(handler, 'router'):
                    logger.debug(f"✅ Router connected: {handler_name}")
                    dp.include_router(handler.router)
                else:
                    logger.error(f"❌ Error: No router attribute in {handler_name}")
            
            logger.info("✅ All handlers connected successfully")
            
        except Exception as e:
            logger.exception(f"❌ Error connecting handlers: {str(e)}")
            return
        
        # Environment-specific startup
        if config.is_render:
            logger.info("🌐 Starting in Render.com mode (webhook)")
            await start_webhook(bot, dp)
        else:
            logger.info("🌐 Starting in local mode (polling)")
            await start_polling(bot, dp)
            
    except Exception as e:
        logger.exception(f"❌ Critical error during startup: {str(e)}")
        raise

async def start_polling(bot, dp):
    """Start bot in polling mode (local development)"""
    logger.info("✅ Bot fully configured for local development")
    logger.info("🔄 Starting polling...")
    await dp.start_polling(bot)

async def start_webhook(bot, dp):
    """Start bot in webhook mode (Render.com)"""
    from aiogram.webhook.aiohttp_server import SimpleAiohttpRequestHandler, setup_aiohttp_app
    import aiohttp.web as web
    
    WEBHOOK_PATH = "/webhook"
    WEBHOOK_URL = f"{os.getenv('RENDER_EXTERNAL_URL', '')}{WEBHOOK_PATH}"
    
    # Set webhook
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"🔗 Webhook set to: {WEBHOOK_URL}")
    
    # Create web application
    app = web.Application()
    SimpleAiohttpRequestHandler(
        dispatcher=dp,
        bot=bot,
    ).register(app, path=WEBHOOK_PATH)
    
    setup_aiohttp_app(app, bot, dp)
    
    # Start web server
    port = int(os.getenv("PORT", 10000))
    logger.info(f"✅ Bot fully configured for Render.com")
    logger.info(f"🚀 Starting web server on port {port}...")
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    logger.info("✨ Starting Escrow Bot")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.exception(f"❌ Unhandled error: {str(e)}")
    finally:
        logger.info("ℹ️ Operation completed")