import asyncio
import os
import sys
import time
from collections import defaultdict
from .config import users_folder, logs_folder
from .encryption import decrypt_token

active_processes = {}
crash_history = defaultdict(list)

def should_auto_restart(user_id, bot_name):
    key = (user_id, bot_name)
    now = time.time()
    if key in crash_history:
        crash_history[key] = [t for t in crash_history[key] if now - t < 600]
    return len(crash_history[key]) < 3

def record_crash(user_id, bot_name):
    crash_history[(user_id, bot_name)].append(time.time())

def clear_crash_history(user_id, bot_name):
    if (user_id, bot_name) in crash_history:
        del crash_history[(user_id, bot_name)]

async def start_bot_process(user_id, bot_name, token, script):
    try:
        dec_token = decrypt_token(token)
    except:
        print(f"Error decrypting token for {bot_name}")
        return False
        
    key = (user_id, bot_name)
    if key in active_processes:
        proc, _ = active_processes[key]
        if proc.returncode is None:
            print(f"{bot_name} already running")
            return True
            
    clear_crash_history(user_id, bot_name)
    
    log_dir = os.path.join(logs_folder, str(user_id))
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_path = os.path.join(log_dir, f"{bot_name}.log")
    
    user_folder = os.path.join(users_folder, str(user_id))
    script_folder = os.path.join(user_folder, "scripts")
    script_path = os.path.join(script_folder, script)
    
    if not os.path.exists(script_path):
        print(f"Script not found: {script_path}")
        return False
        
    env = os.environ.copy()
    env["DISCORD_TOKEN"] = dec_token
    env["PYTHONUNBUFFERED"] = "1"
    
    try:
        log_file = open(log_path, "a", buffering=1, encoding='utf-8')
        log_file.write(f"\n--- Starting {bot_name} ---\n")
    except:
        print("Error opening log")
        return False
        
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_path,
            env=env,
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
            cwd=script_folder
        )
        active_processes[key] = (proc, False)
        print(f"Started {bot_name} (PID {proc.pid})")
        return True
    except Exception as e:
        print(f"Error starting {bot_name}: {e}")
        log_file.close()
        return False

def stop_bot_process(user_id, bot_name):
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
        print(f"Stopped {bot_name}")
        return True
    except:
        return False

def get_bot_status(user_id, bot_name):
    key = (user_id, bot_name)
    if key not in active_processes:
        return "stopped"
    proc, connected = active_processes[key]
    if proc.returncode is not None:
        return "crashed" if proc.returncode != 0 else "stopped"
    return "running" if connected else "starting"

async def monitor_processes(bot):
    from .database import get_bot
    while True:
        await asyncio.sleep(5)
        to_del = []
        
        for key, (proc, connected) in list(active_processes.items()):
            uid, name = key
            if proc.returncode is not None:
                to_del.append(key)
                if proc.returncode != 0:
                    print(f"{name} crashed")
                    record_crash(uid, name)
                    if should_auto_restart(uid, name):
                        print(f"Restarting {name}...")
                        data = await get_bot(uid, name)
                        if data:
                            await asyncio.sleep(2)
                            await start_bot_process(uid, name, data[3], data[4])
            
            if not connected:
                # check logs for connection
                pass # simplified, assume connected eventually or just stay 'starting'
                
        for k in to_del:
            if k in active_processes:
                p, _ = active_processes[k]
                if p.returncode is not None:
                    del active_processes[k]
