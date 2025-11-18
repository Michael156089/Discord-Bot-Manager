import aiosqlite
import json
from datetime import datetime, timedelta
from .config import DB_PATH, SECRETS_FILE
import os
import secrets

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                max_bots INTEGER,
                registered_at TEXT
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
        await db.commit()

def load_secrets():
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_secrets(secrets_data):
    with open(SECRETS_FILE, 'w') as f:
        json.dump(secrets_data, f, indent=4)

def create_secret(user_id: int, max_bots: int) -> str:
    secrets_data = load_secrets()
    secret_id = secrets.token_urlsafe(32)
    expiration = (datetime.now() + timedelta(days=30)).isoformat()
    
    secrets_data[secret_id] = {
        "user_id": user_id,
        "max_bots": max_bots,
        "expiration": expiration,
        "consumed": False
    }
    
    save_secrets(secrets_data)
    return secret_id

def validate_secret(secret_id: str):
    secrets_data = load_secrets()
    
    if secret_id not in secrets_data:
        return None, "Secret invalide"
    
    secret = secrets_data[secret_id]
    
    if secret["consumed"]:
        return None, "Secret deja utilise"
    
    if datetime.fromisoformat(secret["expiration"]) < datetime.now():
        return None, "Secret expire"
    
    return secret, None

def consume_secret(secret_id: str):
    secrets_data = load_secrets()
    secrets_data[secret_id]["consumed"] = True
    save_secrets(secrets_data)

async def register_user(user_id: int, max_bots: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, max_bots, registered_at) VALUES (?, ?, ?)",
            (user_id, max_bots, datetime.now().isoformat())
        )
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def add_bot_to_db(user_id: int, bot_name: str, bot_token: str, script: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bots (user_id, bot_name, bot_token, script) VALUES (?, ?, ?, ?)",
            (user_id, bot_name, bot_token, script)
        )
        await db.commit()

async def get_user_bots(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM bots WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchall()

async def get_bot(user_id: int, bot_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM bots WHERE user_id = ? AND bot_name = ?", 
            (user_id, bot_name)
        ) as cursor:
            return await cursor.fetchone()

async def update_bot_status(user_id: int, bot_name: str, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bots SET status = ? WHERE user_id = ? AND bot_name = ?",
            (status, user_id, bot_name)
        )
        await db.commit()

async def update_bot_token(user_id: int, bot_name: str, new_token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bots SET bot_token = ? WHERE user_id = ? AND bot_name = ?",
            (new_token, user_id, bot_name)
        )
        await db.commit()

async def delete_bot(user_id: int, bot_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM bots WHERE user_id = ? AND bot_name = ?",
            (user_id, bot_name)
        )
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users") as cursor:
            return await cursor.fetchall()

async def revoke_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bots WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()
