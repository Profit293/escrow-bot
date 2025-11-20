from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database.db import create_user
from keyboards import get_main_menu_keyboard

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    telegram_id = message.from_user.id
    username = message.from_user.username or f"user_{telegram_id}"
    
    # Save user to database
    await create_user(telegram_id, username)
    
    await message.answer(
        "🛡️ <b>Welcome to Escrow Bot!</b>\n\n"
        "✅ <b>Security guarantee</b>:\n"
        "• Funds are protected until item receipt is confirmed\n"
        "• All deals are controlled by administrators\n"
        "• Simple and intuitive interface\n\n"
        "💰 <b>Service fee</b>: 2% of amount (minimum $3)\n\n"
        "🛠️ <b>Main commands</b>:\n"
        "/create_deal — Create a new deal\n"
        "/verify_deal — Check deal status\n"
        "/help — Help and support",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🆘 <b>Help</b>\n\n"
        "<b>How to create a deal:</b>\n"
        "1. Click /create_deal\n"
        "2. Enter seller's username\n"
        "3. Select cryptocurrency from buttons\n"
        "4. Enter amount and item description\n\n"
        "<b>Deal statuses:</b>\n"
        "• CREATED — Deal created\n"
        "• AWAITING_PAYMENT — Awaiting payment\n"
        "• PAID — Payment confirmed\n"
        "• SHIPPED — Item shipped\n"
        "• COMPLETED — Funds transferred to seller\n\n"
        "<b>Important!</b>\n"
        "• All payments through escrow wallet\n"
        "• If issues arise, click 'Help'",
        parse_mode="HTML"
    )