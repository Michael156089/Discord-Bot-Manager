import asyncio
import os
from .config import USERS_DIR, LOGS_DIR
from .encryption import decrypt_token

active_processes = {}  # (user_id, bot_name) -> asyncio.subprocess.Process
MAX_AUTO_RESTARTS = 3 

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

async def start_bot_process(user_id: int, bot_name: str, bot_token: str, script: str):
    """Start a bot using async subprocess (non-blocking)."""
    log_dir = os.path.join(LOGS_DIR, str(user_id))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{bot_name}.log")

    key = (user_id, bot_name)
    
    # Évite de démarrer un processus en double
    if key in active_processes:
        proc = active_processes[key]
        if proc.returncode is None:  # Toujours en cours d'exécution
            raise RuntimeError(f"Processus pour {bot_name} déjà en cours (PID {proc.pid})")

    decrypted_token = decrypt_token(bot_token)
    user_dir, env = _setup_bot_environment(user_id, bot_name, decrypted_token)
    script_path = os.path.join(user_dir, "scripts", script)

    # Utilise asyncio.create_subprocess_exec (non-bloquant)
    proc = await asyncio.create_subprocess_exec(
        "python", script_path,
        env=env,
        stdout=open(log_file, "w"),
        stderr=asyncio.subprocess.STDOUT,
        cwd=user_dir
    )
    
    active_processes[key] = proc
    print(f"Bot démarré {bot_name} pour l'utilisateur {user_id} (PID {proc.pid})")

def stop_bot_process(user_id: int, bot_name: str) -> bool:
    """Stop a bot process."""
    key = (user_id, bot_name)
    if key not in active_processes:
        return False
    
    proc = active_processes[key]
    if proc.returncode is not None:  # Déjà arrêté
        return False
    
    # Envoie SIGTERM, laisse-le s'arrêter gracieusement
    try:
        proc.terminate()
        return True
    except:
        return False

def get_bot_status(user_id: int, bot_name: str) -> str:
    """Get current bot status without querying DB."""
    key = (user_id, bot_name)
    if key not in active_processes:
        return "stopped"
    
    proc = active_processes[key]
    if proc.returncode is None:
        return "running"
    elif proc.returncode == 0:
        return "stopped"
    else:
        return "crashed"

async def monitor_processes(bot_manager):
    """Monitor and cleanup dead processes (run as background task)."""
    while True:
        await asyncio.sleep(10)  # Vérifie toutes les 10 secondes
        
        # Supprime les processus terminés du suivi
        finished = [k for k, p in active_processes.items() if p.returncode is not None]
        for key in finished:
            del active_processes[key]
        
        # Optionnel : redémarrer les bots plantés (implémenter la logique de réessai ici si nécessaire)
