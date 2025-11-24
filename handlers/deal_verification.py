from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database.db import get_deal_by_id, get_user_by_id
from utils.crypto_utils import decrypt_data
from keyboards import get_deal_info_keyboard, get_contact_admin_keyboard
from config import load_config
import logging

router = Router()
config = load_config()
logger = logging.getLogger("escrow_bot")

@router.message(F.text == "/verify_deal")
async def start_verification(message: Message):
    await message.answer(
        "🔍 <b>Enter deal ID to verify</b>:\n\n"
        "Example: <code>ABC123</code>",
        parse_mode="HTML"
    )

@router.message(F.text.regexp(r'^[A-Z0-9]{6}$'))
async def process_deal_id(message: Message):
    deal_id = message.text.strip().upper()
    deal = await get_deal_by_id(deal_id)
    
    if not deal:
        await message.answer(
            "❌ <b>Deal not found!</b>\n\n"
            "Check the ID correctness and try again.",
            parse_mode="HTML"
        )
        return
    
    buyer = await get_user_by_id(deal["buyer_id"])
    seller = await get_user_by_id(deal["seller_id"])
    
    buyer_username = buyer["username"] if buyer else f"user_{deal['buyer_id']}"
    seller_username = seller["username"] if seller else f"user_{deal['seller_id']}"
    
    try:
        description = decrypt_data(deal["description"])
    except:
        description = "Decryption error"
    
    status_map = {
        "AWAITING_PAYMENT": "⏳ Awaiting payment",
        "PAID": "💰 Payment confirmed",
        "SHIPPED": "🚚 Item shipped",
        "COMPLETED": "✅ Deal completed"
    }
    
    status_text = status_map.get(deal["status"], deal["status"])
    
    deal_info = (
        f"🆔 <b>Deal ID</b>: <code>{deal['id']}</code>\n"
        f"💰 <b>Amount</b>: {deal['amount']} {deal['crypto_type']}\n"
        f"📦 <b>Item</b>: {description}\n"
        f"📥 <b>Deposit address</b>: <code>{deal['deposit_address']}</code>\n"
        f"📊 <b>Status</b>: {status_text}\n\n"
        f"👥 <b>Participants</b>:\n"
        f"• Buyer: @{buyer_username}\n"
        f"• Seller: @{seller_username}"
    )
    
    role = "buyer" if message.from_user.id == deal["buyer_id"] else "seller"
    
    keyboard = get_deal_info_keyboard(
        deal_id, 
        role, 
        deal["deposit_address"], 
        deal["crypto_type"]
    ) if deal["status"] != "COMPLETED" else None
    
    await message.answer(
        deal_info,
        reply_markup=keyboard or get_contact_admin_keyboard(deal_id),
        parse_mode="HTML"
    )

# ⚠️ УДАЛЕН дублирующий обработчик contact_admin - он теперь в user_actions.py