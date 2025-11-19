import aiosqlite
from datetime import datetime, timedelta
from .config import DB_PATH
import os
import secrets
import time

# Single shared connection pool/context (avoid creating new connections per query)
_db_connection = None

async def get_db():
    """Get or create a singleton DB connection."""
    global _db_connection
    if _db_connection is None:
        _db_connection = await aiosqlite.connect(DB_PATH)
        _db_connection.row_factory = aiosqlite.Row
    return _db_connection

async def init_db():
    """Initialize the database."""
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            max_bots INTEGER NOT NULL,
            registered_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            revoked INTEGER DEFAULT 0
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            bot_name TEXT,
            bot_token TEXT,
            script TEXT,
            status TEXT DEFAULT 'stopped',
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    await db.execute('''
        CREATE TABLE IF NOT EXISTS secrets (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            max_bots INTEGER NOT NULL,
            created_at REAL NOT NULL,
            used INTEGER DEFAULT 0
        )
    ''')
    await db.commit()

async def create_secret(user_id: int, max_bots: int) -> str:
    """Create a secret in SQL database (not JSON)."""
    db = await get_db()
    secret_id = secrets.token_urlsafe(32)
    now = time.time()
    
    await db.execute(
        "INSERT INTO secrets (id, user_id, max_bots, created_at, used) VALUES (?, ?, ?, ?, 0)",
        (secret_id, user_id, max_bots, now)
    )
    await db.commit()
    return secret_id

async def validate_secret(secret_id: str):
    """Validate a secret and check if it's expired."""
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT user_id, max_bots, created_at, used FROM secrets WHERE id = ?",
        (secret_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        return None, "Secret invalide ou expiré."
    
    user_id, max_bots, created_at, used = row
    
    # Check if already used
    if used:
        return None, "Ce secret a déjà été utilisé."
    
    # Check if expired (24 hours)
    now = time.time()
    if now - created_at > (24 * 3600):
        return None, "Ce secret a expiré (24 heures)."
    
    return {"user_id": user_id, "max_bots": max_bots}, None

async def consume_secret(secret_id: str):
    """Mark secret as used in database."""
    db = await get_db()
    await db.execute(
        "UPDATE secrets SET used = 1 WHERE id = ?",
        (secret_id,)
    )
    await db.commit()

async def delete_expired_secrets():
    """Delete secrets that have expired (older than 24 hours)."""
    db = await get_db()
    now = time.time()
    expiry_threshold = now - (24 * 3600)
    
    await db.execute(
        "DELETE FROM secrets WHERE created_at < ?",
        (expiry_threshold,)
    )
    await db.commit()
    print(f"Expired secrets cleaned up at {time.strftime('%Y-%m-%d %H:%M:%S')}")

async def register_user(user_id: int, max_bots: int):
    """Register a user with 30-day expiration."""
    db = await get_db()
    now = time.time()
    expires_at = now + (30 * 24 * 3600)  # 30 days from now
    
    await db.execute(
        "INSERT OR REPLACE INTO users (id, max_bots, registered_at, expires_at, revoked) VALUES (?, ?, ?, ?, 0)",
        (user_id, max_bots, now, expires_at)
    )
    await db.commit()
    print(f"User {user_id} registered until {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires_at))}")

async def get_user(user_id: int):
    """Get user and check if expired."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, max_bots, registered_at, expires_at, revoked FROM users WHERE id = ? AND revoked = 0",
        (user_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        return None
    
    user_id, max_bots, registered_at, expires_at, revoked = row
    
    # Check if user account has expired (30 days)
    now = time.time()
    if now > expires_at:
        # Account expired - revoke it
        await revoke_user(user_id)
        return None
    
    return row

async def delete_expired_users():
    """Automatically revoke and cleanup expired users (30 days after registration)."""
    db = await get_db()
    now = time.time()
    
    # Find expired users - utiliser 'id' qui est la clé primaire
    cursor = await db.execute(
        "SELECT id FROM users WHERE expires_at < ? AND revoked = 0",
        (now,)
    )
    expired_users = await cursor.fetchall()
    
    for (user_id,) in expired_users:
        print(f"Revoking expired user {user_id}")
        await revoke_user(user_id)

async def revoke_user(user_id: int):
    """Mark user as revoked and stop all their bots."""
    db = await get_db()
    
    # Stop all bots first - utiliser 'user_id' qui existe
    cursor = await db.execute(
        "SELECT bot_name FROM bots WHERE user_id = ? AND status != 'deleted'",
        (user_id,)
    )
    bots = await cursor.fetchall()
    
    for (bot_name,) in bots:
        from .bot_process import stop_bot_process
        stop_bot_process(user_id, bot_name)
    
    # Mark user as revoked - utiliser 'id' qui est la clé primaire
    await db.execute(
        "UPDATE users SET revoked = 1 WHERE id = ?",
        (user_id,)
    )
    await db.commit()
    print(f"User {user_id} revoked (all bots stopped)")

async def add_bot_to_db(user_id: int, bot_name: str, bot_token: str, script: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO bots (user_id, bot_name, bot_token, script) VALUES (?, ?, ?, ?)",
        (user_id, bot_name, bot_token, script)
    )
    await db.commit()

async def get_user_bots(user_id: int):
    db = await get_db()
    async with db.execute("SELECT * FROM bots WHERE user_id = ?", (user_id,)) as cursor:
        return await cursor.fetchall()

async def get_bot(user_id: int, bot_name: str):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM bots WHERE user_id = ? AND bot_name = ?", 
        (user_id, bot_name)
    ) as cursor:
        return await cursor.fetchone()

async def update_bot_status(user_id: int, bot_name: str, status: str):
    db = await get_db()
    await db.execute(
        "UPDATE bots SET status = ? WHERE user_id = ? AND bot_name = ?",
        (status, user_id, bot_name)
    )
    await db.commit()

async def update_bot_token(user_id: int, bot_name: str, new_token: str):
    db = await get_db()
    await db.execute(
        "UPDATE bots SET bot_token = ? WHERE user_id = ? AND bot_name = ?",
        (new_token, user_id, bot_name)
    )
    await db.commit()

async def delete_bot(user_id: int, bot_name: str):
    db = await get_db()
    await db.execute(
        "DELETE FROM bots WHERE user_id = ? AND bot_name = ?",
        (user_id, bot_name)
    )
    await db.commit()

async def get_all_users():
    db = await get_db()
    async with db.execute("SELECT * FROM users") as cursor:
        return await cursor.fetchall()

async def renew_user_account(user_id: int, max_bots: int):
    """Renew an expired user account for another 30 days."""
    db = await get_db()
    now = time.time()
    expires_at = now + (30 * 24 * 3600)  # 30 days from now
    
    # Update user: set revoked=0 and new expiration date, keep max_bots
    await db.execute(
        "UPDATE users SET expires_at = ?, revoked = 0 WHERE id = ?",
        (expires_at, user_id)
    )
    await db.commit()
    print(f"User {user_id} account renewed until {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires_at))}")
