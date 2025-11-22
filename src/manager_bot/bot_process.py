import subprocess
import asyncio
import os
import sys
import time
from collections import defaultdict
from .config import USERS_DIR, LOGS_DIR
from .encryption import decrypt_token

active_processes = {}
crash_history = defaultdict(list)
MAX_CRASHES = 3
CRASH_WINDOW_SECONDS = 600


def should_auto_restart(user_id: int, bot_name: str) -> bool:
    """
    Determine if a bot should auto-restart based on crash history.
    Returns False if bot has crashed 3+ times in the last 10 minutes.
    """
    key = (user_id, bot_name)
    now = time.time()
    
    if key in crash_history:
        crash_history[key] = [t for t in crash_history[key] if now - t < CRASH_WINDOW_SECONDS]
    
    recent_crashes = len(crash_history.get(key, []))
    return recent_crashes < MAX_CRASHES


def record_crash(user_id: int, bot_name: str):
    """Record a bot crash timestamp."""
    key = (user_id, bot_name)
    crash_history[key].append(time.time())


def clear_crash_history(user_id: int, bot_name: str):
    """Clear crash history for a bot (e.g., when manually restarted)."""
    key = (user_id, bot_name)
    if key in crash_history:
        del crash_history[key]


def _setup_bot_environment(user_id: int, bot_name: str, decrypted_token: str):
    """Prépare l'environnement et les chemins pour l'exécution du bot utilisateur."""
    log_dir = os.path.join(LOGS_DIR, str(user_id))
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"{bot_name}.log")
    
    user_bot_base_dir = os.path.join(USERS_DIR, str(user_id))
    user_bot_scripts_dir = os.path.join(user_bot_base_dir, "scripts")
    
    env = os.environ.copy()
    env["DISCORD_BOT_TOKEN"] = decrypted_token
    env["DISCORD_TOKEN"] = decrypted_token  # Compatibilité avec les scripts utilisant DISCORD_TOKEN
    env["PYTHONPATH"] = user_bot_scripts_dir + os.pathsep + env.get("PYTHONPATH", "")
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
    
    if key in active_processes:
        proc, is_connected = active_processes[key]
        if proc.returncode is None:
            print(f"⚠️ Processus pour '{bot_name}' déjà en cours (PID {proc.pid})")
            return True
    
    clear_crash_history(user_id, bot_name)
    
    user_bot_base_dir, user_bot_scripts_dir, log_file_path, env = _setup_bot_environment(user_id, bot_name, decrypted_token)
    
    # Inject VIP IDs
    try:
        from .database import get_vip_users
        vip_users = await get_vip_users()
        env["VIP_IDS"] = ",".join(map(str, vip_users))
    except Exception as e:
        print(f"⚠️ Failed to fetch VIP users for {bot_name}: {e}")
    
    full_script_path = os.path.join(user_bot_scripts_dir, script)
    
    if not os.path.exists(full_script_path):
        print(f"❌ Script '{script}' introuvable:")
        print(f"   Chemin: {full_script_path}")
        print(f"   Dossier existe: {os.path.exists(user_bot_scripts_dir)}")
        if os.path.exists(user_bot_scripts_dir):
            print(f"   Fichiers: {os.listdir(user_bot_scripts_dir)}")
        return False

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
        
        active_processes[key] = (proc, False)
        print(f"✅ Bot '{bot_name}' (PID {proc.pid}) lancé. Attente connexion Discord...")
        
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
        
        try:
            proc.wait(timeout=3)
        except asyncio.TimeoutError:
            print(f"⚠️ Bot '{bot_name}' (user {user_id}) did not terminate gracefully, sending SIGKILL.")
            proc.kill()
        
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

from .database import get_bot

async def monitor_processes(bot):
    """Surveille les processus et détecte la connexion Discord."""
    await asyncio.sleep(5)
    
    while True:
        await asyncio.sleep(3)
        
        to_delete = []
        
        for key, (proc, is_connected) in list(active_processes.items()):
            user_id, bot_name = key
            
            if proc.returncode is not None:
                to_delete.append(key)
                if proc.returncode != 0:
                    print(f"💥 Bot '{bot_name}' (user {user_id}) crashé (code {proc.returncode})")
                    
                    record_crash(user_id, bot_name)
                    
                    # Tenter de notifier l'utilisateur
                    discord_user = bot.get_user(user_id)
                    if not discord_user:
                        try:
                            discord_user = await bot.fetch_user(user_id)
                        except:
                            pass

                    if should_auto_restart(user_id, bot_name):
                        print(f"🔄 Tentative de redémarrage auto pour '{bot_name}'...")
                        bot_data = await get_bot(user_id, bot_name)
                        
                        if bot_data:
                            # Attendre un peu avant de redémarrer
                            await asyncio.sleep(2)
                            success = await start_bot_process(user_id, bot_name, bot_data[3], bot_data[4])
                            
                            if success:
                                if discord_user:
                                    try:
                                        await discord_user.send(f"⚠️ Votre bot `{bot_name}` a crashé (code {proc.returncode}) mais a été redémarré automatiquement.")
                                    except: pass
                            else:
                                if discord_user:
                                    try:
                                        await discord_user.send(f"❌ Votre bot `{bot_name}` a crashé et le redémarrage automatique a échoué. Vérifiez les logs.")
                                    except: pass
                    else:
                        print(f"🛑 Bot '{bot_name}' a crashé trop souvent. Redémarrage automatique désactivé.")
                        if discord_user:
                            try:
                                await discord_user.send(f"🛑 Votre bot `{bot_name}` a crashé trop souvent (3 fois en 10min). Redémarrage automatique désactivé. Veuillez vérifier votre code et vos logs.")
                            except: pass
                        
                continue
            
            if not is_connected:
                log_file_path = os.path.join(LOGS_DIR, str(user_id), f"{bot_name}.log")
                
                if os.path.exists(log_file_path):
                    try:
                        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            f.seek(0, 2)
                            file_size = f.tell()
                            f.seek(max(0, file_size - 2048))
                            tail = f.read()
                            
                            if "[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE" in tail:
                                active_processes[key] = (proc, True)
                                print(f"🟢 Bot '{bot_name}' (user {user_id}) connecté à Discord!")
                    except Exception as e:
                        pass
        
        for key in to_delete:
            if key in active_processes: # Vérifier si pas déjà supprimé ou redémarré (si redémarré, la clé est recréée mais avec un nouveau process)
                # Ici active_processes[key] contient le VIEUX process si on n'a pas redémarré
                # Si on a redémarré, active_processes[key] contient le NOUVEAU process
                # Donc on ne doit supprimer que si le process dans active_processes est celui qui est mort
                current_proc, _ = active_processes[key]
                if current_proc.returncode is not None:
                     del active_processes[key]
