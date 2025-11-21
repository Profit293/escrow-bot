import json
from pathlib import Path
from config import load_config
from datetime import datetime, timedelta
import logging
import os
import aiosqlite

config = load_config()
logger = logging.getLogger("escrow_bot")

async def init_db():
    """
    Initialize database - always use SQLite for simplicity
    """
    try:
        if config.is_render:
            logger.info("🔄 Initializing SQLite database on Render...")
        else:
            logger.info("🔄 Initializing SQLite database locally...")
        
        await _init_sqlite_db()
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Critical error during database initialization: {str(e)}")
        raise

async def _init_sqlite_db():
    """Initialize SQLite database"""
    try:
        # Use path from config or default value
        DB_PATH = config.database_path if config.database_path else "escrow_data.db"
        logger.info(f"📁 Database path: {DB_PATH}")
        
        # Only create directory if path contains subdirectories
        directory = os.path.dirname(DB_PATH)
        if directory and directory != DB_PATH:  # Check that directory is not empty and not equal to full path
            os.makedirs(directory, exist_ok=True)
            logger.info(f"📁 Created directory: {directory}")
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Create all required tables
            await db.execute("""
            CREATE TABLE IF NOT EXISTS deposit_addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crypto_type TEXT NOT NULL CHECK(crypto_type IN ('BTC', 'LTC')),
                address TEXT UNIQUE NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                reserved_until TIMESTAMP NULL
            )
            """)
            
            await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                telegram_id INTEGER PRIMARY KEY
            )
            """)
            
            await db.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id TEXT PRIMARY KEY,
                buyer_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                crypto_type TEXT NOT NULL CHECK(crypto_type IN ('BTC', 'LTC')),
                original_amount REAL NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL CHECK(LENGTH(description) <= 200),
                status TEXT NOT NULL DEFAULT 'CREATED',
                deposit_address TEXT NOT NULL,
                tx_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Load addresses from config (which loads from Secret Files on Render)
            await _load_deposit_addresses(db)
            
            # Add admins
            await _add_admins(db)
            
            await db.commit()
            logger.info("✅ SQLite database initialized successfully")
            
    except Exception as e:
        logger.exception(f"❌ Error initializing SQLite database: {str(e)}")
        raise

async def _load_deposit_addresses(db):
    """Load deposit addresses from config (which loads from Secret Files on Render)"""
    try:
        if not config.deposit_addresses:
            logger.warning("⚠️ No deposit addresses in config")
            return
        
        for crypto, address in config.deposit_addresses.items():
            crypto_upper = crypto.upper()
            if crypto_upper not in ["BTC", "LTC"]:
                continue
                
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO deposit_addresses (crypto_type, address) VALUES (?, ?)",
                    (crypto_upper, address)
                )
                logger.debug(f"✅ Added address for {crypto_upper}: {address}")
            except Exception as e:
                logger.error(f"❌ Error inserting address {address}: {str(e)}")
        
        # Count loaded addresses
        cursor = await db.execute("SELECT COUNT(*) FROM deposit_addresses")
        count = await cursor.fetchone()
        logger.info(f"✅ Loaded {count[0]} deposit addresses into database")
            
    except Exception as e:
        logger.error(f"❌ Error loading deposit addresses: {str(e)}")

async def _add_admins(db):
    """Add administrators to database"""
    try:
        for admin_id in config.admin_telegram_ids:
            await db.execute(
                "INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)",
                (admin_id,)
            )
        logger.info(f"✅ Added {len(config.admin_telegram_ids)} administrators")
    except Exception as e:
        logger.error(f"❌ Error adding admins: {str(e)}")

# Common database functions
async def get_next_deposit_address(crypto_type: str) -> str:
    """Get next available deposit address"""
    if crypto_type not in ["BTC", "LTC"]:
        raise ValueError("Only BTC and LTC are allowed")
    
    return await _get_sqlite_deposit_address(crypto_type)

async def _get_sqlite_deposit_address(crypto_type: str) -> str:
    """Get address from SQLite database"""
    try:
        DB_PATH = config.database_path if config.database_path else "escrow_data.db"
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                SELECT address FROM deposit_addresses 
                WHERE crypto_type = ? AND is_used = 0
                ORDER BY id
                LIMIT 1
                """,
                (crypto_type,)
            )
            row = await cursor.fetchone()
            
            if not row:
                raise ValueError(f"No free addresses for {crypto_type}. Contact administrator.")
            
            address = row[0]
            
            # Update address status
            await db.execute(
                """
                UPDATE deposit_addresses 
                SET is_used = 1 
                WHERE address = ?
                """,
                (address,)
            )
            await db.commit()
            logger.info(f"✅ Address {address} reserved for {crypto_type}")
            return address
    except Exception as e:
        logger.exception(f"❌ Error getting SQLite deposit address: {str(e)}")
        raise

async def create_user(telegram_id: int, username: str):
    """Create user in database"""
    try:
        DB_PATH = config.database_path if config.database_path else "escrow_data.db"
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
                (telegram_id, username)
            )
            await db.commit()
        logger.info(f"✅ User {username} (ID: {telegram_id}) created")
    except Exception as e:
        logger.exception(f"❌ Error creating user {username}: {str(e)}")
        raise

async def get_user_by_username(username: str) -> dict:
    """Get user by username"""
    try:
        DB_PATH = config.database_path if config.database_path else "escrow_data.db"
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            )
            row = await cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.exception(f"❌ Error getting user by username {username}: {str(e)}")
        return None

async def get_user_by_id(user_id: int) -> dict:
    """Get user by ID"""
    try:
        DB_PATH = config.database_path if config.database_path else "escrow_data.db"
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE id = ? OR telegram_id = ?",
                (user_id, user_id)
            )
            row = await cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.exception(f"❌ Error getting user by ID {user_id}: {str(e)}")
        return None

async def create_deal(deal_data: dict):
    """Create new deal"""
    try:
        if deal_data["crypto_type"] not in ["BTC", "LTC"]:
            raise ValueError("Only BTC and LTC are allowed")
        
        DB_PATH = config.database_path if config.database_path else "escrow_data.db"
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
            INSERT INTO deals (
                id, buyer_id, seller_id, crypto_type, original_amount, amount,
                description, deposit_address, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deal_data["id"],
                deal_data["buyer_id"],
                deal_data["seller_id"],
                deal_data["crypto_type"],
                deal_data["original_amount"],
                deal_data["amount"],
                deal_data["description"],
                deal_data["deposit_address"],
                deal_data["status"]
            ))
            await db.commit()
        logger.info(f"✅ Deal {deal_data['id']} created successfully")
    except Exception as e:
        logger.exception(f"❌ Error creating deal {deal_data.get('id', 'unknown')}: {str(e)}")
        raise

async def get_deal_by_id(deal_id: str) -> dict:
    """Get deal by ID"""
    try:
        DB_PATH = config.database_path if config.database_path else "escrow_data.db"
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM deals WHERE id = ?",
                (deal_id,)
            )
            row = await cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        return None
    except Exception as e:
        logger.exception(f"❌ Error getting deal {deal_id}: {str(e)}")
        return None

async def update_deal_status(deal_id: str, new_status: str, tx_hash: str = None):
    """Update deal status and update time"""
    try:
        DB_PATH = config.database_path if config.database_path else "escrow_data.db"
        
        async with aiosqlite.connect(DB_PATH) as db:
            if tx_hash:
                await db.execute(
                    "UPDATE deals SET status = ?, tx_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_status, tx_hash, deal_id)
                )
            else:
                await db.execute(
                    "UPDATE deals SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_status, deal_id)
                )
            await db.commit()
        logger.info(f"✅ Deal {deal_id} status updated to {new_status}")
    except Exception as e:
        logger.exception(f"❌ Error updating deal {deal_id} status: {str(e)}")
        raise

async def has_available_addresses(crypto_type: str) -> bool:
    """Check for available addresses"""
    try:
        if crypto_type not in ["BTC", "LTC"]:
            return False
        
        DB_PATH = config.database_path if config.database_path else "escrow_data.db"
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT 1 FROM deposit_addresses WHERE crypto_type = ? AND is_used = 0 LIMIT 1",
                (crypto_type,)
            )
            row = await cursor.fetchone()
            return row is not None
    except Exception as e:
        logger.exception(f"❌ Error checking available addresses for {crypto_type}: {str(e)}")
        return False