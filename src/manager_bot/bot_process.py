import asyncio
import os
from .config import USERS_DIR, LOGS_DIR
from .encryption import decrypt_token

# active_processes stocke maintenant (proc, log_handle)
active_processes = {}

def _setup_bot_environment(user_id: int, bot_name: str, decrypted_token: str):
    """Prépare l'environnement et les chemins pour l'exécution du bot utilisateur."""
    log_dir = os.path.join(LOGS_DIR, str(user_id))
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"{bot_name}.log")
    
    user_bot_base_dir = os.path.join(USERS_DIR, str(user_id))
    # Le répertoire où le script du bot utilisateur sera exécuté
    user_bot_scripts_dir = os.path.join(user_bot_base_dir, "scripts")
    
    env = os.environ.copy()
    env["DISCORD_BOT_TOKEN"] = decrypted_token
    
    return user_bot_base_dir, user_bot_scripts_dir, log_file_path, env

async def start_bot_process(user_id: int, bot_name: str, bot_token: str, script: str) -> bool:
    """Démarre un bot utilisateur en tant que sous-processus non bloquant.
    Retourne True si le processus est lancé/déjà en cours, False sinon."""
    try:
        decrypted_token = decrypt_token(bot_token)
    except Exception as e:
        print(f"Erreur decryption token pour {bot_name}: {e}")
        return False # Échec de la décryption
    
    key = (user_id, bot_name)
    
    # Vérifier si le bot est déjà en cours
    if key in active_processes:
        proc, _ = active_processes[key]
        if proc.returncode is None:  # Toujours en cours d'exécution
            print(f"Processus pour {bot_name} est déjà en cours d'exécution (PID {proc.pid})")
            return True # Considérer comme un succès si déjà running
    
    user_bot_base_dir, user_bot_scripts_dir, log_file_path, env = _setup_bot_environment(user_id, bot_name, decrypted_token)
    
    # Le nom du script lui-même (ex: "utility.py")
    script_name = script
    
    # Vérifier si le script existe avant de le lancer
    full_script_path_check = os.path.join(user_bot_scripts_dir, script_name)
    if not os.path.exists(full_script_path_check):
        print(f"Erreur: Script '{script_name}' introuvable dans '{user_bot_scripts_dir}' pour l'utilisateur {user_id}")
        return False # Échec: script non trouvé

    # Ouvrir le fichier de log et le garder ouvert tant que le processus est actif
    # Le fichier sera fermé dans stop_bot_process ou monitor_processes
    log_file_handle = open(log_file_path, "w")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "python", script_name, # Exécuter le script par son nom
            env=env,
            stdout=log_file_handle,
            stderr=asyncio.subprocess.STDOUT,
            cwd=user_bot_scripts_dir # Définir le répertoire de travail du sous-processus
        )
        active_processes[key] = (proc, log_file_handle)
        print(f"Bot '{bot_name}' demarre pour l'utilisateur {user_id} (PID {proc.pid}) depuis '{user_bot_scripts_dir}'")
        return True
    except Exception as e:
        # En cas d'échec de lancement, fermer le handle du fichier
        log_file_handle.close()
        print(f"Erreur inattendue lors du demarrage du bot '{bot_name}': {e}")
        return False

def stop_bot_process(user_id: int, bot_name: str) -> bool:
    """Arrête un processus de bot et ferme son handle de fichier de log."""
    key = (user_id, bot_name)
    if key not in active_processes:
        return False
    
    proc, log_handle = active_processes[key]
    
    if proc.returncode is not None:  # Le processus est déjà terminé
        try:
            log_handle.close() # S'assurer que le log est fermé
        except:
            pass
        del active_processes[key]
        return False
    
    try:
        proc.terminate() # Envoie un signal de terminaison (SIGTERM)
        log_handle.close() # Ferme le fichier de log
        del active_processes[key] # Supprime l'entrée des processus actifs
        print(f"Bot '{bot_name}' pour utilisateur {user_id} arrêté.")
        return True
    except Exception as e:
        print(f"Erreur lors de l'arrêt du bot '{bot_name}': {e}")
        return False

def get_bot_status(user_id: int, bot_name: str) -> str:
    """Obtient le statut actuel d'un bot sans interroger la DB."""
    key = (user_id, bot_name)
    if key not in active_processes:
        return "stopped"
    
    proc, _ = active_processes[key]
    if proc.returncode is None: # Le processus est toujours en cours
        return "running"
    elif proc.returncode == 0: # Le processus s'est terminé normalement
        return "stopped"
    else: # Le processus s'est terminé avec une erreur
        return "crashed"

async def monitor_processes(bot):
    """Surveille les processus de bot et nettoie les processus terminés."""
    while True:
        await asyncio.sleep(10) # Vérifie toutes les 10 secondes
        
        finished_keys = []
        for key, (proc, log_handle) in active_processes.items():
            if proc.returncode is not None: # Le processus est terminé
                try:
                    log_handle.close() # S'assurer que le log est fermé
                except Exception as e:
                    print(f"Erreur fermeture log pour {key}: {e}")
                finished_keys.append(key)
        
        for key in finished_keys:
            del active_processes[key]
        
        # Pour des logs plus détaillés ou des tentatives de redémarrage des bots crashés,
        # vous pouvez analyser proc.returncode ou le contenu du fichier de log ici.
