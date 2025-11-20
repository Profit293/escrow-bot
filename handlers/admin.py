from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.db import get_deal_by_id, update_deal_status, get_user_by_id
from utils.crypto_utils import decrypt_data
from config import load_config
from keyboards import get_admin_error_keyboard, get_blockchain_url
import logging
import requests
import json
from datetime import datetime

router = Router()
config = load_config()
logger = logging.getLogger("escrow_bot")

if not config.blockcypher_api_key:
    logger.warning("⚠️ BlockCypher API key not configured! Check .env file")

def check_transaction(crypto_type: str, address: str, expected_amount: float) -> dict:
    try:
        if not config.blockcypher_api_key:
            return {"confirmed": False, "error": "BlockCypher API key not configured"}
        
        if crypto_type not in ["BTC", "LTC"]:
            return {"confirmed": False, "error": f"Unsupported cryptocurrency: {crypto_type}"}
        
        if crypto_type == "BTC":
            blockchain = "btc"
            network = "main"
            min_confirmations = 3
        elif crypto_type == "LTC":
            blockchain = "ltc"
            network = "main"
            min_confirmations = 2
        
        url = f"https://api.blockcypher.com/v1/{blockchain}/{network}/addrs/{address}?limit=10&token={config.blockcypher_api_key}"
        
        headers = {
            "User-Agent": "EscrowBot/1.0",
            "Accept": "application/json"
        }
        
        logger.info(f"🔍 Checking transaction for {crypto_type} address: {address}")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 429:
            return {"confirmed": False, "error": "API request limit exceeded. Try again in 1 minute."}
        
        if response.status_code != 200:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", "Unknown API error")
            except:
                error_msg = f"HTTP error {response.status_code}"
            
            logger.error(f"❌ BlockCypher API error: {error_msg}")
            return {
                "confirmed": False, 
                "error": f"API error ({response.status_code}): {error_msg}"
            }
        
        data = response.json()
        
        if logger.level <= logging.DEBUG:
            logger.debug(f"✅ BlockCypher API response: {json.dumps(data, indent=2)}")
        
        transactions = data.get("txrefs", [])
        if not transactions:
            return {"confirmed": False, "error": "No transactions found for this address"}
        
        logger.info(f"📊 Found transactions: {len(transactions)}")
        
        for tx in transactions:
            confirmations = tx.get("confirmations", 0)
            received_value = tx.get("value", 0) / 1e8
            
            logger.info(f"🔍 Transaction: {tx.get('tx_hash', 'unknown')[:10]}..., "
                        f"Confirmations: {confirmations}, "
                        f"Amount: {received_value} {crypto_type}")
            
            if (confirmations >= min_confirmations and 
                received_value >= expected_amount - 0.000001):
                
                tx_hash = tx.get("tx_hash", "unknown")
                if len(tx_hash) > 20:
                    tx_hash = tx_hash[:20] + "..."
                
                return {
                    "confirmed": True,
                    "tx_hash": tx_hash,
                    "amount": received_value,
                    "confirmations": confirmations,
                    "timestamp": tx.get("confirmed", datetime.now().isoformat())
                }
        
        total_received = sum(tx.get("value", 0) for tx in transactions) / 1e8
        
        error_details = (
            f"Required amount: {expected_amount} {crypto_type}\n"
            f"Received: {total_received} {crypto_type}\n"
            f"Min. confirmations: {min_confirmations}\n\n"
            f"Transaction details:\n"
        )
        
        for i, tx in enumerate(transactions[:3], 1):
            tx_confirmations = tx.get("confirmations", 0)
            tx_value = tx.get("value", 0) / 1e8
            tx_hash = tx.get("tx_hash", "unknown")[:10]
            error_details += f"{i}. {tx_hash}... | {tx_value} {crypto_type} | {tx_confirmations} conf.\n"
        
        if len(transactions) > 3:
            error_details += f"+ {len(transactions) - 3} more transactions"
        
        return {
            "confirmed": False,
            "error": error_details
        }
    
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout when requesting BlockCypher API")
        return {"confirmed": False, "error": "Timeout when requesting blockchain. Please try again later."}
    except requests.exceptions.ConnectionError:
        logger.error("❌ Connection error to BlockCypher API")
        return {"confirmed": False, "error": "Connection error to blockchain. Check your internet connection."}
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing error for BlockCypher response: {str(e)}")
        return {"confirmed": False, "error": f"Blockchain response processing error: {str(e)}"}
    except Exception as e:
        logger.exception(f"❌ Critical error in check_transaction: {str(e)}")
        return {"confirmed": False, "error": f"Internal system error: {str(e)}"}

@router.callback_query(F.data.startswith("admin:confirm_payment:"))
async def handle_admin_confirm_payment(callback: CallbackQuery):
    deal_id = callback.data.split(":")[2]
    deal = await get_deal_by_id(deal_id)
    
    if not deal:
        await callback.answer("❌ Deal not found", show_alert=True)
        return
    
    await callback.answer("🔍 Checking payment in blockchain...", show_alert=False)
    
    try:
        logger.info(f"🚀 Starting payment check for deal {deal_id}")
        
        tx_info = check_transaction(
            deal["crypto_type"],
            deal["deposit_address"],
            deal["amount"]
        )
        
        if tx_info.get("confirmed", False):
            logger.info(f"✅ Payment for deal {deal_id} confirmed!")
            
            await update_deal_status(
                deal_id,
                "PAID",
                tx_hash=tx_info["tx_hash"]
            )
            
            buyer = await get_user_by_id(deal["buyer_id"])
            
            await callback.bot.send_message(
                deal["buyer_id"],
                f"✅ Administrator confirmed payment for deal {deal_id}!\n\n"
                f"Now the seller should send the item. You will be notified when they do.",
                parse_mode="HTML"
            )
            
            seller = await get_user_by_id(deal["seller_id"])
            
            if seller:
                try:
                    await callback.bot.send_message(
                        seller["telegram_id"],
                        f"💰 Deal {deal_id} is paid!\n\n"
                        f"Send the item to the buyer and click 'Item shipped' in the deal.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"❌ Error notifying seller {seller.get('username', 'unknown')}: {str(e)}")
            else:
                logger.warning(f"⚠️ Seller not found for deal {deal_id}")
            
            
            confirmation_msg = (
                f"✅ <b>Payment confirmed!</b>\n\n"
                f"🆔 Deal ID: <code>{deal_id}</code>\n"
                f"💰 Amount: {tx_info['amount']:.6f} {deal['crypto_type']}\n"
                f"🔗 Transaction hash: <code>{tx_info['tx_hash']}</code>\n"
                f"✅ Confirmations: {tx_info['confirmations']}\n"
                f"⏰ Time: {tx_info.get('timestamp', 'Unknown')[:19]}"
            )
            
            await callback.message.edit_text(
                confirmation_msg,
                parse_mode="HTML",
                reply_markup=None
            )
        else:
            error = tx_info.get("error", "Unknown error")
            blockchain_url = get_blockchain_url(deal["crypto_type"], deal["deposit_address"])
            
            logger.warning(f"❌ Payment for deal {deal_id} NOT confirmed. Reason: {error}")
            
            error_msg = (
                f"❌ <b>Payment NOT confirmed</b>\n\n"
                f"🆔 Deal ID: <code>{deal_id}</code>\n"
                f"🛑 <b>Error details</b>:\n<pre>{error}</pre>\n\n"
                f"🔍 <b>Manual check</b>:\n"
                f"<a href='{blockchain_url}'>{deal['deposit_address']}</a>\n\n"
                f"ℹ️ <b>What to do</b>:\n"
                f"• Ensure payment was sent exactly to the provided address\n"
                f"• Verify payment amount\n"
                f"• Wait 10-15 minutes for confirmations\n"
                f"• Click button below to recheck"
            )
            
            await callback.message.edit_text(
                error_msg,
                parse_mode="HTML",
                reply_markup=get_admin_error_keyboard(deal_id, deal["crypto_type"], deal["deposit_address"])
            )
    
    except Exception as e:
        logger.exception(f"🚨 Critical error when confirming payment for deal {deal_id}: {str(e)}")
        await callback.message.edit_text(
            "🚨 <b>Critical system error</b>\n\n"
            "An error occurred while checking payment. "
            "Please try again later or contact developers.",
            parse_mode="HTML",
            reply_markup=get_admin_error_keyboard(deal_id, deal["crypto_type"], deal["deposit_address"])
        )

@router.callback_query(F.data.startswith("admin:confirm_shipment:"))
async def handle_admin_confirm_shipment(callback: CallbackQuery):
    deal_id = callback.data.split(":")[2]
    deal = await get_deal_by_id(deal_id)
    
    if not deal:
        await callback.answer("❌ Deal not found", show_alert=True)
        return
    
    await update_deal_status(deal_id, "SHIPPED")
    
    await callback.bot.send_message(
        deal["buyer_id"],
        f"🚚 Seller reported that item for deal {deal_id} has been shipped!\n\n"
        f"Check item receipt and click 'Item received' in the deal.",
        parse_mode="HTML"
    )
    
    await callback.answer("✅ Shipment confirmed")
    await callback.message.edit_text(
        f"✅ <b>Shipment confirmed</b>\n\n"
        f"🆔 Deal ID: <code>{deal_id}</code>",
        parse_mode="HTML",
        reply_markup=None
    )

@router.callback_query(F.data.startswith("admin:release_funds:"))
async def handle_admin_release_funds(callback: CallbackQuery):
    deal_id = callback.data.split(":")[2]
    deal = await get_deal_by_id(deal_id)
    
    if not deal:
        await callback.answer("❌ Deal not found", show_alert=True)
        return
    
    await update_deal_status(deal_id, "COMPLETED")
    
    seller = await get_user_by_id(deal["seller_id"])
    
    if seller:
        try:
            await callback.bot.send_message(
                seller["telegram_id"],
                f"🎉 <b>Funds successfully transferred!</b>\n\n"
                f"🆔 Deal ID: {deal_id}\n"
                f"💰 Amount: {deal['amount']} {deal['crypto_type']}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"❌ Error notifying seller when completing deal {deal_id}: {str(e)}")
    
    await callback.answer("✅ Funds released")
    await callback.message.edit_text(
        f"✅ <b>Funds transferred to seller</b>\n\n"
        f"🆔 Deal ID: {deal_id}",
        parse_mode="HTML",
        reply_markup=None
    )