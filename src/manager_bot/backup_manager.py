# Phase 4: Automatic Backup Manager
# File: src/manager_bot/backup_manager.py

import os
import shutil
import gzip
import asyncio
from datetime import datetime
from .config import DATA_DIR, DB_PATH

BACKUP_DIR = os.path.join(DATA_DIR, "backups")
MAX_BACKUPS = 7


def create_backup() -> str:
    """
    Create a compressed backup of the database.
    Returns the backup file path.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"bot_manager_backup_{timestamp}.db.gz"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    if not os.path.exists(DB_PATH):
        print(f"⚠️ Base de données introuvable: {DB_PATH}")
        return None
    
    try:
        with open(DB_PATH, 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        print(f"✅ Backup créé: {backup_filename}")
        return backup_path
        
    except Exception as e:
        print(f"❌ Erreur création backup: {e}")
        return None


def cleanup_old_backups():
    """Delete old backups, keeping only the most recent MAX_BACKUPS."""
    if not os.path.exists(BACKUP_DIR):
        return
    
    backups = []
    for filename in os.listdir(BACKUP_DIR):
        if filename.endswith('.db.gz'):
            filepath = os.path.join(BACKUP_DIR, filename)
            backups.append((filepath, os.path.getmtime(filepath)))
    
    backups.sort(key=lambda x: x[1], reverse=True)
    
    for filepath, _ in backups[MAX_BACKUPS:]:
        try:
            os.remove(filepath)
            print(f"🗑️ Ancien backup supprimé: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"❌ Erreur suppression backup: {e}")


def restore_backup(backup_path: str) -> bool:
    """
    Restore database from a backup file.
    Returns True if successful.
    """
    if not os.path.exists(backup_path):
        print(f"❌ Backup introuvable: {backup_path}")
        return False
    
    try:
        backup_temp = DB_PATH + ".backup_temp"
        
        with gzip.open(backup_path, 'rb') as f_in:
            with open(backup_temp, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        if os.path.exists(DB_PATH):
            os.replace(backup_temp, DB_PATH)
        else:
            shutil.move(backup_temp, DB_PATH)
        
        print(f"✅ Base de données restaurée depuis: {os.path.basename(backup_path)}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur restauration backup: {e}")
        if os.path.exists(backup_temp):
            os.remove(backup_temp)
        return False


async def daily_backup_task():
    """Background task that creates daily backups."""
    await asyncio.sleep(60)
    
    while True:
        print("🔄 Démarrage backup quotidien...")
        
        create_backup()
        cleanup_old_backups()
        
        await asyncio.sleep(24 * 3600)
