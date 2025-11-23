import aiosqlite
from .config import db_file
import secrets
import time

# global connection
conn = None

async def get_db():
    global conn
    if conn is None:
        conn = await aiosqlite.connect(db_file)
        conn.row_factory = aiosqlite.Row
    return conn

async def close_db():
    global conn
    if conn:
        await conn.close()
        conn = None
        print("db closed")

async def init_db():
    db = await get_db()
    
    # users table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            max_bots INTEGER NOT NULL,
            registered_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            revoked INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            last_crash_notification REAL DEFAULT 0,
            last_expiry_notification REAL DEFAULT 0
        )
    """)
    
    # bots table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            bot_name TEXT,
            bot_token TEXT,
            script TEXT,
            status TEXT DEFAULT 'stopped',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # secrets table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS secrets (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            max_bots INTEGER NOT NULL,
            created_at REAL NOT NULL,
            used INTEGER DEFAULT 0
        )
    """)
    
    # user scripts
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_scripts (
            user_id INTEGER,
            script_name TEXT,
            granted_at REAL NOT NULL,
            granted_by INTEGER,
            PRIMARY KEY (user_id, script_name),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # audit logs
    await db.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        admin_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target_user_id INTEGER,
        details TEXT
    )
    """)
    
    # versioning
    from .script_version_db import init_versioning_tables
    await init_versioning_tables()
    
    await db.commit()

async def create_secret(user_id, max_bots):
    db = await get_db()
    secret = secrets.token_urlsafe(32)
    now = time.time()
    
    await db.execute(
        "INSERT INTO secrets (id, user_id, max_bots, created_at, used) VALUES (?, ?, ?, ?, 0)",
        (secret, user_id, max_bots, now)
    )
    await db.commit()
    return secret

async def validate_secret(secret_id):
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT user_id, max_bots, created_at, used FROM secrets WHERE id = ?",
        (secret_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        return None, "Invalid secret."
    
    user_id, max_bots, created_at, used = row
    
    if used:
        return None, "Secret already used."
    
    now = time.time()
    if now - created_at > (24 * 3600):
        return None, "Secret expired."
    
    return {"user_id": user_id, "max_bots": max_bots}, None

async def consume_secret(secret_id):
    db = await get_db()
    await db.execute(
        "UPDATE secrets SET used = 1 WHERE id = ?",
        (secret_id,)
    )
    await db.commit()

async def delete_expired_secrets():
    db = await get_db()
    now = time.time()
    limit = now - (24 * 3600)
    
    await db.execute(
        "DELETE FROM secrets WHERE created_at < ?",
        (limit,)
    )
    await db.commit()
    print("cleaned secrets")

async def register_user(user_id, max_bots):
    db = await get_db()
    now = time.time()
    expires = now + (30 * 24 * 3600)
    
    await db.execute(
        "INSERT OR REPLACE INTO users (id, max_bots, registered_at, expires_at, revoked, is_vip) VALUES (?, ?, ?, ?, 0, 0)",
        (user_id, max_bots, now, expires)
    )
    await db.commit()
    print(f"user {user_id} registered")

async def get_user(user_id):
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, max_bots, registered_at, expires_at, revoked, is_vip FROM users WHERE id = ? AND revoked = 0",
        (user_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        return None
    
    now = time.time()
    if now > row[3]:
        await revoke_user(user_id)
        return None
    
    return row

async def set_vip_status(user_id, is_vip):
    db = await get_db()
    val = 1 if is_vip else 0
    await db.execute("UPDATE users SET is_vip = ? WHERE id = ?", (val, user_id))
    await db.commit()

async def get_vip_users():
    db = await get_db()
    async with db.execute("SELECT id FROM users WHERE is_vip = 1") as cursor:
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def delete_expired_users():
    db = await get_db()
    now = time.time()
    
    cursor = await db.execute(
        "SELECT id FROM users WHERE expires_at < ? AND revoked = 0",
        (now,)
    )
    expired = await cursor.fetchall()
    
    for (uid,) in expired:
        print(f"revoking {uid}")
        await revoke_user(uid)

async def revoke_user(user_id):
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT bot_name FROM bots WHERE user_id = ?",
        (user_id,)
    )
    bots = await cursor.fetchall()
    
    for (bname,) in bots:
        from .bot_process import stop_bot_process
        stop_bot_process(user_id, bname)
    
    await db.execute(
        "UPDATE users SET revoked = 1 WHERE id = ?",
        (user_id,)
    )
    await db.execute(
        "DELETE FROM user_scripts WHERE user_id = ?",
        (user_id,)
    )
    await db.commit()
    print(f"user {user_id} revoked")

async def add_bot_to_db(user_id, bot_name, bot_token, script):
    db = await get_db()
    await db.execute(
        "INSERT INTO bots (user_id, bot_name, bot_token, script) VALUES (?, ?, ?, ?)",
        (user_id, bot_name, bot_token, script)
    )
    await db.commit()

async def get_user_bots(user_id):
    db = await get_db()
    async with db.execute("SELECT * FROM bots WHERE user_id = ?", (user_id,)) as cursor:
        return await cursor.fetchall()

async def get_bot(user_id, bot_name):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM bots WHERE user_id = ? AND bot_name = ?", 
        (user_id, bot_name)
    ) as cursor:
        return await cursor.fetchone()

async def update_bot_status(user_id, bot_name, status):
    db = await get_db()
    await db.execute(
        "UPDATE bots SET status = ? WHERE user_id = ? AND bot_name = ?",
        (status, user_id, bot_name)
    )
    await db.commit()

async def update_bot_token(user_id, bot_name, new_token):
    db = await get_db()
    await db.execute(
        "UPDATE bots SET bot_token = ? WHERE user_id = ? AND bot_name = ?",
        (new_token, user_id, bot_name)
    )
    await db.commit()

async def delete_bot(user_id, bot_name):
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

async def renew_user_account(user_id, max_bots):
    db = await get_db()
    now = time.time()
    expires = now + (30 * 24 * 3600)
    
    await db.execute(
        "UPDATE users SET expires_at = ?, revoked = 0 WHERE id = ?",
        (expires, user_id)
    )
    await db.commit()
    print(f"user {user_id} renewed")

async def grant_script_access(user_id, script_name, granted_by):
    db = await get_db()
    now = time.time()
    
    await db.execute(
        "INSERT OR REPLACE INTO user_scripts (user_id, script_name, granted_at, granted_by) VALUES (?, ?, ?, ?)",
        (user_id, script_name, now, granted_by)
    )
    await db.commit()
    print(f"script {script_name} given to {user_id}")

async def revoke_script_access(user_id, script_name):
    db = await get_db()
    
    await db.execute(
        "DELETE FROM user_scripts WHERE user_id = ? AND script_name = ?",
        (user_id, script_name)
    )
    await db.commit()
    print(f"script {script_name} removed from {user_id}")

async def get_user_allowed_scripts(user_id):
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT script_name FROM user_scripts WHERE user_id = ?",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [row[0] for row in rows]

async def is_script_allowed(user_id, script_name):
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT 1 FROM user_scripts WHERE user_id = ? AND script_name = ?",
        (user_id, script_name)
    )
    row = await cursor.fetchone()
    return row is not None

async def log_admin_action(admin_id, action, target_user_id=None, details=None):
    db = await get_db()
    now = time.time()
    
    await db.execute(
        "INSERT INTO audit_logs (timestamp, admin_id, action, target_user_id, details) VALUES (?, ?, ?, ?, ?)",
        (now, admin_id, action, target_user_id, details)
    )
    await db.commit()
    print(f"admin {admin_id} did {action}")

async def get_audit_logs(limit=50):
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT id, timestamp, admin_id, action, target_user_id, details FROM audit_logs ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )
    return await cursor.fetchall()

async def update_crash_notification_time(user_id):
    db = await get_db()
    now = time.time()
    
    await db.execute(
        "UPDATE users SET last_crash_notification = ? WHERE id = ?",
        (now, user_id)
    )
    await db.commit()

async def update_expiry_notification_time(user_id):
    db = await get_db()
    now = time.time()
    
    await db.execute(
        "UPDATE users SET last_expiry_notification = ? WHERE id = ?",
        (now, user_id)
    )
    await db.commit()

async def get_users_needing_expiry_warning(days_before=5):
    db = await get_db()
    now = time.time()
    warning_threshold = now + (days_before * 24 * 3600)
    notification_cooldown = now - (24 * 3600)
    
    cursor = await db.execute(
        """SELECT id, expires_at FROM users 
           WHERE revoked = 0 
           AND expires_at < ? 
           AND expires_at > ? 
           AND (last_expiry_notification < ? OR last_expiry_notification = 0)""",
        (warning_threshold, now, notification_cooldown)
    )
    return await cursor.fetchall()