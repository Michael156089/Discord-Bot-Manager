import time
from .database import get_db

async def init_versioning_tables():
    db = await get_db()
    
    await db.execute("""
    CREATE TABLE IF NOT EXISTS script_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        script_name TEXT NOT NULL,
        version TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        db_schema_version INTEGER DEFAULT 1,
        deprecated INTEGER DEFAULT 0,
        deprecation_message TEXT,
        changelog TEXT,
        created_at REAL NOT NULL,
        UNIQUE(script_name, version)
    )
    """)
    
    await db.execute("""
    CREATE TABLE IF NOT EXISTS user_script_versions (
        user_id INTEGER,
        script_name TEXT,
        installed_version TEXT,
        last_update_check REAL,
        auto_update INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, script_name),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    
    await db.execute("""
    CREATE TABLE IF NOT EXISTS script_migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        script_name TEXT NOT NULL,
        from_version TEXT NOT NULL,
        to_version TEXT NOT NULL,
        migration_sql TEXT NOT NULL,
        rollback_sql TEXT,
        applied_at REAL
    )
    """)
    
    await db.commit()
    print("Script versioning tables initialized")

async def register_script_version(script_name: str, version: str, file_hash: str, 
                                  db_schema_version: int = 1, changelog: str = None):
    db = await get_db()
    now = time.time()
    
    await db.execute("""
        INSERT OR REPLACE INTO script_versions 
        (script_name, version, file_hash, db_schema_version, changelog, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (script_name, version, file_hash, db_schema_version, changelog, now))
    
    await db.commit()
    print(f"Registered script version: {script_name} v{version}")

async def get_latest_script_version(script_name: str):
    db = await get_db()
    
    cursor = await db.execute("""
        SELECT version, file_hash, db_schema_version, deprecated, deprecation_message, changelog
        FROM script_versions
        WHERE script_name = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (script_name,))
    
    return await cursor.fetchone()

async def get_user_script_version(user_id: int, script_name: str):
    db = await get_db()
    
    cursor = await db.execute("""
        SELECT installed_version, last_update_check, auto_update
        FROM user_script_versions
        WHERE user_id = ? AND script_name = ?
    """, (user_id, script_name))
    
    return await cursor.fetchone()

async def set_user_script_version(user_id: int, script_name: str, version: str):
    db = await get_db()
    now = time.time()
    
    await db.execute("""
        INSERT OR REPLACE INTO user_script_versions
        (user_id, script_name, installed_version, last_update_check)
        VALUES (?, ?, ?, ?)
    """, (user_id, script_name, version, now))
    
    await db.commit()

async def update_last_check_time(user_id: int, script_name: str):
    db = await get_db()
    now = time.time()
    
    await db.execute("""
        UPDATE user_script_versions
        SET last_update_check = ?
        WHERE user_id = ? AND script_name = ?
    """, (now, user_id, script_name))
    
    await db.commit()

async def deprecate_script(script_name: str, version: str, message: str):
    db = await get_db()
    
    await db.execute("""
        UPDATE script_versions
        SET deprecated = 1, deprecation_message = ?
        WHERE script_name = ? AND version = ?
    """, (message, script_name, version))
    
    await db.commit()
    print(f"Script {script_name} v{version} marked as deprecated")

async def get_users_with_deprecated_scripts():
    db = await get_db()
    
    cursor = await db.execute("""
        SELECT DISTINCT usv.user_id, usv.script_name, usv.installed_version, sv.deprecation_message
        FROM user_script_versions usv
        JOIN script_versions sv ON usv.script_name = sv.script_name AND usv.installed_version = sv.version
        WHERE sv.deprecated = 1
    """)
    
    return await cursor.fetchall()

async def get_users_with_outdated_scripts():
    db = await get_db()
    
    cursor = await db.execute("""
        SELECT usv.user_id, usv.script_name, usv.installed_version, 
               (SELECT version FROM script_versions sv2 
                WHERE sv2.script_name = usv.script_name 
                ORDER BY sv2.created_at DESC LIMIT 1) as latest_version
        FROM user_script_versions usv
        WHERE usv.installed_version != (
            SELECT version FROM script_versions sv 
            WHERE sv.script_name = usv.script_name 
            ORDER BY sv.created_at DESC LIMIT 1
        )
    """)
    
    return await cursor.fetchall()

async def add_migration(script_name: str, from_version: str, to_version: str, 
                       migration_sql: str, rollback_sql: str = None):
    db = await get_db()
    
    await db.execute("""
        INSERT INTO script_migrations
        (script_name, from_version, to_version, migration_sql, rollback_sql)
        VALUES (?, ?, ?, ?, ?)
    """, (script_name, from_version, to_version, migration_sql, rollback_sql))
    
    await db.commit()
    print(f"Migration added: {script_name} {from_version} -> {to_version}")

async def get_migrations(script_name: str, from_version: str, to_version: str):
    db = await get_db()
    
    cursor = await db.execute("""
        SELECT migration_sql, rollback_sql
        FROM script_migrations
        WHERE script_name = ? AND from_version = ? AND to_version = ?
    """, (script_name, from_version, to_version))
    
    return await cursor.fetchall()

async def mark_migration_applied(script_name: str, from_version: str, to_version: str):
    db = await get_db()
    now = time.time()
    
    await db.execute("""
        UPDATE script_migrations
        SET applied_at = ?
        WHERE script_name = ? AND from_version = ? AND to_version = ?
    """, (now, script_name, from_version, to_version))
    
    await db.commit()
