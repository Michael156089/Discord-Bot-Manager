import asyncio
import os
import sys
from .config import USERS_DIR, LOGS_DIR
from .encryption import decrypt_token

# ✅ Structure: {(user_id, bot_name): (proc, is_connected)}
active_processes = {}

def _setup_bot_environment(user_id: int, bot_name: str, decrypted_token: str):
    """Prépare l'environnement et les chemins pour l'exécution du bot utilisateur."""
    log_dir = os.path.join(LOGS_DIR, str(user_id))
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"{bot_name}.log")
    
    user_bot_base_dir = os.path.join(USERS_DIR, str(user_id))
    user_bot_scripts_dir = os.path.join(user_bot_base_dir, "scripts")
    
    env = os.environ.copy()
    env["DISCORD_BOT_TOKEN"] = decrypted_token
    env["PYTHONPATH"] = user_bot_scripts_dir + os.pathsep + env.get("PYTHONPATH", "")
    # ✅ CRITIQUE: Mode unbuffered pour flush immédiat des logs
    env["PYTHONUNBUFFERED"] = "1"

    return user_bot_base_dir, user_bot_scripts_dir, log_file_path, env

async def start_bot_process(user_id: int, bot_name: str, bot_token: str, script: str) -> bool:
    """Démarre un bot utilisateur en tant que sous-processus non bloquant."""
    try:
        decrypted_token = decrypt_token(bot_token)
    except Exception as e:
        print(f"❌ Erreur decryption token pour {bot_name}: {e}")
        return False
    
    key = (user_id, bot_name)
    
    # ✅ Vérifier si déjà en cours
    if key in active_processes:
        proc, is_connected = active_processes[key]
        if proc.returncode is None:
            print(f"⚠️ Processus pour '{bot_name}' déjà en cours (PID {proc.pid})")
            return True
    
    user_bot_base_dir, user_bot_scripts_dir, log_file_path, env = _setup_bot_environment(user_id, bot_name, decrypted_token)
    
    full_script_path = os.path.join(user_bot_scripts_dir, script)
    
    # ✅ Vérification détaillée avec debug
    if not os.path.exists(full_script_path):
        print(f"❌ Script '{script}' introuvable:")
        print(f"   Chemin: {full_script_path}")
        print(f"   Dossier existe: {os.path.exists(user_bot_scripts_dir)}")
        if os.path.exists(user_bot_scripts_dir):
            print(f"   Fichiers: {os.listdir(user_bot_scripts_dir)}")
        return False

    # ✅ Ouvrir en mode append avec line buffering
    try:
        log_file_handle = open(log_file_path, "a", buffering=1, encoding='utf-8')
        log_file_handle.write(f"\n{'='*60}\n")
        log_file_handle.write(f"🚀 [{bot_name}] Démarrage - {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file_handle.write(f"{'='*60}\n")
        log_file_handle.flush()
    except Exception as e:
        print(f"❌ Erreur ouverture log pour {bot_name}: {e}")
        return False
    
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, full_script_path,
            env=env,
            stdout=log_file_handle,
            stderr=asyncio.subprocess.STDOUT,
            cwd=user_bot_scripts_dir
        )
        
        # ✅ Stocker avec is_connected=False
        active_processes[key] = (proc, False)
        print(f"✅ Bot '{bot_name}' (PID {proc.pid}) lancé. Attente connexion Discord...")
        
        # ✅ Fermer le handle après 2 secondes (le processus garde sa propre référence)
        asyncio.create_task(_close_log_handle_delayed(log_file_handle))
        
        return True
    except Exception as e:
        log_file_handle.close()
        print(f"❌ Erreur lancement '{bot_name}': {e}")
        return False

async def _close_log_handle_delayed(handle):
    """Ferme le handle après 2s pour permettre au processus de démarrer."""
    await asyncio.sleep(2)
    try:
        handle.close()
    except:
        pass

def stop_bot_process(user_id: int, bot_name: str) -> bool:
    """Arrête un processus de bot."""
    key = (user_id, bot_name)
    if key not in active_processes:
        return False
    
    proc, _ = active_processes[key]
    
    if proc.returncode is not None:
        del active_processes[key]
        return False
    
    try:
        proc.terminate()
        del active_processes[key]
        print(f"🛑 Bot '{bot_name}' (user {user_id}) arrêté.")
        return True
    except Exception as e:
        print(f"❌ Erreur arrêt '{bot_name}': {e}")
        return False

def get_bot_status(user_id: int, bot_name: str) -> str:
    """Obtient le statut actuel d'un bot."""
    key = (user_id, bot_name)
    if key not in active_processes:
        return "stopped"
    
    proc, is_connected = active_processes[key]
    
    if proc.returncode is not None:
        return "crashed" if proc.returncode != 0 else "stopped"
    
    return "running" if is_connected else "starting"

async def monitor_processes(bot):
    """Surveille les processus et détecte la connexion Discord."""
    await asyncio.sleep(5)  # Délai initial
    
    while True:
        await asyncio.sleep(3)  # Vérification toutes les 3 secondes
        
        to_delete = []
        
        for key, (proc, is_connected) in list(active_processes.items()):
            user_id, bot_name = key
            
            # ✅ 1. Nettoyer processus terminés
            if proc.returncode is not None:
                to_delete.append(key)
                if proc.returncode != 0:
                    print(f"💥 Bot '{bot_name}' (user {user_id}) crashé (code {proc.returncode})")
                continue
            
            # ✅ 2. Vérifier connexion si pas encore connecté
            if not is_connected:
                log_file_path = os.path.join(LOGS_DIR, str(user_id), f"{bot_name}.log")
                
                if os.path.exists(log_file_path):
                    try:
                        # ✅ Lecture efficace: seulement les derniers 2KB
                        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            f.seek(0, 2)  # Fin du fichier
                            file_size = f.tell()
                            f.seek(max(0, file_size - 2048))  # Lire max 2KB
                            tail = f.read()
                            
                            if "[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE" in tail:
                                active_processes[key] = (proc, True)
                                print(f"🟢 Bot '{bot_name}' (user {user_id}) connecté à Discord!")
                    except Exception as e:
                        # Fichier verrouillé, réessayer au prochain cycle
                        pass
        
        # ✅ 3. Supprimer les processus terminés
        for key in to_delete:
            del active_processes[key]
