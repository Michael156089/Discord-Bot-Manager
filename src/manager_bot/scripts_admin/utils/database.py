import sqlite3
import discord
from datetime import datetime

def get_db_connection():
    """Établit et retourne une connexion à la base de données."""
    return sqlite3.connect('bot_data.db')

def get_user_permission_level(user: discord.Member):
    """Détermine le niveau de permission d'un utilisateur (rôles et niveaux individuels)."""
    if user.guild_permissions.administrator: # Les admins ont toujours le niveau max
        return 9

    conn = get_db_connection()
    cursor = conn.cursor()

    # Niveau de permission le plus élevé via les rôles de l'utilisateur
    user_role_ids = [str(role.id) for role in user.roles]
    max_role_level = 0
    if user_role_ids:
        placeholders = ','.join('?' for _ in user_role_ids)
        cursor.execute(f'SELECT MAX(level) FROM permission_roles WHERE guild_id = ? AND role_id IN ({placeholders})', (str(user.guild.id), *user_role_ids))
        result = cursor.fetchone()
        if result and result[0] is not None:
            max_role_level = int(result[0])

    # Niveau de permission spécifique de l'utilisateur
    cursor.execute('SELECT level FROM user_levels WHERE user_id = ? AND guild_id = ?', (str(user.id), str(user.guild.id)))
    user_specific_result = cursor.fetchone()
    user_specific_level = int(user_specific_result[0]) if user_specific_result else 0
    
    conn.close()

    # Retourne le niveau le plus élevé, par default 1
    return max(max_role_level, user_specific_level, 1)

def set_permission_role(guild_id, role_id, level):
    """Assigne un niveau de permission à un rôle spécifique."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO permission_roles (guild_id, role_id, level) VALUES (?, ?, ?)', (str(guild_id), str(role_id), level))
    conn.commit()
    conn.close()

def remove_permission_role(guild_id, role_id):
    """Supprime la permission assignée à un rôle."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM permission_roles WHERE guild_id = ? AND role_id = ?', (str(guild_id), str(role_id)))
    conn.commit()
    conn.close()

def get_permission_roles(guild_id):
    """Récupère les rôles configurés avec un niveau de permission pour un serveur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role_id, level FROM permission_roles WHERE guild_id = ? ORDER BY level DESC', (str(guild_id),))
    results = cursor.fetchall()
    conn.close()
    return results

def add_status_role(guild_id, status_text, role_id):
    """Associe un texte de statut (activité) à un rôle."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO status_roles (guild_id, status_text, role_id) VALUES (?, ?, ?)', (str(guild_id), status_text.lower(), str(role_id)))
    conn.commit()
    conn.close()

def remove_status_role(guild_id, status_text):
    """Supprime l'association statut-rôle."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM status_roles WHERE guild_id = ? AND status_text = ?', (str(guild_id), status_text.lower()))
    conn.commit()
    conn.close()

def get_status_roles(guild_id):
    """Récupère les associations statut-rôle pour un serveur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT status_text, role_id FROM status_roles WHERE guild_id = ?', (str(guild_id),))
    results = cursor.fetchall()
    conn.close()
    return {text: int(role_id) for text, role_id in results}

def get_prefix(guild_id):
    """Récupère le préfixe du bot pour un serveur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT prefix FROM guild_settings WHERE guild_id = ?', (str(guild_id),))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else '!'

def set_guild_prefix(guild_id, prefix):
    """Définit le préfixe du bot pour un serveur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO guild_settings (guild_id, prefix) VALUES (?, ?)', (str(guild_id), prefix))
    conn.commit()
    conn.close()

def get_user_level(user_id, guild_id):
    """Récupère le niveau et l'XP d'un utilisateur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT level, xp FROM user_levels WHERE user_id = ? AND guild_id = ?', (str(user_id), str(guild_id)))
    result = cursor.fetchone()
    conn.close()
    return (int(result[0]), int(result[1])) if result else (1, 0)

def set_user_level(user_id, guild_id, level, xp=0):
    """Définit le niveau et l'XP d'un utilisateur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO user_levels (user_id, guild_id, level, xp) VALUES (?, ?, ?, ?)', (str(user_id), str(guild_id), level, xp))
    conn.commit()
    conn.close()

def get_rank_role(guild_id, rank_level):
    """Récupère le rôle associé à un niveau de rang."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role_id FROM guild_ranks WHERE guild_id = ? AND rank_level = ?', (str(guild_id), rank_level))
    result = cursor.fetchone()
    conn.close()
    return int(result[0]) if result else None

def get_all_rank_roles(guild_id):
    """Récupère tous les ID de rôles de rang pour un serveur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role_id FROM guild_ranks WHERE guild_id = ?', (str(guild_id),))
    results = cursor.fetchall()
    conn.close()
    return [int(row[0]) for row in results]

def set_rank_role(guild_id, rank_level, role_id):
    """Définit le rôle pour un niveau de rang spécifique."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO guild_ranks (guild_id, rank_level, role_id) VALUES (?, ?, ?)', (str(guild_id), rank_level, str(role_id)))
    conn.commit()
    conn.close()

def get_command_usage_today(guild_id, user_id, command_name):
    """Récupère le nombre d'utilisations d'une commande par un utilisateur aujourd'hui."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM command_usage
        WHERE guild_id = ? AND user_id = ? AND command_name = ?
        AND DATE(timestamp) = DATE('now')
    ''', (str(guild_id), str(user_id), command_name))
    result = cursor.fetchone()
    conn.close()
    return int(result[0]) if result else 0

def record_command_usage(guild_id, user_id, command_name):
    """Enregistre l'utilisation d'une commande."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO command_usage (guild_id, user_id, command_name)
        VALUES (?, ?, ?)
    ''', (str(guild_id), str(user_id), command_name))
    conn.commit()
    conn.close()

def set_immunity_role(guild_id, role_id):
    """Définit le rôle d'immunité pour un serveur. Les membres avec ce rôle sont protégés."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)', (str(guild_id),)) # Assure l'existence du serveur
    cursor.execute('UPDATE guild_settings SET immunity_role_id = ? WHERE guild_id = ?', (str(role_id), str(guild_id)))
    conn.commit()
    conn.close()

def get_immunity_role(guild_id):
    """Récupère le rôle d'immunité pour un serveur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT immunity_role_id FROM guild_settings WHERE guild_id = ?', (str(guild_id),))
    result = cursor.fetchone()
    conn.close()
    return int(result[0]) if result and result[0] else None

def set_log_channel(guild_id, channel_id):
    """Définit le salon de logs pour un serveur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)', (str(guild_id),)) # Assure l'existence du serveur
    cursor.execute('UPDATE guild_settings SET log_channel_id = ? WHERE guild_id = ?', (str(channel_id), str(guild_id)))
    conn.commit()
    conn.close()

def get_log_channel(guild_id):
    """Récupère le salon de logs pour un serveur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT log_channel_id FROM guild_settings WHERE guild_id = ?', (str(guild_id),))
    result = cursor.fetchone()
    conn.close()
    return int(result[0]) if result and result[0] else None

def init_database():
    """Initialise la base de données SQLite en créant les tables nécessaires."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id TEXT PRIMARY KEY,
            prefix TEXT DEFAULT '!',
            log_channel_id TEXT,
            immunity_role_id TEXT
        )
    ''')
    
    # MIGRATIONS : Ajoute les nouvelles colonnes si elles n'existent pas
    cursor.execute("PRAGMA table_info(guild_settings)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'log_channel_id' not in columns:
        cursor.execute('ALTER TABLE guild_settings ADD COLUMN log_channel_id TEXT')
    if 'immunity_role_id' not in columns:
        cursor.execute('ALTER TABLE guild_settings ADD COLUMN immunity_role_id TEXT')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_levels (
            user_id TEXT,
            guild_id TEXT,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guild_ranks (
            guild_id TEXT,
            rank_level INTEGER,
            role_id TEXT,
            PRIMARY KEY (guild_id, rank_level)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS command_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT,
            command_name TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT,
            moderator_id TEXT,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permission_roles (
            guild_id TEXT,
            role_id TEXT,
            level INTEGER,
            PRIMARY KEY (guild_id, role_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS status_roles (
            guild_id TEXT,
            status_text TEXT,
            role_id TEXT,
            PRIMARY KEY (guild_id, status_text)
        )
    ''')
    conn.commit()
    conn.close()
