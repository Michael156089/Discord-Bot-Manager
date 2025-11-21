import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.manager_bot.main import bot, BOT_MANAGER_TOKEN

if __name__ == "__main__":
    if not BOT_MANAGER_TOKEN or BOT_MANAGER_TOKEN == "VOTRE_TOKEN_BOT_MANAGER":
        print("ERREUR: Le token du Bot Manager n'est pas configuré dans config.py.")
        exit()
    
    bot.run(BOT_MANAGER_TOKEN)