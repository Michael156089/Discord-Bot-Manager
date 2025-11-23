import re
import os

def validate_discord_token(token):
    if not token or len(token) < 50:
        return False, "Token too short"
    if '.' not in token:
        return False, "Invalid format"
    return True, ""

def validate_bot_name(name):
    if not name or len(name) < 1 or len(name) > 32:
        return False, "Name bad length"
    if not re.match(r"^[A-Za-z0-9_-]+$", name):
        return False, "Bad chars"
    return True, ""

def validate_script_name(script):
    if not script or not script.endswith('.py'):
        return False, "Must be .py"
    if '..' in script or '/' in script or '\\' in script:
        return False, "Bad path"
    return True, ""
