import subprocess
import os
import asyncio
from config import USERS_DIR, LOGS_DIR
from encryption import decrypt_token

active_processes = {}
MAX_AUTO_RESTARTS = 3 # Nouvelle constante: limite de 3 redémarrages automatiques

# Fonction utilitaire pour configurer l'environnement et ouvrir le fichier de log
def _setup_bot_environment(user_id: int, bot_name: str, decrypted_token: str):
    user_dir = os.path.join(USERS_DIR, str(user_id))
    scripts_dir = os.path.join(user_dir, "scripts") # Chemin vers le dossier 'scripts' de l'utilisateur
    log_dir = os.path.join(LOGS_DIR, str(user_id))
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"{bot_name}.log")
    
    env = os.environ.copy()
    env["BOT_TOKEN"] = decrypted_token
    
    # Ajoute le répertoire 'scripts' au PYTHONPATH du sous-processus
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{scripts_dir}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = scripts_dir
    
    # On retourne le descripteur de fichier ouvert pour le subprocess
    return user_dir, log_file_path, env

def start_bot_process(user_id: int, bot_name: str, bot_token: str, script: str):
    key = f"{user_id}_{bot_name}"
    
    # Arrête le processus existant si présent pour ce bot
    if key in active_processes and active_processes[key]["process"].poll() is None:
        active_processes[key]["process"].terminate()
        try: active_processes[key]["process"].wait(timeout=5)
        except subprocess.TimeoutExpired: active_processes[key]["process"].kill()

    decrypted_token = decrypt_token(bot_token)
    user_dir, log_file_path, env = _setup_bot_environment(user_id, bot_name, decrypted_token)
    script_path = os.path.join(user_dir, "scripts", script)

    # Ouvre le fichier de log pour le nouveau subprocess
    with open(log_file_path, "a") as log:
        process = subprocess.Popen(
            ["python", script_path],
            env=env,
            stdout=log,
            stderr=log,
            cwd=user_dir # Le cwd est le dossier de l'utilisateur, pas le dossier scripts
        )
    
    # Initialise ou réinitialise le compteur de redémarrages automatiques pour un démarrage manuel
    active_processes[key] = {"process": process, "auto_restart_count": 0}
    return process

def stop_bot_process(user_id: int, bot_name: str):
    key = f"{user_id}_{bot_name}"
    if key in active_processes:
        process = active_processes[key]["process"]
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        del active_processes[key] # Supprime le bot des processus actifs
        return True
    return False

def get_bot_status(user_id: int, bot_name: str):
    key = f"{user_id}_{bot_name}"
    if key in active_processes:
        process_info = active_processes[key]
        process = process_info["process"]
        if process.poll() is None: # Processus toujours en cours d'exécution
            return "running"
        else: # Processus est mort
            if process_info["auto_restart_count"] >= MAX_AUTO_RESTARTS:
                return "crashed_permanently" # A atteint la limite de redémarrages
            return "crashed" # Planté, mais pourrait être redémarré
    return "stopped" # N'est pas dans les processus actifs

async def monitor_processes(bot_manager):
    while True:
        await asyncio.sleep(30) # Vérifie toutes les 30 secondes
        from database import get_bot, update_bot_status # Importation nécessaire ici

        for key in list(active_processes.keys()): # Itère sur une copie des clés pour éviter des erreurs si `active_processes` est modifié
            process_info = active_processes[key]
            process = process_info["process"]
            
            if process.poll() is not None: # Le processus du bot est mort
                user_id, bot_name = key.split("_", 1)
                user_id = int(user_id)
                
                # Incrémente le compteur de redémarrages automatiques
                process_info["auto_restart_count"] += 1
                
                if process_info["auto_restart_count"] <= MAX_AUTO_RESTARTS:
                    # Tente de redémarrer le bot
                    try:
                        user = await bot_manager.fetch_user(user_id)
                        await user.send(f"⚠️ Votre bot `{bot_name}` s'est arrêté (tentative {process_info['auto_restart_count']}/{MAX_AUTO_RESTARTS}). Redémarrage automatique...")
                        
                        bot_data = await get_bot(user_id, bot_name)
                        if bot_data:
                            decrypted_token = decrypt_token(bot_data[3]) # Token chiffré stocké en bot_data[3]
                            user_dir, log_file_path, env = _setup_bot_environment(user_id, bot_name, decrypted_token)
                            script_path = os.path.join(user_dir, "scripts", bot_data[4]) # Script stocké en bot_data[4]

                            with open(log_file_path, "a") as log:
                                new_process = subprocess.Popen(
                                    ["python", script_path],
                                    env=env,
                                    stdout=log,
                                    stderr=log,
                                    cwd=user_dir
                                )
                            active_processes[key]["process"] = new_process # Met à jour le processus Popen
                            await update_bot_status(user_id, bot_name, "running") # Met à jour le statut dans la DB
                            await user.send(f"✅ Bot `{bot_name}` redémarré avec succès.")
                    except Exception as e:
                        # Si le redémarrage échoue, on continue le cycle pour potentiellement atteindre la limite
                        print(f"Erreur lors du redémarrage automatique du bot {bot_name}: {e}")
                        await update_bot_status(user_id, bot_name, "crashed") # Marque comme crashé si le redémarrage échoue
                else:
                    # Le bot a atteint la limite de redémarrages
                    try:
                        user = await bot_manager.fetch_user(user_id)
                        await user.send(f"❌ Votre bot `{bot_name}` a atteint la limite de {MAX_AUTO_RESTARTS} redémarrages automatiques et a été arrêté. Veuillez vérifier vos logs pour les erreurs.")
                        await update_bot_status(user_id, bot_name, "crashed_permanently") # Statut permanent dans la DB
                    except Exception as e:
                        print(f"Erreur lors de l'envoi du message d'arrêt permanent pour {bot_name}: {e}")
                    finally:
                        del active_processes[key] # Supprime définitivement le bot de la surveillance
