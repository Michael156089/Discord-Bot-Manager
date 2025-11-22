import os
import json
import hashlib
import shutil
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from .script_version_db import (
    register_script_version,
    get_latest_script_version,
    get_user_script_version,
    set_user_script_version,
    get_migrations,
    mark_migration_applied
)
from .config import ADMIN_SCRIPTS_DIR, USER_SCRIPTS_DIR

def parse_script_metadata(script_path: str) -> Optional[Dict]:
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata_pattern = r'SCRIPT_METADATA\s*=\s*({[^}]+})'
        match = re.search(metadata_pattern, content, re.DOTALL)
        
        if not match:
            return None
        
        metadata_str = match.group(1)
        metadata_str = re.sub(r'#.*', '', metadata_str)
        metadata_str = re.sub(r"'", '"', metadata_str)
        
        metadata = json.loads(metadata_str)
        return metadata
    except Exception as e:
        print(f"Error parsing metadata from {script_path}: {e}")
        return None

def calculate_file_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def compare_versions(v1: str, v2: str) -> int:
    def parse_version(v):
        parts = v.split('.')
        return tuple(int(p) for p in parts if p.isdigit())
    
    try:
        v1_parts = parse_version(v1)
        v2_parts = parse_version(v2)
        
        if v1_parts < v2_parts:
            return -1
        elif v1_parts > v2_parts:
            return 1
        else:
            return 0
    except:
        return 0

async def scan_and_register_scripts():
    admin_scripts_path = Path(ADMIN_SCRIPTS_DIR)
    
    for category in ['basic', 'premium']:
        category_path = admin_scripts_path / category
        if not category_path.exists():
            continue
        
        for script_file in category_path.glob('*.py'):
            if script_file.name.startswith('_'):
                continue
            
            metadata = parse_script_metadata(str(script_file))
            if not metadata:
                print(f"Warning: {script_file.name} has no metadata")
                continue
            
            file_hash = calculate_file_hash(str(script_file))
            
            await register_script_version(
                script_name=metadata['name'],
                version=metadata['version'],
                file_hash=file_hash,
                db_schema_version=metadata.get('db_schema_version', 1),
                changelog=json.dumps(metadata.get('changelog', {}))
            )
    
    print("Script versions registered successfully")

async def is_update_available(user_id: int, script_name: str) -> Tuple[bool, Optional[str], Optional[str]]:
    user_version_data = await get_user_script_version(user_id, script_name)
    if not user_version_data:
        return False, None, None
    
    installed_version = user_version_data[0]
    
    latest_version_data = await get_latest_script_version(script_name)
    if not latest_version_data:
        return False, None, None
    
    latest_version = latest_version_data[0]
    
    if compare_versions(installed_version, latest_version) < 0:
        return True, installed_version, latest_version
    
    return False, installed_version, latest_version

async def get_script_info(script_name: str) -> Optional[Dict]:
    latest_version_data = await get_latest_script_version(script_name)
    if not latest_version_data:
        return None
    
    version, file_hash, db_schema, deprecated, deprecation_msg, changelog_json = latest_version_data
    
    changelog = {}
    if changelog_json:
        try:
            changelog = json.loads(changelog_json)
        except:
            pass
    
    return {
        'name': script_name,
        'version': version,
        'file_hash': file_hash,
        'db_schema_version': db_schema,
        'deprecated': bool(deprecated),
        'deprecation_message': deprecation_msg,
        'changelog': changelog
    }

def get_script_path(script_name: str, category: str = None) -> Optional[str]:
    admin_scripts_path = Path(ADMIN_SCRIPTS_DIR)
    
    if category:
        script_path = admin_scripts_path / category / f"{script_name}.py"
        if script_path.exists():
            return str(script_path)
        return None
    
    for cat in ['premium', 'basic']:
        script_path = admin_scripts_path / cat / f"{script_name}.py"
        if script_path.exists():
            return str(script_path)
    
    return None

def get_user_script_path(user_id: int, script_name: str) -> str:
    user_dir = Path(USER_SCRIPTS_DIR) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return str(user_dir / f"{script_name}.py")

async def update_user_script(user_id: int, script_name: str) -> Tuple[bool, str]:
    try:
        source_path = get_script_path(script_name)
        if not source_path:
            return False, f"Script {script_name} not found in admin scripts"
        
        dest_path = get_user_script_path(user_id, script_name)
        
        backup_path = dest_path + '.backup'
        if os.path.exists(dest_path):
            shutil.copy2(dest_path, backup_path)
        
        shutil.copy2(source_path, dest_path)
        
        metadata = parse_script_metadata(source_path)
        if metadata:
            await set_user_script_version(user_id, script_name, metadata['version'])
        
        if os.path.exists(backup_path):
            os.remove(backup_path)
        
        return True, f"Script {script_name} updated successfully"
    
    except Exception as e:
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, dest_path)
            os.remove(backup_path)
        return False, f"Update failed: {str(e)}"

async def apply_migrations(user_id: int, script_name: str, from_version: str, to_version: str) -> Tuple[bool, str]:
    migrations = await get_migrations(script_name, from_version, to_version)
    
    if not migrations:
        return True, "No migrations needed"
    
    try:
        for migration_sql, rollback_sql in migrations:
            print(f"Applying migration for {script_name}: {from_version} -> {to_version}")
        
        await mark_migration_applied(script_name, from_version, to_version)
        return True, "Migrations applied successfully"
    
    except Exception as e:
        return False, f"Migration failed: {str(e)}"

async def rollback_update(user_id: int, script_name: str, backup_path: str) -> bool:
    try:
        dest_path = get_user_script_path(user_id, script_name)
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, dest_path)
            os.remove(backup_path)
            return True
        return False
    except:
        return False
