import sys
import os

# Ajoute le répertoire racine au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importe et exécute le module
from src.manager_bot.main import bot, BOT_MANAGER_TOKEN

if __name__ == "__main__":
    if not BOT_MANAGER_TOKEN or BOT_MANAGER_TOKEN == "VOTRE_TOKEN_BOT_MANAGER":
        print("ERREUR: Le token du Bot Manager n'est pas configuré dans config.py.")
        exit()
    
    # Lance simplement le bot - la synchro se fera dans on_ready()
    bot.run(BOT_MANAGER_TOKEN)