import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiohttp import web
from config import load_config
from database.db import init_db
from handlers import start, deal_creation, deal_verification, admin, main_menu, user_actions

# Load configuration
config = load_config()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("escrow_bot")

async def main():
    """Main application entry point"""
    try:
        logger.info("✨ Starting Escrow Bot")
        logger.info("🚀 Starting bot launch...")
        
        # Log available currencies
        if config.deposit_addresses:
            available_currencies = list(config.deposit_addresses.keys())
            logger.info(f"✅ Available currencies: {available_currencies}")
        else:
            logger.warning("⚠️ No deposit addresses configured")

        # Initialize database
        logger.info("🔄 Initializing database...")
        await init_db()

        # Initialize bot and dispatcher - NEW STYLE for aiogram 3.3.0
        bot = Bot(token=config.telegram_bot_token, parse_mode=ParseMode.HTML)
        dp = Dispatcher()

        # Connect handlers
        logger.info("🔄 Connecting handlers...")
        await setup_handlers(dp)
        logger.info("✅ All handlers connected successfully")

        # Start in appropriate mode
        if config.is_render:
            await start_webhook(bot, dp)
        else:
            await start_polling(bot, dp)

    except Exception as e:
        logger.error(f"❌ Unhandled error: {str(e)}")
        raise
    finally:
        logger.info("ℹ️ Operation completed")

async def setup_handlers(dp: Dispatcher):
    """Setup all message handlers"""
    # Include all handler routers
    dp.include_router(start.router)
    dp.include_router(main_menu.router)
    dp.include_router(deal_creation.router)
    dp.include_router(deal_verification.router)
    dp.include_router(user_actions.router)
    dp.include_router(admin.router)

async def start_webhook(bot: Bot, dp: Dispatcher):
    """Start bot in webhook mode for Render.com"""
    try:
        logger.info("🌐 Starting in Render.com mode (webhook)")

        # Get webhook settings from environment
        webhook_url = config.webhook_url
        webhook_path = config.webhook_path
        render_port = config.port

        if not webhook_url or not webhook_path:
            raise ValueError("WEBHOOK_URL and WEBHOOK_PATH must be set in environment")

        # Reset webhook
        await bot.delete_webhook()
        await asyncio.sleep(1)

        # Set webhook
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types()
        )

        # Create aiohttp app
        app = web.Application()

        # Register webhook handler
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            # secret_token=config.webhook_secret,  # Optional
        )
        
        # Register webhook handler
        webhook_requests_handler.register(app, path=webhook_path)

        # Health check endpoint
        async def health_check(request):
            return web.Response(text="Bot is running!")

        app.router.add_get('/health', health_check)

        # Start web server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host='0.0.0.0', port=render_port)
        await site.start()

        logger.info(f"🚀 Webhook server started on port {render_port}")
        logger.info(f"📝 Webhook URL: {webhook_url}")
        logger.info("✅ Bot is ready and waiting for updates...")

        # Wait forever
        await asyncio.Event().wait()

    except Exception as e:
        logger.error(f"❌ Critical error during startup: {str(e)}")
        raise

async def start_polling(bot: Bot, dp: Dispatcher):
    """Start bot in polling mode for local development"""
    try:
        logger.info("🔍 Starting in local mode (polling)")
        
        # Delete webhook if exists
        await bot.delete_webhook()
        await asyncio.sleep(1)
        
        logger.info("✅ Bot is ready and waiting for messages...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Error in polling mode: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())