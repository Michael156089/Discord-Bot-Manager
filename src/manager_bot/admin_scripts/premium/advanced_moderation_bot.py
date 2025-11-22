import discord
from discord.ext import commands
import sqlite3
import os
import sys
import asyncio
import typing
from datetime import datetime, timedelta, timezone
import logging
import random

# --- Configuration ---
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("ERREUR: Aucun token Discord trouvé (DISCORD_TOKEN).")
    sys.exit(1)

DB_FILE = "bot_data.db"

# --- Database Manager ---
class LocalDatabase:
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_file)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Guild Settings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id TEXT PRIMARY KEY,
                    prefix TEXT DEFAULT '!',
                    log_channel_id TEXT,
                    immunity_role_id TEXT
                )
            ''')
            
            # User Levels
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_levels (
                    user_id TEXT,
                    guild_id TEXT,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')

            # Guild Ranks
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS guild_ranks (
                    guild_id TEXT,
                    rank_level INTEGER,
                    role_id TEXT,
                    PRIMARY KEY (guild_id, rank_level)
                )
            ''')

            # Command Usage
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS command_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT,
                    user_id TEXT,
                    command_name TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Warnings
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
            
            # Permission Roles
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS permission_roles (
                    guild_id TEXT,
                    role_id TEXT,
                    level INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )
            ''')
            
            # Status Roles
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS status_roles (
                    guild_id TEXT,
                    status_text TEXT,
                    role_id TEXT,
                    PRIMARY KEY (guild_id, status_text)
                )
            ''')
            
            # Leashes (Forced Nicknames)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leashes (
                    user_id TEXT,
                    guild_id TEXT,
                    nickname TEXT,
                    expires_at DATETIME,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            
            # Anti-Link Configuration
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS antilink_config (
                    guild_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    whitelisted_roles TEXT DEFAULT ''
                )
            ''')
            conn.commit()

    # --- Guild Settings ---
    def get_prefix(self, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT prefix FROM guild_settings WHERE guild_id = ?', (str(guild_id),))
            res = cursor.fetchone()
            return res[0] if res else '!'

    def set_prefix(self, guild_id, prefix):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO guild_settings (guild_id, prefix) VALUES (?, ?)', (str(guild_id), prefix))
            conn.commit()

    def get_log_channel(self, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT log_channel_id FROM guild_settings WHERE guild_id = ?', (str(guild_id),))
            res = cursor.fetchone()
            return int(res[0]) if res and res[0] else None

    def set_log_channel(self, guild_id, channel_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)', (str(guild_id),))
            cursor.execute('UPDATE guild_settings SET log_channel_id = ? WHERE guild_id = ?', (str(channel_id), str(guild_id)))
            conn.commit()

    def get_immunity_role(self, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT immunity_role_id FROM guild_settings WHERE guild_id = ?', (str(guild_id),))
            res = cursor.fetchone()
            return int(res[0]) if res and res[0] else None

    def set_immunity_role(self, guild_id, role_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)', (str(guild_id),))
            cursor.execute('UPDATE guild_settings SET immunity_role_id = ? WHERE guild_id = ?', (str(role_id), str(guild_id)))
            conn.commit()

    # --- Permissions ---
    def get_role_permission_level(self, guild_id, role_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT level FROM permission_roles WHERE guild_id = ? AND role_id = ?', (str(guild_id), str(role_id)))
            res = cursor.fetchone()
            return int(res[0]) if res else 0

    def set_permission_role(self, guild_id, role_id, level):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO permission_roles (guild_id, role_id, level) VALUES (?, ?, ?)', (str(guild_id), str(role_id), level))
            conn.commit()

    def remove_permission_role(self, guild_id, role_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM permission_roles WHERE guild_id = ? AND role_id = ?', (str(guild_id), str(role_id)))
            conn.commit()

    def get_permission_roles(self, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT role_id, level FROM permission_roles WHERE guild_id = ? ORDER BY level DESC', (str(guild_id),))
            return cursor.fetchall()

    # --- Ranks ---
    def get_rank_role(self, guild_id, rank_level):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT role_id FROM guild_ranks WHERE guild_id = ? AND rank_level = ?', (str(guild_id), rank_level))
            res = cursor.fetchone()
            return int(res[0]) if res else None

    def set_rank_role(self, guild_id, rank_level, role_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO guild_ranks (guild_id, rank_level, role_id) VALUES (?, ?, ?)', (str(guild_id), rank_level, str(role_id)))
            conn.commit()

    def get_all_rank_roles(self, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT role_id FROM guild_ranks WHERE guild_id = ?', (str(guild_id),))
            return [int(row[0]) for row in cursor.fetchall()]

    # --- Users ---
    def get_user_level(self, user_id, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT level, xp FROM user_levels WHERE user_id = ? AND guild_id = ?', (str(user_id), str(guild_id)))
            res = cursor.fetchone()
            return (int(res[0]), int(res[1])) if res else (1, 0)

    def set_user_level(self, user_id, guild_id, level, xp=0):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO user_levels (user_id, guild_id, level, xp) VALUES (?, ?, ?, ?)', (str(user_id), str(guild_id), level, xp))
            conn.commit()

    # --- Warns ---
    def add_warn(self, user_id, guild_id, moderator_id, reason):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)', (str(guild_id), str(user_id), str(moderator_id), reason))
            conn.commit()

    def remove_warn(self, warn_id, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM warnings WHERE id = ? AND guild_id = ?', (warn_id, str(guild_id)))
            conn.commit()
            return cursor.rowcount > 0

    def get_user_warns(self, user_id, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, moderator_id, reason, timestamp FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC', (str(user_id), str(guild_id)))
            return cursor.fetchall()

    # --- Leashes ---
    def add_leash(self, user_id, guild_id, nickname, duration_minutes):
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(minutes=duration_minutes)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO leashes (user_id, guild_id, nickname, expires_at) VALUES (?, ?, ?, ?)', 
                         (str(user_id), str(guild_id), nickname, expires_at.isoformat()))
            conn.commit()

    def get_leash(self, user_id, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT nickname, expires_at FROM leashes WHERE user_id = ? AND guild_id = ?', (str(user_id), str(guild_id)))
            return cursor.fetchone()

    def remove_leash(self, user_id, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM leashes WHERE user_id = ? AND guild_id = ?', (str(user_id), str(guild_id)))
            conn.commit()

    def get_expired_leashes(self):
        from datetime import datetime
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, guild_id FROM leashes WHERE expires_at < ?', (datetime.now().isoformat(),))
            return cursor.fetchall()

    # --- Anti-Link ---
    def get_antilink_config(self, guild_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT enabled, whitelisted_roles FROM antilink_config WHERE guild_id = ?', (str(guild_id),))
            res = cursor.fetchone()
            if res:
                return {'enabled': bool(res[0]), 'whitelisted_roles': res[1].split(',') if res[1] else []}
            return {'enabled': False, 'whitelisted_roles': []}

    def set_antilink_enabled(self, guild_id, enabled):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO antilink_config (guild_id) VALUES (?)', (str(guild_id),))
            cursor.execute('UPDATE antilink_config SET enabled = ? WHERE guild_id = ?', (1 if enabled else 0, str(guild_id)))
            conn.commit()

    def add_antilink_whitelist_role(self, guild_id, role_id):
        config = self.get_antilink_config(guild_id)
        roles = config['whitelisted_roles']
        if str(role_id) not in roles:
            roles.append(str(role_id))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO antilink_config (guild_id) VALUES (?)', (str(guild_id),))
            cursor.execute('UPDATE antilink_config SET whitelisted_roles = ? WHERE guild_id = ?', (','.join(roles), str(guild_id)))
            conn.commit()

    def remove_antilink_whitelist_role(self, guild_id, role_id):
        config = self.get_antilink_config(guild_id)
        roles = config['whitelisted_roles']
        if str(role_id) in roles:
            roles.remove(str(role_id))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE antilink_config SET whitelisted_roles = ? WHERE guild_id = ?', (','.join(roles), str(guild_id)))
            conn.commit()

db = LocalDatabase(DB_FILE)

# --- Utils ---
RESPONSES = {
    "ban_success": [
        "C'est fait, {target} a été banni. La porte, c'est par là.",
        "Yes, {target} a pris son ban. On le reverra plus.",
        "{target} a été envoyé en exil. Adios.",
        "Mission accomplie. {target} est plus là.",
        "Ok, {target} a été éjecté. Zéro pitié.",
        "Voilà, {target} a été banni. On respire.",
        "C'est bon, {target} a été mis au coin, mais pour de vrai.",
        "{target} a été neutralisé. On est tranquilles.",
        "Le couperet est tombé pour {target}. Ban mérité.",
        "Et bim, {target} a été banni. Fallait pas chercher."
    ],
    "kick_success": [
        "{target} a été kick. Un peu d'air frais lui fera du bien.",
        "Allez, dehors ! {target} a été gentiment raccompagné à la sortie.",
        "{target} a été expulsé. Il pourra retenter sa chance, ou pas.",
        "C'est réglé, {target} a été mis à la porte.",
        "Ok, {target} a été sorti. Problème suivant.",
        "Un petit coup de pied aux fesses pour {target}. C'est fait.",
        "{target} a été viré. Il a compris le message.",
        "Expulsion de {target} réussie. On passe à autre chose.",
        "C'est bon, {target} est parti faire un tour. Pour de bon.",
        "Le kick est parti tout seul sur {target}. C'est la vie."
    ],
    "setprefix_success": [
        "C'est carré, le nouveau préfixe est : `{prefix}`",
        "Bien reçu, le préfixe c'est maintenant `{prefix}`. Fais pas l'con avec.",
        "Ok, le préfixe a été changé en `{prefix}`. T'as intérêt à t'en souvenir.",
        "Nouveau préfixe `{prefix}` enregistré. C'est toi le boss.",
        "C'est noté, le préfixe est `{prefix}`. Simple, basique.",
        "Voilà, `{prefix}` sera le nouveau signe de ralliement.",
        "Le préfixe est maintenant `{prefix}`. À tes ordres.",
        "Ça marche, le préfixe est `{prefix}`. On innove.",
        "Préfixe mis à jour : `{prefix}`. C'est frais.",
        "Validé. Le nouveau préfixe est `{prefix}`."
    ],
    "permission_denied": [
        "T'as pas les droits pour ça, frérot. Il te faut le niveau {level}.",
        "Essaie pas, t'as pas le niveau {level} pour ça.",
        "Non, non, non. Il te faut la perm {level} pour faire ça.",
        "T'as cru ? Niveau {level} requis, et tu l'as pas.",
        "C'est pas pour toi, ça. Reviens quand t'auras le niveau {level}.",
        "Accès refusé. Il te manque le niveau {level}.",
        "Tu peux pas faire ça. Il faut être niveau {level} minimum.",
        "T'es pas assez haut gradé pour ça. Niveau {level} demandé.",
        "Oublie, c'est pour les grands ça (niveau {level}).",
        "Hmm, il te manque des galons. Niveau {level} pour être précis."
    ],
    "ban_fail_immune": [
        "Tu peux pas toucher à {target}, il est protégé par l'immunité.",
        "Laisse {target} tranquille, il est intouchable.",
        "Même pas en rêve. {target} a un totem d'immunité.",
        "T'attaques un mur, là. {target} est immunisé.",
        "C'est non. {target} est un VIP, immunité activée."
    ],
     "kick_fail_immune": [
        "Tu peux pas toucher à {target}, il est protégé par l'immunité.",
        "Laisse {target} tranquille, il est intouchable.",
        "Même pas en rêve. {target} a un totem d'immunité.",
        "T'attaques un mur, là. {target} est immunisé.",
        "C'est non. {target} est un VIP, immunité activée."
    ],
    "mute_fail_immune": [
        "Tu peux pas mute {target}, il est protégé par l'immunité.",
        "Laisse {target} tranquille, il est intouchable.",
        "Même pas en rêve. {target} a un totem d'immunité pour le mute.",
        "T'attaques un mur, là. {target} est immunisé contre le mute.",
        "C'est non. {target} est un VIP, immunité activée."
    ],
    "unmute_fail_immune": [
        "Tu peux pas unmute {target}, il est protégé par l'immunité.",
        "Laisse {target} tranquille, il est intouchable.",
        "Même pas en rêve. {target} a un totem d'immunité pour le mute.",
        "T'attaques un mur, là. {target} est immunisé contre le mute.",
        "C'est non. {target} est un VIP, immunité activée."
    ],
    "warn_fail_immune": [
        "Tu peux pas warn {target}, il est protégé par l'immunité.",
        "Laisse {target} tranquille, il est intouchable.",
        "Même pas en rêve. {target} a un totem d'immunité.",
        "T'attaques un mur, là. {target} est immunisé.",
        "C'est non. {target} est un VIP, immunité activée."
    ],
     "rank_fail_immune": [
        "Tu peux pas toucher à {target}, il est protégé.",
        "Laisse {target} tranquille, il est intouchable.",
        "Même pas en rêve.",
        "T'attaques un mur, là.",
        "C'est non. {target} est un VIP."
    ]
}

def get_random_response(key, **kwargs):
    if key not in RESPONSES:
        return f"Message manquant pour {key}"
    response = random.choice(RESPONSES[key])
    return response.format(**kwargs)

def get_user_permission_level(member):
    if member.guild.owner_id == member.id:
        return 10
    if member.guild_permissions.administrator:
        return 9
    
    max_level = 0
    for role in member.roles:
        level = db.get_role_permission_level(member.guild.id, role.id)
        if level > max_level:
            max_level = level
    
    user_level, _ = db.get_user_level(member.id, member.guild.id)
    return max(max_level, user_level)

async def log_action(bot, ctx, target, action, reason, duration=None):
    log_channel_id = db.get_log_channel(ctx.guild.id)
    if not log_channel_id:
        return

    channel = bot.get_channel(log_channel_id)
    if not channel:
        return

    embed = discord.Embed(title=f"Action: {action.upper()}", timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Cible", value=f"{target} ({target.id})", inline=False)
    embed.add_field(name="Modérateur", value=f"{ctx.author} ({ctx.author.id})", inline=False)
    embed.add_field(name="Raison", value=reason, inline=False)
    if duration:
        embed.add_field(name="Durée", value=duration, inline=False)
    
    colors = {
        'ban': discord.Color.red(),
        'kick': discord.Color.orange(),
        'mute': discord.Color.yellow(),
        'unmute': discord.Color.green(),
        'warn': discord.Color.gold()
    }
    embed.color = colors.get(action, discord.Color.blue())
    
    await channel.send(embed=embed)

def parse_duration(duration_str: str) -> timedelta | None:
    unit_map = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
    duration_str = duration_str.lower().strip()
    if not duration_str or not duration_str[:-1].isdigit():
        return None
    unit = duration_str[-1]
    if unit not in unit_map:
        return None
    try:
        value = int(duration_str[:-1])
        return timedelta(**{unit_map[unit]: value})
    except:
        return None

def check_permission_level(required_level):
    async def predicate(ctx):
        user_level = get_user_permission_level(ctx.author)
        if user_level >= required_level:
            return True
        await ctx.send(get_random_response("permission_denied", level=required_level))
        return False
    return commands.check(predicate)

async def get_target_user_async(ctx, user_input=None):
    if ctx.message.reference and ctx.message.reference.message_id:
        try:
            replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            return replied_message.author
        except (discord.NotFound, discord.HTTPException):
            pass

    if user_input:
        if isinstance(user_input, discord.Member):
            return user_input

        if isinstance(user_input, str):
            try:
                converter = commands.MemberConverter()
                member = await converter.convert(ctx, user_input)
                return member
            except commands.BadArgument:
                pass

            if user_input.isdigit():
                try:
                    member = ctx.guild.get_member(int(user_input))
                    if member:
                        return member
                except (ValueError, TypeError):
                    pass
    return None

# --- Cogs ---

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setprefix')
    @check_permission_level(9)
    async def set_prefix(self, ctx, new_prefix: str):
        if len(new_prefix) > 5:
            await ctx.send("Le préfixe doit faire 5 caractères max.")
            return
        db.set_prefix(ctx.guild.id, new_prefix)
        await ctx.send(get_random_response("setprefix_success", prefix=new_prefix))

    @commands.command(name='rankassign')
    @check_permission_level(9)
    async def rank_assign(self, ctx, rank_level: int, role: discord.Role):
        if not 1 <= rank_level <= 9:
            await ctx.send("Les rangs vont de 1 à 9.")
            return
        db.set_rank_role(ctx.guild.id, rank_level, role.id)
        await ctx.send(f"Rôle **{role.name}** lié au rang **{rank_level}**.")

    @commands.command(name='rank')
    @check_permission_level(8)
    async def rank_user(self, ctx, target: discord.Member = None, new_rank: int = 0):
        if not target:
            # Si pas de target, on essaie de parser les args manuellement si besoin ou on return
            # Ici on suppose que les convertisseurs de discord.py font le job si l'ordre est respecté
            return await ctx.send("Usage: rank <membre> <niveau>")
            
        author_level = get_user_permission_level(ctx.author)
        target_level = get_user_permission_level(target)

        immunity_role_id = db.get_immunity_role(ctx.guild.id)
        if immunity_role_id and immunity_role_id in [role.id for role in target.roles]:
            await ctx.send(get_random_response("rank_fail_immune", target=target.display_name))
            return

        if author_level == 8:
            if target == ctx.author: return await ctx.send("Non.")
            if target_level >= author_level: return await ctx.send("Impossible sur un rang égal ou supérieur.")
            if new_rank > 7: return await ctx.send("Max rang 7 pour vous.")

        if not 1 <= new_rank <= 9: return await ctx.send("Rang entre 1 et 9.")

        role_id = db.get_rank_role(ctx.guild.id, new_rank)
        if not role_id: return await ctx.send(f"Aucun rôle configuré pour le rang {new_rank}.")

        new_role = ctx.guild.get_role(int(role_id))
        if not new_role: return await ctx.send(f"Rôle introuvable.")

        try:
            all_rank_role_ids = db.get_all_rank_roles(ctx.guild.id)
            roles_to_remove = [role for role in target.roles if role.id in all_rank_role_ids]
            if roles_to_remove:
                await target.remove_roles(*roles_to_remove)
            await target.add_roles(new_role)
        except discord.Forbidden:
            return await ctx.send("Je n'ai pas la permission de gérer les rôles.")
        
        _, xp = db.get_user_level(target.id, ctx.guild.id)
        db.set_user_level(target.id, ctx.guild.id, new_rank, xp)
        await ctx.send(f"{target.display_name} est maintenant rang {new_rank} ({new_role.name}).")

    @commands.command(name='setimmunityrole')
    @check_permission_level(9)
    async def set_immunity_role_command(self, ctx, role: discord.Role = None):
        if role:
            db.set_immunity_role(ctx.guild.id, role.id)
            await ctx.send(f"Rôle d'immunité : **{role.name}**.")
        else:
            db.set_immunity_role(ctx.guild.id, None)
            await ctx.send("Rôle d'immunité supprimé.")

    @commands.command(name='setlogchannel')
    @check_permission_level(9)
    async def set_log_channel_command(self, ctx, channel: discord.TextChannel = None):
        if channel:
            db.set_log_channel(ctx.guild.id, channel.id)
            await ctx.send(f"Salon de logs : {channel.mention}.")
        else:
            db.set_log_channel(ctx.guild.id, None)
            await ctx.send("Logs désactivés.")

    @commands.command(name='setperm')
    @check_permission_level(9)
    async def set_permission(self, ctx, role: discord.Role, level: int):
        if not 1 <= level <= 8: return await ctx.send("Niveau entre 1 et 8.")
        db.set_permission_role(ctx.guild.id, role.id, level)
        await ctx.send(f"Rôle **{role.name}** = Permission **{level}**.")

    @commands.command(name='delperm')
    @check_permission_level(9)
    async def delete_permission(self, ctx, role: discord.Role):
        db.remove_permission_role(ctx.guild.id, role.id)
        await ctx.send(f"Permission supprimée pour **{role.name}**.")

    @commands.command(name='listperm')
    @check_permission_level(8)
    async def list_permissions(self, ctx):
        roles_with_perms = db.get_permission_roles(ctx.guild.id)
        if not roles_with_perms: return await ctx.send("Aucune permission configurée.")
        
        desc = ""
        for role_id, level in roles_with_perms:
            role = ctx.guild.get_role(int(role_id))
            if role: desc += f"**{role.name}** : Niveau **{level}**\n"
        
        embed = discord.Embed(title="Permissions des Rôles", description=desc, color=discord.Color.blue())
        await ctx.send(embed=embed)

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipe_cache = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return
        self.snipe_cache[message.channel.id] = {
            'content': message.content,
            'author': message.author,
            'created_at': message.created_at
        }

    @commands.command(name='snipe')
    async def snipe_message(self, ctx):
        if ctx.channel.id not in self.snipe_cache: return await ctx.send("Rien à snipe.")
        data = self.snipe_cache[ctx.channel.id]
        await ctx.send(f"**Supprimé par {data['author'].display_name} :**\n>>> {data['content'] or '*Image*'}")

    @commands.command(name='pic', aliases=['avatar'])
    async def profile_picture(self, ctx, *, member_input=None):
        target = await get_target_user_async(ctx, member_input) or ctx.author
        embed = discord.Embed(title=f"Avatar de {target.display_name}", color=0x7289DA)
        embed.set_image(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='userinfo', aliases=['ui'])
    async def user_info(self, ctx, *, member_input=None):
        target = await get_target_user_async(ctx, member_input) or ctx.author
        level, xp = db.get_user_level(target.id, ctx.guild.id)
        embed = discord.Embed(title=f"Infos {target.display_name}", color=target.color)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="ID", value=target.id)
        embed.add_field(name="Niveau", value=f"{level} ({xp} XP)")
        embed.add_field(name="Créé le", value=f"<t:{int(target.created_at.timestamp())}:D>")
        embed.add_field(name="Rejoint le", value=f"<t:{int(target.joined_at.timestamp())}:D>")
        await ctx.send(embed=embed)

    @commands.command(name='level', aliases=['lvl'])
    async def check_level(self, ctx, *, member_input=None):
        target = await get_target_user_async(ctx, member_input) or ctx.author
        level, xp = db.get_user_level(target.id, ctx.guild.id)
        await ctx.send(f"**{target.display_name}** : Niveau **{level}** (**{xp}** XP).")

    @commands.command(name='rankinfo')
    async def rank_info(self, ctx):
        embed = discord.Embed(title="Rangs du Serveur", color=0xE91E63)
        for i in range(1, 10):
            role_id = db.get_rank_role(ctx.guild.id, i)
            role_name = f"@{ctx.guild.get_role(role_id).name}" if role_id and ctx.guild.get_role(role_id) else "Aucun"
            embed.add_field(name=f"Rang {i}", value=role_name, inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='banner', aliases=['banniere'])
    async def user_banner(self, ctx, *, member_input=None):
        target = await get_target_user_async(ctx, member_input) or ctx.author
        user = await self.bot.fetch_user(target.id)
        
        if user.banner:
            embed = discord.Embed(title=f"Bannière de {target.display_name}", color=0x7289DA)
            embed.set_image(url=user.banner.url)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"**{target.display_name}** n'a pas de bannière.")

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_immune(self, ctx, member, action):
        immunity_role_id = db.get_immunity_role(ctx.guild.id)
        if immunity_role_id:
            role = ctx.guild.get_role(immunity_role_id)
            if role and role in member.roles:
                await ctx.send(get_random_response(f"{action}_fail_immune", target=member.display_name))
                return True
        return False

    @commands.command(name='ban')
    @check_permission_level(7)
    async def ban_member(self, ctx, *, user_input: str):
        parts = user_input.split()
        target = await get_target_user_async(ctx, parts[0])
        reason = ' '.join(parts[1:]) if len(parts) > 1 else "Aucune raison."
        
        if not target: return await ctx.send("Membre introuvable.")
        if await self.is_immune(ctx, target, 'ban'): return
        if target.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner: return await ctx.send("Hiérarchie respectée.")

        try:
            await target.ban(reason=f"Par {ctx.author}: {reason}")
            await ctx.send(get_random_response("ban_success", target=target.display_name))
            await log_action(self.bot, ctx, target, 'ban', reason)
        except discord.Forbidden: await ctx.send("Pas la permission.")

    @commands.command(name='kick')
    @check_permission_level(6)
    async def kick_member(self, ctx, *, user_input: str):
        parts = user_input.split()
        target = await get_target_user_async(ctx, parts[0])
        reason = ' '.join(parts[1:]) if len(parts) > 1 else "Aucune raison."

        if not target: return await ctx.send("Membre introuvable.")
        if await self.is_immune(ctx, target, 'kick'): return
        if target.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner: return await ctx.send("Hiérarchie respectée.")

        try:
            await target.kick(reason=f"Par {ctx.author}: {reason}")
            await ctx.send(get_random_response("kick_success", target=target.display_name))
            await log_action(self.bot, ctx, target, 'kick', reason)
        except discord.Forbidden: await ctx.send("Pas la permission.")

    @commands.command(name="mute", aliases=["timeout"])
    @check_permission_level(5)
    async def mute(self, ctx, user_input: str, duration_str: str, *, reason="Aucune raison"):
        target = await get_target_user_async(ctx, user_input)
        if not target: return await ctx.send("Membre introuvable.")
        if await self.is_immune(ctx, target, 'mute'): return
        
        duration = parse_duration(duration_str)
        if not duration: return await ctx.send("Format durée invalide (ex: 10m, 1h).")

        try:
            await target.timeout(duration, reason=reason)
            await ctx.send(f"**{target.display_name}** mute pour {duration_str}.")
            await log_action(self.bot, ctx, target, 'mute', reason, duration_str)
        except discord.Forbidden: await ctx.send("Pas la permission.")

    @commands.command(name="unmute")
    @check_permission_level(5)
    async def unmute(self, ctx, *, user_input: str):
        target = await get_target_user_async(ctx, user_input.split()[0])
        if not target: return await ctx.send("Membre introuvable.")
        
        try:
            await target.timeout(None, reason="Unmute")
            await ctx.send(f"**{target.display_name}** unmute.")
            await log_action(self.bot, ctx, target, 'unmute', "Manuelle")
        except discord.Forbidden: await ctx.send("Pas la permission.")

    @commands.command(name='clear', aliases=['purge'])
    @check_permission_level(4)
    async def clear_messages(self, ctx, amount: int):
        if not 1 <= amount <= 100: return await ctx.send("Entre 1 et 100.")
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"Supprimé {len(deleted)} messages.", delete_after=5)

    @commands.command(name='warn')
    @check_permission_level(5)
    async def warn_user(self, ctx, user_input: str, *, reason="Aucune raison"):
        target = await get_target_user_async(ctx, user_input)
        if not target: return await ctx.send("Membre introuvable.")
        if await self.is_immune(ctx, target, 'warn'): return

        db.add_warn(target.id, ctx.guild.id, ctx.author.id, reason)
        await ctx.send(f"**{target.display_name}** averti : {reason}")
        await log_action(self.bot, ctx, target, 'warn', reason)
        try: await target.send(f"Avertissement sur {ctx.guild.name}: {reason}")
        except: pass

    @commands.command(name='delwarn')
    @check_permission_level(6)
    async def delete_warning(self, ctx, warn_id: int):
        if db.remove_warn(warn_id, ctx.guild.id):
            await ctx.send(f"Avertissement #{warn_id} supprimé.")
            await log_action(self.bot, ctx, ctx.author, 'delwarn', f"ID: {warn_id}")
        else:
            await ctx.send("Avertissement introuvable ou n'appartient pas à ce serveur.")

    @commands.command(name='sanctions', aliases=['warnings', 'warns'])
    @check_permission_level(5)
    async def show_sanctions(self, ctx, *, user_input: str):
        target = await get_target_user_async(ctx, user_input)
        if not target: return await ctx.send("Membre introuvable.")

        warns = db.get_user_warns(target.id, ctx.guild.id)
        if not warns:
            return await ctx.send(f"**{target.display_name}** a un casier vierge.")

        embed = discord.Embed(title=f"Sanctions de {target.display_name}", color=discord.Color.orange())
        for w in warns:
            # w = (id, moderator_id, reason, timestamp)
            mod = ctx.guild.get_member(int(w[1]))
            mod_name = mod.display_name if mod else "Inconnu"
            embed.add_field(
                name=f"Warn #{w[0]} - {w[3]}",
                value=f"**Mod:** {mod_name}\n**Raison:** {w[2]}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name='lock')
    @check_permission_level(6)
    async def lock_channel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        
        if overwrite.send_messages is False:
            return await ctx.send(f"Le salon {channel.mention} est déjà verrouillé.")
        
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"Le salon {channel.mention} a été verrouillé.")
        await log_action(self.bot, ctx, channel, 'lock', "Verrouillage du salon")

    @commands.command(name='unlock')
    @check_permission_level(6)
    async def unlock_channel(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        
        if overwrite.send_messages is True or overwrite.send_messages is None:
            return await ctx.send(f"Le salon {channel.mention} n'est pas verrouillé.")
        
        overwrite.send_messages = None # Reset to default (usually True)
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"Le salon {channel.mention} a été déverrouillé.")
        await log_action(self.bot, ctx, channel, 'unlock', "Déverrouillage du salon")

    @commands.command(name='addrole')
    @check_permission_level(7)
    async def add_role(self, ctx, member: discord.Member, role: discord.Role):
        if ctx.author.top_role <= role and ctx.author != ctx.guild.owner:
            return await ctx.send("Vous ne pouvez pas ajouter un rôle supérieur ou égal au vôtre.")
        
        if ctx.guild.me.top_role <= role:
            return await ctx.send("Je ne peux pas ajouter ce rôle (il est supérieur au mien).")

        try:
            await member.add_roles(role, reason=f"Ajouté par {ctx.author}")
            await ctx.send(f"Rôle **{role.name}** ajouté à **{member.display_name}**.")
            await log_action(self.bot, ctx, member, 'addrole', f"Ajout du rôle {role.name}")
        except discord.Forbidden:
            await ctx.send("Je n'ai pas la permission de gérer les rôles.")

    @commands.command(name='delrole', aliases=['removerole'])
    @check_permission_level(7)
    async def remove_role(self, ctx, member: discord.Member, role: discord.Role):
        if ctx.author.top_role <= role and ctx.author != ctx.guild.owner:
            return await ctx.send("Vous ne pouvez pas retirer un rôle supérieur ou égal au vôtre.")
            
        if ctx.guild.me.top_role <= role:
            return await ctx.send("Je ne peux pas retirer ce rôle (il est supérieur au mien).")

        try:
            await member.remove_roles(role, reason=f"Retiré par {ctx.author}")
            await ctx.send(f"Rôle **{role.name}** retiré de **{member.display_name}**.")
            await log_action(self.bot, ctx, member, 'delrole', f"Retrait du rôle {role.name}")
        except discord.Forbidden:
            await ctx.send("Je n'ai pas la permission de gérer les rôles.")

    @commands.command(name='leash')
    @check_permission_level(6)
    async def leash_nickname(self, ctx, member: discord.Member, duration: str, *, nickname: str):
        if len(nickname) > 32:
            return await ctx.send("Le pseudo ne peut pas dépasser 32 caractères.")
        
        duration_delta = parse_duration(duration)
        if not duration_delta:
            return await ctx.send("Format de durée invalide (ex: 30m, 2h, 1d).")
        
        duration_minutes = int(duration_delta.total_seconds() / 60)
        
        try:
            await member.edit(nick=nickname, reason=f"Leash par {ctx.author}")
            db.add_leash(member.id, ctx.guild.id, nickname, duration_minutes)
            await ctx.send(f"**{member.display_name}** est maintenant forcé au pseudo **{nickname}** pour {duration}.")
            await log_action(self.bot, ctx, member, 'leash', f"Pseudo forcé: {nickname} pour {duration}")
        except discord.Forbidden:
            await ctx.send("Je n'ai pas la permission de modifier les pseudos.")

    @commands.command(name='unleash')
    @check_permission_level(6)
    async def unleash_nickname(self, ctx, member: discord.Member):
        leash = db.get_leash(member.id, ctx.guild.id)
        if not leash:
            return await ctx.send(f"**{member.display_name}** n'a pas de pseudo forcé.")
        
        db.remove_leash(member.id, ctx.guild.id)
        await ctx.send(f"**{member.display_name}** peut maintenant changer son pseudo librement.")
        await log_action(self.bot, ctx, member, 'unleash', "Libération du pseudo forcé")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick == after.nick:
            return
        
        leash = db.get_leash(after.id, after.guild.id)
        if not leash:
            return
        
        forced_nick, expires_at = leash
        from datetime import datetime
        if datetime.fromisoformat(expires_at) < datetime.now():
            db.remove_leash(after.id, after.guild.id)
            return
        
        if after.nick != forced_nick:
            try:
                await after.edit(nick=forced_nick, reason="Leash actif")
            except discord.Forbidden:
                pass

    @commands.command(name='massban')
    async def mass_ban(self, ctx, amount: int, *, reason: str = "Mass ban"):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("Cette commande est réservée au propriétaire du serveur uniquement.")
        
        if not 1 <= amount <= 50:
            return await ctx.send("Vous pouvez bannir entre 1 et 50 personnes maximum.")
        
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)
        
        to_ban = []
        for member in members:
            if len(to_ban) >= amount:
                break
            if member.id == ctx.guild.owner_id or member.bot:
                continue
            to_ban.append(member)
        
        if not to_ban:
            return await ctx.send("Aucun membre éligible pour le mass ban.")
        
        member_list = "\n".join([f"- {m.display_name} ({m.id})" for m in to_ban[:10]])
        if len(to_ban) > 10:
            member_list += f"\n... et {len(to_ban) - 10} autre(s)"
        
        confirm_msg = await ctx.send(
            f"**ATTENTION : MASS BAN**\n"
            f"Vous êtes sur le point de bannir **{len(to_ban)}** membre(s) :\n"
            f"{member_list}\n\n"
            f"Raison : {reason}\n\n"
            f"Réagissez avec ✅ pour confirmer ou ❌ pour annuler (30 secondes)."
        )
        
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await confirm_msg.edit(content="Mass ban annulé.")
                return
            
            banned_count = 0
            failed_count = 0
            
            status_msg = await ctx.send(f"Bannissement en cours... 0/{len(to_ban)}")
            
            for i, member in enumerate(to_ban, 1):
                try:
                    await member.ban(reason=f"Mass ban par {ctx.author}: {reason}")
                    banned_count += 1
                except:
                    failed_count += 1
                
                if i % 5 == 0 or i == len(to_ban):
                    await status_msg.edit(content=f"Bannissement en cours... {i}/{len(to_ban)}")
            
            await status_msg.edit(
                content=f"Mass ban terminé.\n"
                f"Bannis : {banned_count}\n"
                f"Échecs : {failed_count}"
            )
            await log_action(self.bot, ctx, ctx.author, 'massban', f"{banned_count} membres bannis: {reason}")
            
        except asyncio.TimeoutError:
            await confirm_msg.edit(content="Mass ban annulé (timeout).")

    @commands.group(name='antilink', invoke_without_command=True)
    @check_permission_level(7)
    async def antilink(self, ctx):
        config = db.get_antilink_config(ctx.guild.id)
        status = "Activé" if config['enabled'] else "Désactivé"
        
        whitelisted = []
        for role_id in config['whitelisted_roles']:
            role = ctx.guild.get_role(int(role_id))
            if role:
                whitelisted.append(role.name)
        
        whitelist_text = ", ".join(whitelisted) if whitelisted else "Aucun"
        
        await ctx.send(
            f"**Configuration Anti-Liens**\n"
            f"Statut : {status}\n"
            f"Rôles exemptés : {whitelist_text}"
        )

    @antilink.command(name='on')
    @check_permission_level(7)
    async def antilink_on(self, ctx):
        db.set_antilink_enabled(ctx.guild.id, True)
        await ctx.send("Anti-liens activé. Les liens seront supprimés automatiquement.")

    @antilink.command(name='off')
    @check_permission_level(7)
    async def antilink_off(self, ctx):
        db.set_antilink_enabled(ctx.guild.id, False)
        await ctx.send("Anti-liens désactivé.")

    @antilink.command(name='whitelist')
    @check_permission_level(7)
    async def antilink_whitelist(self, ctx, role: discord.Role):
        db.add_antilink_whitelist_role(ctx.guild.id, role.id)
        await ctx.send(f"Le rôle **{role.name}** peut maintenant envoyer des liens.")

    @antilink.command(name='unwhitelist')
    @check_permission_level(7)
    async def antilink_unwhitelist(self, ctx, role: discord.Role):
        db.remove_antilink_whitelist_role(ctx.guild.id, role.id)
        await ctx.send(f"Le rôle **{role.name}** ne peut plus envoyer de liens.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        config = db.get_antilink_config(message.guild.id)
        if not config['enabled']:
            return
        
        # Vérifier si l'utilisateur a un rôle whitelisté
        user_role_ids = [str(role.id) for role in message.author.roles]
        if any(role_id in config['whitelisted_roles'] for role_id in user_role_ids):
            return
        
        # Vérifier si l'utilisateur a des permissions de modération
        if message.author.guild_permissions.manage_messages:
            return
        
        # Détecter les liens
        import re
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        discord_invite_pattern = r'discord(?:\.gg|app\.com/invite)/[a-zA-Z0-9]+'
        
        if re.search(url_pattern, message.content, re.IGNORECASE) or re.search(discord_invite_pattern, message.content, re.IGNORECASE):
            try:
                await message.delete()
                warning = await message.channel.send(f"{message.author.mention} Les liens ne sont pas autorisés ici.")
                await asyncio.sleep(5)
                await warning.delete()
            except discord.Forbidden:
                pass

class CustomHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs={
            'help': 'Affiche ce message d\'aide.'
        })

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Aide du Bot", color=discord.Color.blue())
        for cog, commands_list in mapping.items():
            if not commands_list: continue
            cog_name = cog.qualified_name if cog else "Autres"
            filtered = await self.filter_commands(commands_list, sort=True)
            if filtered:
                value = " ".join([f"`{c.name}`" for c in filtered])
                embed.add_field(name=cog_name, value=value, inline=False)
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=f"Commande: {command.name}", color=discord.Color.blue())
        embed.add_field(name="Description", value=command.help or "Pas de description.", inline=False)
        if command.aliases:
            embed.add_field(name="Alias", value=", ".join(command.aliases), inline=False)
        embed.add_field(name="Utilisation", value=f"`{self.context.prefix}{command.name} {command.signature}`", inline=False)
        await self.get_destination().send(embed=embed)

# --- Bot Setup ---
class AdvancedBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=self.get_prefix, intents=intents, help_command=CustomHelpCommand())

    async def get_prefix(self, message):
        if not message.guild: return "!"
        return db.get_prefix(message.guild.id)

    async def setup_hook(self):
        await self.add_cog(Admin(self))
        await self.add_cog(General(self))
        await self.add_cog(Moderation(self))

    async def on_ready(self):
        print(f"Advanced Bot connecté: {self.user}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = AdvancedBot()
    bot.run(TOKEN)
