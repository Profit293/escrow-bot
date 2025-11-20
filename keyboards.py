from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from config import load_config
import logging

config = load_config()
logger = logging.getLogger("escrow_bot")

def get_main_menu_keyboard():
    """Main bot menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
        [InlineKeyboardButton(text="🔄 Create Deal", callback_data="create_deal")],
        [InlineKeyboardButton(text="🔍 Verify Deal", callback_data="verify_deal")]
    ])

def get_inline_crypto_keyboard():
    """Inline keyboard for cryptocurrency selection (BTC and LTC only)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💰 Bitcoin (BTC)",
                callback_data="crypto_btc"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚡ Litecoin (LTC)",
                callback_data="crypto_ltc"
            )
        ]
    ])

def get_deal_info_keyboard(deal_id: str, role: str, deposit_address: str = None, crypto_type: str = None):
    """Keyboard for deal information"""
    builder = InlineKeyboardMarkup(inline_keyboard=[])
    
    if role == "buyer":
        builder.inline_keyboard.append([
            InlineKeyboardButton(text="✅ I Paid", callback_data=f"payment_confirmed:{deal_id}")
        ])
    elif role == "seller":
        builder.inline_keyboard.append([
            InlineKeyboardButton(text="📦 Item Shipped", callback_data=f"item_shipped:{deal_id}")
        ])
    
    if deposit_address and crypto_type:
        blockchain_url = get_blockchain_url(crypto_type, deposit_address)
        builder.inline_keyboard.append([
            InlineKeyboardButton(text="🔍 Check Payment", url=blockchain_url)
        ])
    
    builder.inline_keyboard.append([
        InlineKeyboardButton(text="🆘 Help", callback_data=f"contact_admin:{deal_id}")
    ])
    
    return builder

def get_blockchain_url(crypto_type: str, address: str) -> str:
    """Returns the correct URL for checking address in blockchain"""
    if crypto_type == "BTC":
        return f"https://www.blockchain.com/explorer/addresses/btc/{address}"
    elif crypto_type == "LTC":
        return f"https://live.blockcypher.com/ltc/address/{address}/"
    return "https://www.blockchain.com/explorer"

def get_admin_action_keyboard(deal_id: str, action_type: str):
    """Administrator actions keyboard"""
    builder = InlineKeyboardMarkup(inline_keyboard=[])
    
    if action_type == "confirm_payment":
        builder.inline_keyboard.append([
            InlineKeyboardButton(text="✅ Confirm Payment", 
                               callback_data=f"admin:confirm_payment:{deal_id}")
        ])
    elif action_type == "retry_payment":
        builder.inline_keyboard.append([
            InlineKeyboardButton(text="🔄 Check Again", 
                               callback_data=f"admin:confirm_payment:{deal_id}")
        ])
    elif action_type == "shipment":
        builder.inline_keyboard.append([
            InlineKeyboardButton(text="✅ Confirm Shipment", 
                               callback_data=f"admin:confirm_shipment:{deal_id}")
        ])
    elif action_type == "release":
        builder.inline_keyboard.append([
            InlineKeyboardButton(text="💰 Release Funds", 
                               callback_data=f"admin:release_funds:{deal_id}")
        ])
    
    return builder

def get_admin_payment_keyboard(deal_id: str, crypto_type: str, deposit_address: str):
    """Administrator keyboard with payment confirmation and blockchain check"""
    builder = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Payment confirmation button
    builder.inline_keyboard.append([
        InlineKeyboardButton(
            text="✅ Confirm Payment", 
            callback_data=f"admin:confirm_payment:{deal_id}"
        )
    ])
    
    # Blockchain check button
    blockchain_url = get_blockchain_url(crypto_type, deposit_address)
    builder.inline_keyboard.append([
        InlineKeyboardButton(
            text="🔍 Check in Blockchain", 
            url=blockchain_url
        )
    ])
    
    return builder

def get_admin_error_keyboard(deal_id: str, crypto_type: str, deposit_address: str):
    """Administrator keyboard for payment confirmation error"""
    builder = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Recheck button
    builder.inline_keyboard.append([
        InlineKeyboardButton(
            text="🔄 Check Again", 
            callback_data=f"admin:confirm_payment:{deal_id}"
        )
    ])
    
    # Blockchain check button
    blockchain_url = get_blockchain_url(crypto_type, deposit_address)
    builder.inline_keyboard.append([
        InlineKeyboardButton(
            text="🔍 Check in Blockchain", 
            url=blockchain_url
        )
    ])
    
    return builder

def get_contact_admin_keyboard(deal_id: str = None):
    """Button to contact administrator"""
    if config.admin_username:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💬 Write to Administrator",
                url=f"https://t.me/{config.admin_username}"
            )]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🆘 Contact Administrator",
            callback_data=f"contact_admin:{deal_id or 'general'}"
        )]
    ])