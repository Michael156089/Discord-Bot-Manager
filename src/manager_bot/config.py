import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# load the env file
load_dotenv()

# get variables
token = os.getenv("BOT_MANAGER_TOKEN")
key = os.getenv("ENCRYPTION_KEY")
admin_list = os.getenv("ADMIN_IDS")

if not key:
    key = Fernet.generate_key().decode()
    print("Warning: No key found, using generated key.")

# make the key thing
cipher = Fernet(key.encode())

# folders
base_dir = os.path.dirname(os.path.abspath(__file__))
users_folder = os.path.join(base_dir, "utilisateurs")
logs_folder = os.path.join(base_dir, "logs")
data_folder = os.path.join(base_dir, "data")
admin_scripts_folder = os.path.join(base_dir, "admin_scripts")
db_file = os.path.join(data_folder, "bot_manager.db")

# make folders if they dont exist
if not os.path.exists(users_folder):
    os.makedirs(users_folder)
if not os.path.exists(logs_folder):
    os.makedirs(logs_folder)
if not os.path.exists(data_folder):
    os.makedirs(data_folder)
if not os.path.exists(admin_scripts_folder):
    os.makedirs(admin_scripts_folder)

async def cleanup():
    print("cleaning up...")
    from .database import close_db
    await close_db()
