# Security: Input Validators Module
# Validates all user inputs to prevent malicious or invalid data

import re
import os
from typing import Tuple

RESERVED_BOT_NAMES = {
    "admin", "system", "bot", "manager", "discord", "server",
    "moderator", "mod", "owner", "root", "null", "undefined"
}

MAX_SCRIPT_SIZE_MB = 1


def validate_discord_token(token: str) -> Tuple[bool, str]:
    """
    Validate Discord bot token format.
    
    Discord tokens have 3 parts separated by dots:
    - Part 1: User ID (base64)
    - Part 2: Timestamp
    - Part 3: HMAC signature
    
    Returns: (is_valid, error_message)
    """
    if not token or not isinstance(token, str):
        return False, "Token ne peut pas être vide"
    
    token = token.strip()
    
    if len(token) < 50:
        return False, "Token trop court (minimum 50 caractères)"
    
    if len(token) > 100:
        return False, "Token trop long (maximum 100 caractères)"
    
    if ' ' in token or '\n' in token or '\t' in token:
        return False, "Token ne doit pas contenir d'espaces ou retours à la ligne"
    
    parts = token.split('.')
    if len(parts) != 3:
        return False, "Format de token invalide (doit avoir 3 parties séparées par '.')"
    
    valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.')
    if not all(c in valid_chars for c in token):
        return False, "Token contient des caractères invalides"
    
    return True, ""


def validate_bot_name(name: str) -> Tuple[bool, str]:
    """
    Validate bot name.
    
    Rules:
    - 1-32 characters
    - Alphanumeric, hyphens, underscores only
    - No reserved names
    - No consecutive special characters
    - Must start and end with alphanumeric
    
    Returns: (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "Nom de bot ne peut pas être vide"
    
    name = name.strip()
    
    if len(name) < 1:
        return False, "Nom de bot trop court (minimum 1 caractère)"
    
    if len(name) > 32:
        return False, "Nom de bot trop long (maximum 32 caractères)"
    
    pattern = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]*[A-Za-z0-9]$|^[A-Za-z0-9]$')
    if not pattern.match(name):
        return False, "Nom invalide (lettres, chiffres, tirets, underscores uniquement, doit commencer/finir par une lettre ou chiffre)"
    
    if '--' in name or '__' in name or '-_' in name or '_-' in name:
        return False, "Pas de caractères spéciaux consécutifs autorisés"
    
    if name.lower() in RESERVED_BOT_NAMES:
        return False, f"Nom réservé '{name}' non autorisé"
    
    return True, ""


def validate_script_name(script: str) -> Tuple[bool, str]:
    """
    Validate script filename.
    
    Rules:
    - Must end with .py
    - No path traversal (../, ..\)
    - No absolute paths (/, C:\)
    - 1-100 characters
    - Alphanumeric, underscore, hyphen, dot only
    
    Returns: (is_valid, error_message)
    """
    if not script or not isinstance(script, str):
        return False, "Nom de script ne peut pas être vide"
    
    script = script.strip()
    
    if len(script) < 4:
        return False, "Nom de script trop court"
    
    if len(script) > 100:
        return False, "Nom de script trop long (maximum 100 caractères)"
    
    if not script.endswith('.py'):
        return False, "Script doit avoir l'extension .py"
    
    if '..' in script or '/' in script or '\\' in script:
        return False, "Path traversal détecté - accès refusé"
    
    if script.startswith('/') or (len(script) > 2 and script[1] == ':'):
        return False, "Chemins absolus non autorisés"
    
    base_name = script[:-3]
    pattern = re.compile(r'^[A-Za-z0-9_-]+$')
    if not pattern.match(base_name):
        return False, "Nom de script invalide (lettres, chiffres, tirets, underscores uniquement)"
    
    return True, ""


def validate_file_size(file_path: str, max_mb: int = MAX_SCRIPT_SIZE_MB) -> Tuple[bool, str]:
    """
    Validate file size.
    
    Args:
        file_path: Path to file
        max_mb: Maximum size in megabytes (default: 1MB)
    
    Returns: (is_valid, error_message)
    """
    if not os.path.exists(file_path):
        return False, f"Fichier introuvable: {file_path}"
    
    try:
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > max_mb:
            return False, f"Fichier trop volumineux ({size_mb:.2f}MB > {max_mb}MB)"
        
        return True, ""
        
    except Exception as e:
        return False, f"Erreur vérification taille: {e}"


def sanitize_user_input(text: str, max_length: int = 2000) -> str:
    """
    Sanitize user input for safe display in Discord.
    
    Args:
        text: User input text
        max_length: Maximum allowed length
    
    Returns: Sanitized text
    """
    if not text or not isinstance(text, str):
        return ""
    
    text = text[:max_length]
    
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
    
    text = text.replace('`', '\\`').replace('@', '@\u200b')
    
    return text


def validate_user_id(user_id: int) -> Tuple[bool, str]:
    """
    Validate Discord user ID.
    
    Rules:
    - Must be positive integer
    - Reasonable range (Discord snowflake IDs)
    
    Returns: (is_valid, error_message)
    """
    if not isinstance(user_id, int):
        return False, "ID utilisateur doit être un entier"
    
    if user_id <= 0:
        return False, "ID utilisateur doit être positif"
    
    if user_id > 2**63 - 1:
        return False, "ID utilisateur invalide"
    
    return True, ""


def validate_max_bots(max_bots: int) -> Tuple[bool, str]:
    """
    Validate max_bots parameter.
    
    Rules:
    - Must be positive integer
    - Reasonable limit (1-50)
    
    Returns: (is_valid, error_message)
    """
    if not isinstance(max_bots, int):
        return False, "max_bots doit être un entier"
    
    if max_bots < 1:
        return False, "max_bots doit être au minimum 1"
    
    if max_bots > 50:
        return False, "max_bots ne peut pas dépasser 50"
    
    return True, ""
