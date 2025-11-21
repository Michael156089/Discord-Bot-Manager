import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import asyncio

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".env"))

BOT_MANAGER_TOKEN = os.getenv("BOT_MANAGER_TOKEN")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
ADMIN_IDS = [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]
USERS_DIR = os.getenv("USERS_DIR", os.path.join(os.path.dirname(__file__), "users"))
SCRIPTS_ADMIN_DIR = os.getenv("SCRIPTS_ADMIN_DIR", os.path.join(os.path.dirname(__file__), "admin_scripts"))

if not BOT_MANAGER_TOKEN or BOT_MANAGER_TOKEN == "VOTRE_TOKEN_BOT_MANAGER":
    raise EnvironmentError("BOT_MANAGER_TOKEN not set in environment (.env).")

if not ENCRYPTION_KEY:
    raise EnvironmentError("ENCRYPTION_KEY not set in environment (.env). Provide a fixed key to persist encrypted tokens across restarts.")

cipher = Fernet(ENCRYPTION_KEY.encode())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SCRIPTS_ADMIN_DIR = os.path.join(BASE_DIR, "admin_scripts")

USERS_DIR = os.path.join(BASE_DIR, "utilisateurs")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")
SCRIPTS_ADMIN_DIR = os.path.join(BASE_DIR, "admin_scripts")
DB_PATH = os.path.join(DATA_DIR, "bot_manager.db")

for directory in [USERS_DIR, LOGS_DIR, DATA_DIR, SCRIPTS_ADMIN_DIR]:
    os.makedirs(directory, exist_ok=True)

async def shutdown_handler():
    """Clean up resources on bot shutdown."""
    from .database import close_db
    await close_db()
    print("Cleanup complete.")
