from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.filters import Command

router = Router()

@router.callback_query(F.data == "create_deal")
async def handle_create_deal(callback: CallbackQuery):
    """Handler for 'Create deal' button"""
    await callback.answer()  # Remove "loading" state from button
    await callback.message.answer("/create_deal")  # Trigger command

@router.callback_query(F.data == "verify_deal")
async def handle_verify_deal(callback: CallbackQuery):
    """Handler for 'Verify deal' button"""
    await callback.answer()  # Remove "loading" state from button
    await callback.message.answer("/verify_deal")  # Trigger command

@router.callback_query(F.data == "main_menu")
async def handle_main_menu(callback: CallbackQuery):
    """Handler for 'Main menu' button"""
    from handlers.start import cmd_start
    await cmd_start(callback.message)
    await callback.answer()