import re
import string
import random
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from database.db import get_next_deposit_address, create_deal, create_user, get_user_by_username, get_user_by_id
from utils.crypto_utils import encrypt_data
from keyboards import (
    get_inline_crypto_keyboard,
    get_deal_info_keyboard,
    get_contact_admin_keyboard
)
from config import load_config
import logging

router = Router()
config = load_config()
logger = logging.getLogger("escrow_bot")

class CreateDeal(StatesGroup):
    waiting_for_seller = State()
    waiting_for_amount = State()
    waiting_for_description = State()

def generate_deal_id() -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=6))

def calculate_commission(original_amount: float) -> float:
    return round(original_amount * 1.02, 8)

def validate_crypto_amount(amount: str, crypto_type: str) -> float:
    try:
        value = float(amount)
        if value <= 0:
            raise ValueError("Amount must be positive")
        
        min_amounts = {
            "BTC": 0.0003,
            "LTC": 0.1
        }
        
        if value < min_amounts[crypto_type]:
            raise ValueError(f"Minimum amount for {crypto_type}: {min_amounts[crypto_type]}")
        
        return value
    except ValueError as e:
        raise ValueError(f"Invalid amount: {str(e)}") from e

@router.message(F.text == "/create_deal")
async def start_deal_creation(message: Message, state: FSMContext):
    await message.answer(
        "👤 <b>Enter seller's Telegram username</b> (without @):\n\n"
        "Example: <code>seller_username</code>",
        parse_mode="HTML"
    )
    await state.set_state(CreateDeal.waiting_for_seller)

@router.message(CreateDeal.waiting_for_seller)
async def process_seller(message: Message, state: FSMContext):
    seller_username = message.text.strip().lstrip('@')
    
    if not re.match(r'^[a-zA-Z0-9_]{5,32}$', seller_username):
        await message.answer(
            "❌ <b>Invalid username format!</b>\n\n"
            "Allowed characters: letters, numbers, underscore\n"
            "Length: 5-32 characters\n\n"
            "Try again:",
            parse_mode="HTML"
        )
        return
    
    seller = await get_user_by_username(seller_username)
    if not seller:
        await message.answer(
            "❌ <b>Seller not found!</b>\n\n"
            f"User with username @{seller_username} is not registered in the system.\n"
            "Ask the seller to start the bot first using /start command",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(
        seller_username=seller_username,
        seller_id=seller["id"]
    )
    
    await message.answer(
        "💰 <b>Select cryptocurrency for payment</b>\n\n"
        "✅ <b>Bitcoin (BTC)</b>\n"
        "• Most reliable cryptocurrency\n"
        "• Best for large amounts\n\n"
        "✅ <b>Litecoin (LTC)</b>\n"
        "• Fast transactions\n"
        "• Low transfer fees\n\n"
        "<i>Click the button with your preferred cryptocurrency</i>",
        parse_mode="HTML",
        reply_markup=get_inline_crypto_keyboard()
    )

@router.callback_query(F.data.startswith("crypto_"))
async def process_crypto_selection(callback: CallbackQuery, state: FSMContext):
    crypto_type = callback.data.replace("crypto_", "").upper()
    
    if crypto_type not in ["BTC", "LTC"]:
        await callback.answer("❌ Select BTC or LTC", show_alert=True)
        return
    
    await state.update_data(crypto_type=crypto_type)
    
    min_amounts = {
        "BTC": 0.0003,
        "LTC": 0.1
    }
    
    await callback.message.edit_text(
        f"✅ You selected: <b>{crypto_type}</b>\n\n"
        f"💰 Enter amount in {crypto_type}\n"
        f"Minimum amount: {min_amounts[crypto_type]} {crypto_type}\n\n"
        f"ℹ️ <b>Service fee: 2% (minimum $3)</b>\n\n"
        "Example: <code>0.05</code>",
        parse_mode="HTML"
    )
    
    await callback.answer()
    await state.set_state(CreateDeal.waiting_for_amount)

@router.message(CreateDeal.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        amount = validate_crypto_amount(message.text, data["crypto_type"])
        
        amount_with_commission = calculate_commission(amount)
        
        await state.update_data(
            amount=amount,
            amount_with_commission=amount_with_commission
        )
        
        await message.answer(
            "📦 <b>Describe the item or service</b>:\n\n"
            "Maximum 200 characters\n\n"
            "Example: <code>iPhone 13 smartphone, 256GB, new in box</code>",
            parse_mode="HTML"
        )
        await state.set_state(CreateDeal.waiting_for_description)
    except ValueError as e:
        await message.answer(
            f"❌ {str(e)}\n\nTry again:",
            parse_mode="HTML"
        )

@router.message(CreateDeal.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    if len(message.text) > 200:
        await message.answer(
            f"❌ <b>Description must not exceed 200 characters!</b>\n\n"
            f"Current length: {len(message.text)}\n"
            f"Remaining: {200 - len(message.text)}",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    deal_id = generate_deal_id()
    
    try:
        deposit_address = await get_next_deposit_address(data["crypto_type"])
    except ValueError as e:
        await message.answer(
            "🚨 <b>Error getting deposit address</b>\n\n"
            f"{str(e)}\n\n"
            "Please contact administrator.",
            parse_mode="HTML",
            reply_markup=get_contact_admin_keyboard("address_error")
        )
        await state.clear()
        return
    
    encrypted_description = encrypt_data(message.text)
    
    buyer = await get_user_by_id(message.from_user.id)
    
    deal_data = {
        "id": deal_id,
        "buyer_id": buyer["id"] if buyer else message.from_user.id,
        "seller_id": data["seller_id"],
        "crypto_type": data["crypto_type"],
        "original_amount": data["amount"],
        "amount": data["amount_with_commission"],
        "description": encrypted_description,
        "deposit_address": deposit_address,
        "status": "AWAITING_PAYMENT"
    }
    
    await create_deal(deal_data)
    
    buyer_data = await get_user_by_id(deal_data["buyer_id"])
    seller_data = await get_user_by_id(deal_data["seller_id"])
    
    buyer_username = buyer_data["username"] if buyer_data else f"user_{deal_data['buyer_id']}"
    seller_username = seller_data["username"] if seller_data else f"user_{deal_data['seller_id']}"
    
    deal_info = (
        f"✅ <b>DEAL CREATED!</b>\n\n"
        f"🆔 <b>Deal ID</b>: <code>{deal_id}</code>\n"
        f"💰 <b>Deal amount</b>: {data['amount']} {data['crypto_type']}\n"
        f"💸 <b>Amount to pay</b>: {data['amount_with_commission']:.8f} {data['crypto_type']}\n"
        f"   • Including 2% service fee\n"
        f"📦 <b>Item</b>: {message.text}\n"
        f"📥 <b>Deposit address</b>:\n<code>{deposit_address}</code>\n\n"
        f"👥 <b>Participants</b>:\n"
        f"• Buyer: @{buyer_username}\n"
        f"• Seller: @{seller_username}\n\n"
        f"⏳ <b>Status</b>: Awaiting payment\n\n"
        f"❗️ <b>IMPORTANT</b>:\n"
        f"1. Send EXACTLY the specified amount\n"
        f"2. After payment, click the button below\n"
        f"3. Funds will be held until item is confirmed received"
    )
    
    await message.answer(
        deal_info,
        reply_markup=get_deal_info_keyboard(deal_id, "buyer", deposit_address, data["crypto_type"]),
        parse_mode="HTML"
    )
    
    try:
        if seller_data and seller_data.get("telegram_id"):
            await message.bot.send_message(
                seller_data["telegram_id"],
                (
                    f"🛒 <b>New deal created for you!</b>\n\n"
                    f"🆔 <b>Deal ID</b>: <code>{deal_id}</code>\n"
                    f"💰 <b>Amount</b>: {data['amount']} {data['crypto_type']}\n"
                    f"💸 <b>Amount to pay</b>: {data['amount_with_commission']:.8f} {data['crypto_type']}\n"
                    f"   • Including 2% service fee\n"
                    f"📦 <b>Item</b>: {message.text}\n"
                    f"👤 <b>Buyer</b>: @{buyer_username}\n\n"
                    f"ℹ️ <b>Actions</b>:\n"
                    f"• Wait for payment confirmation from administrator\n"
                    f"• After confirmation, ship the item\n"
                    f"• Click 'Item shipped' in the deal"
                ),
                parse_mode="HTML",
                reply_markup=get_deal_info_keyboard(deal_id, "seller", deposit_address, data["crypto_type"])
            )
    except Exception as e:
        logger.error(f"❌ Error notifying seller for deal {deal_id}: {str(e)}")
        await message.answer(
            f"⚠️ <b>Failed to notify seller</b> @{seller_username}!\n\n"
            f"Please inform them <b>manually</b>:\n"
            f"🆔 Deal ID: <code>{deal_id}</code>",
            parse_mode="HTML"
        )
    
    await state.clear()