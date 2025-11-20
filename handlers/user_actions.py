from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.db import get_deal_by_id, update_deal_status
from utils.crypto_utils import decrypt_data
from config import load_config
from keyboards import get_admin_payment_keyboard, get_blockchain_url
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
    
    # Notify administrators
    for admin_id in config.admin_telegram_ids:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🚨 <b>New payment for confirmation</b>\n\n"
                f"🆔 <b>Deal ID</b>: <code>{deal_id}</code>\n"
                f"💰 <b>Amount</b>: {deal['amount']} {deal['crypto_type']}\n"
                f"📦 <b>Item</b>: {description}\n"
                f"👤 <b>Buyer</b>: @{callback.from_user.username or callback.from_user.id}\n"
                f"🤝 <b>Seller</b>: @{deal['seller_username']}\n"
                f"🔗 <b>Deposit address</b>: <code>{deal['deposit_address']}</code>",
                parse_mode="HTML",
                reply_markup=get_admin_payment_keyboard(
                    deal_id, 
                    deal["crypto_type"],
                    deal["deposit_address"]
                )
            )
        except Exception as e:
            logger.error(f"❌ Error sending notification to admin {admin_id}: {str(e)}")
    
    # Update user message
    await callback.answer("✅ Your payment has been sent for verification", show_alert=True)
    await callback.message.edit_text(
        f"✅ Payment for deal <code>{deal_id}</code> has been sent for verification\n\n"
        "Administrator will confirm payment within 30 minutes",
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
    
    # Send to administrators
    for admin_id in config.admin_telegram_ids:
        try:
            await callback.bot.send_message(
                admin_id,
                message_text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Error sending help request to admin {admin_id}: {str(e)}")
    
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