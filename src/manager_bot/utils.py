import discord
from discord.ext import commands
import os
import time
import re
from collections import defaultdict
from .config import ADMIN_IDS, USERS_DIR
from .database import get_user, get_bot

# Constants
check_mark = "<:CheckMark:1441244706762788937>"
fail_emoji = "<:redcross:1441245277263757394>"

# Caches
_start_cooldowns = defaultdict(lambda: 0)
_START_COOLDOWN_SECONDS = 30
_user_cache = {}
_CACHE_TTL = 60
_bot_cache = {}
_BOT_CACHE_TTL = 60

# Regex
_bot_name_re = re.compile(r"^[A-Za-z0-9\-]{1,32}$")

def is_valid_bot_name(name: str) -> bool:
    return bool(_bot_name_re.fullmatch(name))

async def get_user_cached(user_id: int):
    """Retrieve user data with simple TTL cache (60s)."""
    now = time.time()
    if user_id in _user_cache:
        data, timestamp = _user_cache[user_id]
        if now - timestamp < _CACHE_TTL:
            return data
    data = await get_user(user_id)
    _user_cache[user_id] = (data, now)
    return data

async def get_bot_cached(user_id: int, bot_name: str):
    """Retrieve bot data with simple TTL cache (60s)."""
    key = (user_id, bot_name)
    now = time.time()
    if key in _bot_cache:
        data, timestamp = _bot_cache[key]
        if now - timestamp < _BOT_CACHE_TTL:
            return data
    data = await get_bot(user_id, bot_name)
    _bot_cache[key] = (data, now)
    return data

def cleanup_expired_cooldowns():
    now = time.time()
    expired = [uid for uid, ts in _start_cooldowns.items() if now - ts > _START_COOLDOWN_SECONDS * 2]
    for uid in expired:
        del _start_cooldowns[uid]

async def cleanup_expired_cache():
    global _user_cache, _bot_cache
    now = time.time()
    expired_users = [uid for uid, (_, ts) in _user_cache.items() if now - ts > _CACHE_TTL]
    for uid in expired_users:
        del _user_cache[uid]
    expired_bots = [key for key, (_, ts) in _bot_cache.items() if now - ts > _BOT_CACHE_TTL]
    for key in expired_bots:
        del _bot_cache[key]

def is_admin_check(ctx: commands.Context) -> bool:
    return ctx.author.id in ADMIN_IDS

def is_registered_check(interaction: discord.Interaction) -> bool:
    return os.path.exists(os.path.join(USERS_DIR, str(interaction.user.id)))

async def check_bot_ownership(user_id: int, bot_name: str) -> bool:
    bot_data = await get_bot_cached(user_id, bot_name)
    return bot_data is not None
