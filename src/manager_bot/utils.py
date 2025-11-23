import discord
import time
import re
from collections import defaultdict
from .config import admin_list, users_folder
from .database import get_user, get_bot

# Constants
check_mark = "✅"
fail_emoji = "❌"

# Caches
_start_cooldowns = defaultdict(lambda: 0)
_START_COOLDOWN_SECONDS = 30
_user_cache = {}
_bot_cache = {}

# Regex
_bot_name_re = re.compile(r"^[A-Za-z0-9\-]{1,32}$")

def is_valid_bot_name(name: str) -> bool:
    return bool(_bot_name_re.fullmatch(name))

async def get_user_cached(user_id: int):
    now = time.time()
    if user_id in _user_cache:
        data, timestamp = _user_cache[user_id]
        if now - timestamp < 60:
            return data
    data = await get_user(user_id)
    _user_cache[user_id] = (data, now)
    return data

async def get_bot_cached(user_id: int, bot_name: str):
    key = (user_id, bot_name)
    now = time.time()
    if key in _bot_cache:
        data, timestamp = _bot_cache[key]
        if now - timestamp < 60:
            return data
    data = await get_bot(user_id, bot_name)
    _bot_cache[key] = (data, now)
    return data

def cleanup_expired_cooldowns():
    now = time.time()
    expired = [uid for uid, ts in _start_cooldowns.items() if now - ts > 60]
    for uid in expired:
        del _start_cooldowns[uid]

async def cleanup_expired_cache():
    global _user_cache, _bot_cache
    now = time.time()
    _user_cache = {k: v for k, v in _user_cache.items() if now - v[1] < 60}
    _bot_cache = {k: v for k, v in _bot_cache.items() if now - v[1] < 60}

def is_admin_check(ctx_or_interaction) -> bool:
    uid = ctx_or_interaction.user.id if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author.id
    # simplified check
    return str(uid) in (admin_list or "")
