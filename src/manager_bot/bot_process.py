import asyncio
import os
import sys
from .config import USERS_DIR, LOGS_DIR
from .encryption import decrypt_token # Importation déplacée ici pour éviter les références circulaires

# active_processes stocke maintenant (proc, log_handle)
active_processes = {}

def _setup_bot_environment(user_id: int, bot_name: str, decrypted_token: str):
    """Prépare l'environnement et les chemins pour l'exécution du bot utilisateur."""
    log_dir = os.path.join(LOGS_DIR, str(user_id))
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"{bot_name}.log")
    
    user_bot_base_dir = os.path.join(USERS_DIR, str(user_id))
    user_bot_scripts_dir = os.path.join(user_bot_base_dir, "scripts") # Répertoire de travail
    
    env = os.environ.copy()
    env["DISCORD_BOT_TOKEN"] = decrypted_token
    # S'assurer que le chemin vers le script est accessible si le CWD change
    # Cela peut être utile si le script fait des imports relatifs.
    env["PYTHONPATH"] = user_bot_scripts_dir + os.pathsep + env.get("PYTHONPATH", "")

    return user_bot_base_dir, user_bot_scripts_dir, log_file_path, env

async def start_bot_process(user_id: int, bot_name: str, bot_token: str, script: str) -> bool:
    """Démarre un bot utilisateur en tant que sous-processus non bloquant.
    Retourne True si le processus Python est lancé/déjà en cours, False sinon."""
    try:
        decrypted_token = decrypt_token(bot_token)
    except Exception as e:
        print(f"Erreur decryption token pour {bot_name}: {e}")
        return False
    
    key = (user_id, bot_name)
    
    if key in active_processes:
        proc, _ = active_processes[key]
        if proc.returncode is None:
            print(f"Processus pour '{bot_name}' est deja en cours d'execution (PID {proc.pid})")
            return True
    
    user_bot_base_dir, user_bot_scripts_dir, log_file_path, env = _setup_bot_environment(user_id, bot_name, decrypted_token)
    script_name = script # Nom du fichier script
    
    full_script_path_check = os.path.join(user_bot_scripts_dir, script_name)
    if not os.path.exists(full_script_path_check):
        print(f"Erreur: Script '{script_name}' introuvable dans '{user_bot_scripts_dir}' pour l'utilisateur {user_id}")
        return False

    log_file_handle = open(log_file_path, "w")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, full_script_path_check, # ✅ Utiliser sys.executable et le chemin complet
            env=env,
            stdout=log_file_handle,
            stderr=asyncio.subprocess.STDOUT,
            cwd=user_bot_scripts_dir # ✅ Répertoire de travail pour le sous-processus
        )
        active_processes[key] = (proc, log_file_handle, False)
        print(f"Bot '{bot_name}' (PID {proc.pid}) lance. Attente de la connexion Discord...")
        return True
    except Exception as e:
        log_file_handle.close()
        print(f"Erreur inattendue lors du lancement du processus bot '{bot_name}': {e}")
        return False

def stop_bot_process(user_id: int, bot_name: str) -> bool:
    """Arrête un processus de bot et ferme son handle de fichier de log."""
    key = (user_id, bot_name)
    if key not in active_processes:
        return False
    
    proc, log_handle, _ = active_processes[key]
    
    if proc.returncode is not None:
        try:
            log_handle.close()
        except:
            pass
        del active_processes[key]
        return False
    
    try:
        proc.terminate()
        log_handle.close()
        del active_processes[key]
        print(f"Bot '{bot_name}' pour utilisateur {user_id} arrete.")
        return True
    except Exception as e:
        print(f"Erreur lors de l'arret du bot '{bot_name}': {e}")
        return False

def get_bot_status(user_id: int, bot_name: str) -> str:
    """Obtient le statut actuel d'un bot (niveau processus)."""
    key = (user_id, bot_name)
    if key not in active_processes:
        return "stopped"
    
    proc, _, is_connected = active_processes[key]
    if proc.returncode is not None:
        if proc.returncode == 0:
            return "stopped"
        else:
            return "crashed"
    else:
        # Processus en cours
        if is_connected:
            return "running" # Connecté à Discord
        else:
            return "starting" # Processus lancé, attente connexion

async def monitor_processes(bot):
    """Surveille les processus de bot et nettoie les processus terminés."""
    while True:
        await asyncio.sleep(5) # Vérification toutes les 5 secondes pour une réponse plus rapide
        
        finished_keys = []
        for key, (proc, log_handle, is_connected) in list(active_processes.items()):
            # 1. Nettoyer les processus terminés
            if proc.returncode is not None:
                try:
                    log_handle.close()
                except Exception as e:
                    print(f"Erreur fermeture log pour {key}: {e}")
                finished_keys.append(key)
                continue # Passer au suivant
            
            # 2. Vérifier la connexion si pas encore connecté
            if not is_connected:
                user_id, bot_name = key
                log_file_path = os.path.join(LOGS_DIR, str(user_id), f"{bot_name}.log")
                if os.path.exists(log_file_path):
                    try:
                        # Lire les dernières lignes du fichier
                        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            # Vérifier les 10 dernières lignes
                            for line in lines[-10:]:
                                if "[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE" in line:
                                    # ✅ Signal détecté, mettre à jour l'état
                                    active_processes[key] = (proc, log_handle, True)
                                    print(f"✅ Bot '{bot_name}' utilisateur {user_id} connecte a Discord.")
                                    break # Sortir de la boucle de lecture
                    except Exception as e:
                        # En cas d'erreur de lecture (fichier verrouillé, etc.), on continue
                        # La vérification se fera au prochain cycle
                        pass
        
        for key in finished_keys:
            del active_processes[key]
