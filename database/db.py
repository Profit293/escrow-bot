import json
from pathlib import Path
from config import load_config
from datetime import datetime, timedelta
import logging
import os

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
    """Initialize SQLite database for local development"""
    try:
        import aiosqlite
        
        DB_PATH = config.database_path
        
        # Create directory if not exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
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
            
            # Load addresses from JSON
            await _load_deposit_addresses(db, "sqlite")
            
            # Add admins
            await _add_admins(db, "sqlite")
            
            await db.commit()
            logger.info("✅ SQLite database initialized successfully")
    except Exception as e:
        logger.exception(f"❌ Error initializing SQLite database: {str(e)}")
        raise

# async def _init_postgres_db():
    """Initialize PostgreSQL database for Render.com"""
    try:
        import asyncpg
        
        conn = await asyncpg.connect(config.database_url)
        
        # Create all required tables
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS deposit_addresses (
            id SERIAL PRIMARY KEY,
            crypto_type TEXT NOT NULL CHECK(crypto_type IN ('BTC', 'LTC')),
            address TEXT UNIQUE NOT NULL,
            is_used BOOLEAN DEFAULT FALSE,
            reserved_until TIMESTAMP
        )
        """)
        
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """)
        
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            telegram_id BIGINT PRIMARY KEY
        )
        """)
        
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id VARCHAR(6) PRIMARY KEY,
            buyer_id INTEGER NOT NULL REFERENCES users(id),
            seller_id INTEGER NOT NULL REFERENCES users(id),
            crypto_type TEXT NOT NULL CHECK(crypto_type IN ('BTC', 'LTC')),
            original_amount NUMERIC(20,8) NOT NULL,
            amount NUMERIC(20,8) NOT NULL,
            description TEXT NOT NULL CHECK(LENGTH(description) <= 200),
            status TEXT NOT NULL DEFAULT 'CREATED',
            deposit_address TEXT NOT NULL,
            tx_hash TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """)
        
        # Load addresses from JSON
        await _load_deposit_addresses(conn, "postgres")
        
        # Add admins
        await _add_admins(conn, "postgres")
        
        await conn.close()
        logger.info("✅ PostgreSQL database initialized successfully")
    except Exception as e:
        logger.exception(f"❌ Error initializing PostgreSQL database: {str(e)}")
        raise

async def _load_deposit_addresses(db, db_type):
    """Load deposit addresses from JSON file"""
    addresses_file = Path("deposit_addresses.json")
    
    if not addresses_file.exists():
        logger.warning("⚠️ deposit_addresses.json not found. Please create it with BTC/LTC addresses")
        return
    
    try:
        with open(addresses_file) as f:
            addresses = json.load(f)
        
        for crypto, addr_list in addresses.items():
            if crypto not in ["BTC", "LTC"]:
                continue
                
            for addr in addr_list:
                try:
                    if db_type == "sqlite":
                        await db.execute(
                            "INSERT OR IGNORE INTO deposit_addresses (crypto_type, address) VALUES (?, ?)",
                            (crypto, addr)
                        )
                    else:  # postgres
                        await db.execute(
                            "INSERT INTO deposit_addresses (crypto_type, address) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                            crypto, addr
                        )
                except Exception as e:
                    logger.error(f"❌ Error inserting address {addr}: {str(e)}")
        
        # Count loaded addresses
        if db_type == "sqlite":
            cursor = await db.execute("SELECT COUNT(*) FROM deposit_addresses")
            count = await cursor.fetchone()
            logger.info(f"✅ Loaded {count[0]} deposit addresses")
        else:  # postgres
            count = await db.fetchval("SELECT COUNT(*) FROM deposit_addresses")
            logger.info(f"✅ Loaded {count} deposit addresses")
            
    except Exception as e:
        logger.error(f"❌ Error loading deposit addresses: {str(e)}")

async def _add_admins(db, db_type):
    """Add administrators to database"""
    for admin_id in config.admin_telegram_ids:
        try:
            if db_type == "sqlite":
                await db.execute(
                    "INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)",
                    (admin_id,)
                )
            else:  # postgres
                await db.execute(
                    "INSERT INTO admins (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING",
                    admin_id
                )
        except Exception as e:
            logger.error(f"❌ Error adding admin {admin_id}: {str(e)}")
    logger.info(f"✅ Added {len(config.admin_telegram_ids)} administrators")

# Common database functions (work for both SQLite and PostgreSQL)
async def get_next_deposit_address(crypto_type: str) -> str:
    """Get next available deposit address"""
    if crypto_type not in ["BTC", "LTC"]:
        raise ValueError("Only BTC and LTC are allowed")
    
    if config.is_render:
        return await _get_postgres_deposit_address(crypto_type)
    else:
        return await _get_sqlite_deposit_address(crypto_type)

async def _get_sqlite_deposit_address(crypto_type: str) -> str:
    """Get address from SQLite database"""
    try:
        import aiosqlite
        
        async with aiosqlite.connect(config.database_path) as db:
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

async def _get_postgres_deposit_address(crypto_type: str) -> str:
    """Get address from PostgreSQL database"""
    try:
        import asyncpg
        
        conn = await asyncpg.connect(config.database_url)
        
        row = await conn.fetchrow(
            """
            SELECT address FROM deposit_addresses 
            WHERE crypto_type = $1 AND is_used = FALSE
            ORDER BY id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
            """,
            crypto_type
        )
        
        if not row:
            await conn.close()
            raise ValueError(f"No free addresses for {crypto_type}. Contact administrator.")
        
        address = row["address"]
        
        # Update address status
        await conn.execute(
            """
            UPDATE deposit_addresses 
            SET is_used = TRUE 
            WHERE address = $1
            """,
            address
        )
        
        await conn.close()
        logger.info(f"✅ Address {address} reserved for {crypto_type}")
        return address
    except Exception as e:
        logger.exception(f"❌ Error getting PostgreSQL deposit address: {str(e)}")
        raise

async def create_user(telegram_id: int, username: str):
    """Create user in database (works for both environments)"""
    try:
        if config.is_render:
            import asyncpg
            conn = await asyncpg.connect(config.database_url)
            await conn.execute(
                "INSERT INTO users (telegram_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                telegram_id, username
            )
            await conn.close()
        else:
            import aiosqlite
            async with aiosqlite.connect(config.database_path) as db:
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
    """Get user by username (works for both environments)"""
    try:
        if config.is_render:
            import asyncpg
            conn = await asyncpg.connect(config.database_url)
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE username = $1",
                username
            )
            await conn.close()
            if row:
                return dict(row)
        else:
            import aiosqlite
            async with aiosqlite.connect(config.database_path) as db:
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
    """Get user by ID (works for both environments)"""
    try:
        if config.is_render:
            import asyncpg
            conn = await asyncpg.connect(config.database_url)
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1 OR telegram_id = $2",
                user_id, user_id
            )
            await conn.close()
            if row:
                return dict(row)
        else:
            import aiosqlite
            async with aiosqlite.connect(config.database_path) as db:
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
    """Create new deal (works for both environments)"""
    try:
        if deal_data["crypto_type"] not in ["BTC", "LTC"]:
            raise ValueError("Only BTC and LTC are allowed")
        
        if config.is_render:
            import asyncpg
            conn = await asyncpg.connect(config.database_url)
            await conn.execute("""
            INSERT INTO deals (
                id, buyer_id, seller_id, crypto_type, original_amount, amount,
                description, deposit_address, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
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
            await conn.close()
        else:
            import aiosqlite
            async with aiosqlite.connect(config.database_path) as db:
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
    """Get deal by ID (works for both environments)"""
    try:
        if config.is_render:
            import asyncpg
            conn = await asyncpg.connect(config.database_url)
            row = await conn.fetchrow(
                "SELECT * FROM deals WHERE id = $1",
                deal_id
            )
            await conn.close()
            if row:
                return dict(row)
        else:
            import aiosqlite
            async with aiosqlite.connect(config.database_path) as db:
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
    """Update deal status and update time (works for both environments)"""
    try:
        if config.is_render:
            import asyncpg
            conn = await asyncpg.connect(config.database_url)
            if tx_hash:
                await conn.execute(
                    "UPDATE deals SET status = $1, tx_hash = $2, updated_at = NOW() WHERE id = $3",
                    new_status, tx_hash, deal_id
                )
            else:
                await conn.execute(
                    "UPDATE deals SET status = $1, updated_at = NOW() WHERE id = $2",
                    new_status, deal_id
                )
            await conn.close()
        else:
            import aiosqlite
            async with aiosqlite.connect(config.database_path) as db:
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
    """Check for available addresses (works for both environments)"""
    try:
        if crypto_type not in ["BTC", "LTC"]:
            return False
        
        if config.is_render:
            import asyncpg
            conn = await asyncpg.connect(config.database_url)
            row = await conn.fetchrow(
                "SELECT 1 FROM deposit_addresses WHERE crypto_type = $1 AND is_used = FALSE LIMIT 1",
                crypto_type
            )
            await conn.close()
            return row is not None
        else:
            import aiosqlite
            async with aiosqlite.connect(config.database_path) as db:
                cursor = await db.execute(
                    "SELECT 1 FROM deposit_addresses WHERE crypto_type = ? AND is_used = 0 LIMIT 1",
                    (crypto_type,)
                )
                row = await cursor.fetchone()
                return row is not None
    except Exception as e:
        logger.exception(f"❌ Error checking available addresses for {crypto_type}: {str(e)}")
        return False