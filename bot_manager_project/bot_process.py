import subprocess
import os
import asyncio
from config import USERS_DIR, LOGS_DIR
from encryption import decrypt_token

active_processes = {}

def start_bot_process(user_id: int, bot_name: str, bot_token: str, script: str):
    user_dir = os.path.join(USERS_DIR, str(user_id))
    script_path = os.path.join(user_dir, "scripts", script)
    log_dir = os.path.join(LOGS_DIR, str(user_id))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{bot_name}.log")
    
    decrypted_token = decrypt_token(bot_token)
    
    env = os.environ.copy()
    env["BOT_TOKEN"] = decrypted_token
    
    with open(log_file, "a") as log:
        process = subprocess.Popen(
            ["python", script_path],
            env=env,
            stdout=log,
            stderr=log,
            cwd=user_dir
        )
    
    key = f"{user_id}_{bot_name}"
    active_processes[key] = process
    return process

def stop_bot_process(user_id: int, bot_name: str):
    key = f"{user_id}_{bot_name}"
    if key in active_processes:
        process = active_processes[key]
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        del active_processes[key]
        return True
    return False

def get_bot_status(user_id: int, bot_name: str):
    key = f"{user_id}_{bot_name}"
    if key in active_processes:
        process = active_processes[key]
        if process.poll() is None:
            return "running"
        else:
            del active_processes[key]
            return "crashed"
    return "stopped"

async def monitor_processes(bot_manager):
    while True:
        await asyncio.sleep(30)
        for key in list(active_processes.keys()):
            process = active_processes[key]
            if process.poll() is not None:
                user_id, bot_name = key.split("_", 1)
                user_id = int(user_id)
                
                try:
                    user = await bot_manager.fetch_user(user_id)
                    await user.send(f" Votre bot `{bot_name}` s'est arrete. Redemarrage automatique...")
                    
                    from database import get_bot
                    bot_data = await get_bot(user_id, bot_name)
                    if bot_data:
                        start_bot_process(user_id, bot_name, bot_data[3], bot_data[4])
                        await user.send(f" Bot `{bot_name}` redemarre avec succes.")
                except:
                    pass
