import os
from cryptography.fernet import Fernet

BOT_MANAGER_TOKEN = "MTQyMjM5ODgzMDUxNDY3MTYyNg.GoNxOG.1KpfveEXlAP8f7vV8EBOjdGExp4FrICcHB2I_0"
ADMIN_IDS = [1278669161584922658]

ENCRYPTION_KEY = Fernet.generate_key()
cipher = Fernet(ENCRYPTION_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "utilisateurs")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")
SCRIPTS_ADMIN_DIR = os.path.join(BASE_DIR, "src", "manager_bot", "scripts_admin")
SECRETS_FILE = os.path.join(BASE_DIR, "secrets.json")
DB_PATH = os.path.join(DATA_DIR, "bot_manager.db")

for directory in [USERS_DIR, LOGS_DIR, DATA_DIR, SCRIPTS_ADMIN_DIR]:
    os.makedirs(directory, exist_ok=True)
