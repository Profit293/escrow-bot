from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.db import get_deal_by_id, update_deal_status, get_user_by_id
from utils.crypto_utils import decrypt_data
from utils.notifications import notify_admins, notify_seller
from config import load_config
from keyboards import get_admin_payment_keyboard
import logging

router = Router()
config = load_config()
logger = logging.getLogger("escrow_bot")

@router.callback_query(F.data.startswith("payment_confirmed:"))
async def handle_payment_confirmation(callback: CallbackQuery):
    deal_id = callback.data.split(":")[1]
    deal = await get_deal_by_id(deal_id)
    
    if not deal:
        await callback.answer("❌ Deal not found", show_alert=True)
        return
    
    # Decrypt description
    try:
        description = decrypt_data(deal["description"])
    except Exception as e:
        description = "Decryption error"
        logger.error(f"❌ Error decrypting description for deal {deal_id}: {str(e)}")
    
    # Update deal status
    await update_deal_status(deal_id, "PAID_WAITING_ADMIN")
    
    # Get user data for notifications
    buyer = await get_user_by_id(deal["buyer_id"])
    seller = await get_user_by_id(deal["seller_id"])
    
    buyer_username = buyer["username"] if buyer else f"user_{deal['buyer_id']}"
    seller_username = seller["username"] if seller else f"user_{deal['seller_id']}"
    
    # ✅ FIXED: Notify administrators with keyboard for payment confirmation
    admin_message = (
        f"🚨 <b>NEW PAYMENT AWAITING CONFIRMATION</b>\n\n"
        f"🆔 <b>Deal ID</b>: <code>{deal_id}</code>\n"
        f"💰 <b>Amount</b>: {deal['amount']} {deal['crypto_type']}\n"
        f"📦 <b>Item</b>: {description}\n"
        f"👤 <b>Buyer</b>: @{buyer_username}\n"
        f"🤝 <b>Seller</b>: @{seller_username}\n"
        f"🔗 <b>Deposit address</b>: <code>{deal['deposit_address']}</code>\n\n"
        f"<i>Buyer reported payment. Please confirm via blockchain or manually.</i>"
    )

    # ✅ FIXED: Send to each admin individually with keyboard
    admin_keyboard = get_admin_payment_keyboard(deal_id, deal["crypto_type"], deal["deposit_address"])
    
    for admin_id in config.admin_telegram_ids:
        try:
            await callback.bot.send_message(
                admin_id,
                admin_message,
                parse_mode="HTML",
                reply_markup=admin_keyboard
            )
            logger.info(f"✅ Admin notification with buttons sent to {admin_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send notification to admin {admin_id}: {e}")
    
    # ✅ FIXED: Notify seller if they are registered in bot
    if seller:
        seller_message = (
            f"💰 <b>Buyer reported payment for deal {deal_id}!</b>\n\n"
            f"🆔 Deal ID: <code>{deal_id}</code>\n"
            f"💰 Amount: {deal['amount']} {deal['crypto_type']}\n"
            f"📦 Item: {description}\n\n"
            f"⏳ <b>Administrator is verifying the payment...</b>\n\n"
            f"You will receive another notification when payment is confirmed."
        )
        await notify_seller(callback.bot, seller, seller_message, deal_id)
    
    # Update user message
    await callback.answer("✅ Your payment has been sent for verification", show_alert=True)
    await callback.message.edit_text(
        f"✅ <b>Payment reported for deal {deal_id}!</b>\n\n"
        f"💰 Amount: {deal['amount']} {deal['crypto_type']}\n"
        f"📦 Item: {description}\n\n"
        f"⏳ <b>Administrator is verifying your payment...</b>\n\n"
        f"You will receive a notification when payment is confirmed.",
        parse_mode="HTML",
        reply_markup=None
    )

@router.callback_query(F.data.startswith("contact_admin:"))
async def handle_contact_admin(callback: CallbackQuery):
    deal_id = callback.data.split(":")[1]
    deal = await get_deal_by_id(deal_id) if deal_id != "general" else None
    
    # Form message for administrator
    if deal:
        try:
            description = decrypt_data(deal["description"])
        except:
            description = deal["description"]
            
        message_text = (
            f"🆘 <b>Help request for deal {deal_id}</b>\n\n"
            f"User: @{callback.from_user.username}\n"
            f"Deal: {description}\n"
            f"Amount: {deal['amount']} {deal['crypto_type']}"
        )
    else:
        message_text = (
            f"🆘 <b>General help request</b>\n\n"
            f"User: @{callback.from_user.username}\n"
            f"Message: {callback.message.text}"
        )
    
    # Send to administrators (without keyboard for help requests)
    await notify_admins(callback.bot, message_text)
    
    # Show information to user
    if config.admin_username:
        await callback.answer(
            f"Administrator notified. You can contact them directly: @{config.admin_username}",
            show_alert=True
        )
    else:
        await callback.answer(
            "Administrator notified. Expect response within 30 minutes",
            show_alert=True
        )
    
    await callback.message.edit_text(
        "Administrator notified. Expect response",
        reply_markup=None
    )