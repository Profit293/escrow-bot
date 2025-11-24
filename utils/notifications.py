# utils/notifications.py
import logging
from config import load_config

config = load_config()
logger = logging.getLogger("escrow_bot")

async def notify_admins(bot, message_text: str):
    """Send notification to all admins"""
    try:
        logger.info(f"🔔 Sending admin notification: {message_text[:100]}...")
        
        for admin_id in config.admin_telegram_ids:
            try:
                await bot.send_message(admin_id, message_text, parse_mode="HTML")
                logger.info(f"✅ Admin notification sent to {admin_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send notification to admin {admin_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Error in admin notification system: {e}")

async def notify_seller(bot, seller_data: dict, message_text: str, deal_id: str = None):
    """Send notification to seller if they are registered in bot"""
    try:
        if seller_data and seller_data.get("telegram_id"):
            await bot.send_message(seller_data["telegram_id"], message_text, parse_mode="HTML")
            logger.info(f"✅ Seller notified for deal {deal_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Error notifying seller for deal {deal_id}: {e}")
        return False