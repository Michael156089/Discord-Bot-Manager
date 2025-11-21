# Phase 3: Resource Monitoring Module
# File: src/manager_bot/resource_monitor.py

import psutil
import asyncio
from collections import defaultdict
from .config import DATA_DIR
import os
import json

MAX_CPU_PERCENT = 80.0
MAX_RAM_MB = 500

resource_violations = defaultdict(int)
VIOLATION_THRESHOLD = 3


def get_process_resources(pid: int) -> dict:
    """Get CPU and RAM usage for a process."""
    try:
        process = psutil.Process(pid)
        cpu_percent = process.cpu_percent(interval=1.0)
        memory_info = process.memory_info()
        ram_mb = memory_info.rss / (1024 * 1024)
        
        return {
            "cpu_percent": cpu_percent,
            "ram_mb": ram_mb,
            "cpu_exceeded": cpu_percent > MAX_CPU_PERCENT,
            "ram_exceeded": ram_mb > MAX_RAM_MB
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def check_resource_limits(user_id: int, bot_name: str, pid: int) -> tuple[bool, str]:
    """
    Check if a bot process is exceeding resource limits.
    Returns (should_terminate, reason).
    """
    resources = get_process_resources(pid)
    
    if resources is None:
        return False, ""
    
    key = (user_id, bot_name)
    
    if resources["cpu_exceeded"] or resources["ram_exceeded"]:
        resource_violations[key] += 1
        
        if resource_violations[key] >= VIOLATION_THRESHOLD:
            reasons = []
            if resources["cpu_exceeded"]:
                reasons.append(f"CPU {resources['cpu_percent']:.1f}% > {MAX_CPU_PERCENT}%")
            if resources["ram_exceeded"]:
                reasons.append(f"RAM {resources['ram_mb']:.1f}MB > {MAX_RAM_MB}MB")
            
            return True, ", ".join(reasons)
    else:
        if key in resource_violations:
            resource_violations[key] = 0
    
    return False, ""


def clear_violations(user_id: int, bot_name: str):
    """Clear resource violations for a bot."""
    key = (user_id, bot_name)
    if key in resource_violations:
        del resource_violations[key]


async def monitor_bot_resources(active_processes: dict, bot_manager):
    """
    Background task to monitor resource usage of all active bots.
    Terminates bots that exceed limits repeatedly.
    """
    await asyncio.sleep(30)
    
    while True:
        await asyncio.sleep(15)
        
        for key, (proc, is_connected) in list(active_processes.items()):
            user_id, bot_name = key
            
            if proc.returncode is not None:
                continue
            
            should_terminate, reason = check_resource_limits(user_id, bot_name, proc.pid)
            
            if should_terminate:
                print(f"⚠️ Bot '{bot_name}' (user {user_id}) dépassement de ressources: {reason}")
                print(f"   Arrêt forcé du bot...")
                
                try:
                    proc.terminate()
                    await asyncio.sleep(2)
                    
                    if proc.returncode is None:
                        proc.kill()
                    
                    clear_violations(user_id, bot_name)
                    
                except Exception as e:
                    print(f"❌ Erreur lors de l'arrêt du bot: {e}")
