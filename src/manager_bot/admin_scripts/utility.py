"""
Bot Discord Utilitaire Autonome
Charge sa configuration directement depuis une base de donnees
Utilisation: python utility.py
"""

import discord
from discord.ext import commands
from datetime import timedelta
import typing
import os
import json
import sys
import sqlite3

# --- DATABASE SETUP --- #
DB_PATH = "bot_config.db"

def init_db():
    """Initialize database for bot configuration."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            token TEXT NOT NULL,
            prefix TEXT DEFAULT "!",
            description TEXT DEFAULT "Bot Utilitaire Discord"
        )
    ''')
    
    # Insert default config if empty
    cursor.execute("SELECT COUNT(*) FROM bot_config")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO bot_config (id, token, prefix, description)
            VALUES (1, "", "!", "Bot Utilitaire Discord")
        ''')
        conn.commit()
        print(f"Base de donnees initialisee: {DB_PATH}")
    
    conn.close()

def load_config():
    """Load bot configuration from database."""
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT token, prefix, description FROM bot_config WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        token, prefix, description = row
        return {
            "TOKEN": token or os.getenv("DISCORD_BOT_TOKEN", ""),
            "PREFIX": prefix or "!",
            "DESCRIPTION": description or "Bot Utilitaire Discord"
        }
    
    return {
        "TOKEN": os.getenv("DISCORD_BOT_TOKEN", ""),
        "PREFIX": "!",
        "DESCRIPTION": "Bot Utilitaire Discord"
    }

# Charger la config
config = load_config()

# Verifier le token
TOKEN = config.get("TOKEN")
PREFIX = config.get("PREFIX", "!")

if not TOKEN:
    print("ERREUR: Token non configure.")
    print("Methodes pour ajouter le token:")
    print("1. Variable d'environnement: set DISCORD_BOT_TOKEN=votre_token")
    print("Le bot attend un token valide pour demarrer.")
    sys.exit(1)

# --- BOT SETUP --- #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ✅ Désactiver la commande help par défaut pour éviter les conflits
bot = commands.Bot(command_prefix=PREFIX, intents=intents, description=config.get("DESCRIPTION", "Bot Utilitaire Discord"), help_command=None)

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipe_cache = {}

    # --- SNIPE & MESSAGES --- #
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Capture les messages supprimes pour la commande snipe."""
        if message.author.bot:
            return
        self.snipe_cache[message.channel.id] = {
            'content': message.content,
            'author': message.author,
            'created_at': message.created_at,
            'attachments': [attachment.url for attachment in message.attachments] if message.attachments else []
        }

    @commands.command(name='snipe')
    async def snipe_message(self, ctx):
        """Affiche le dernier message qui a ete supprime."""
        if ctx.channel.id not in self.snipe_cache:
            await ctx.send("Aucun message a sniper ici.")
            return
        snipe_data = self.snipe_cache[ctx.channel.id]
        content = snipe_data['content'] or "[Message sans contenu]"
        await ctx.send(f"Dernier message supprime par {snipe_data['author'].display_name}:\n>>> {content}")

    # --- INFOS UTILISATEUR --- #
    @commands.command(name='pic', aliases=['avatar', 'pp'])
    async def profile_picture(self, ctx, *, member: discord.Member = None):
        """Montre la photo de profil d'un gars."""
        target = member or ctx.author
        embed = discord.Embed(
            title=f"Photo de profil de {target.display_name}",
            color=0x7289DA
        )
        embed.set_image(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='userinfo', aliases=['ui', 'user'])
    async def user_info(self, ctx, *, member: discord.Member = None):
        """Donne les infos sur un membre."""
        target = member or ctx.author
        embed = discord.Embed(
            title=f"Infos sur {target.display_name}",
            color=target.color
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Nom", value=target.name, inline=True)
        embed.add_field(name="ID", value=target.id, inline=True)
        embed.add_field(name="Compte cree le", value=f"<t:{int(target.created_at.timestamp())}:D>", inline=False)
        embed.add_field(name="A rejoint le", value=f"<t:{int(target.joined_at.timestamp())}:D>", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='serverinfo', aliases=['si', 'server'])
    async def serverinfo(self, ctx):
        """Affiche les infos du serveur."""
        guild = ctx.guild
        embed = discord.Embed(title=f"Infos de {guild.name}", color=discord.Color.blue())
        embed.add_field(name="ID", value=guild.id)
        embed.add_field(name="Membres", value=guild.member_count)
        embed.add_field(name="Proprietaire", value=guild.owner.mention)
        embed.add_field(name="Cree le", value=guild.created_at.strftime("%d/%m/%Y"))
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        await ctx.send(embed=embed)

    @commands.command(name='ping')
    async def ping(self, ctx):
        """Affiche la latence du bot."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Latence: {latency}ms")

    # --- MODERATION --- #
    def parse_duration(self, duration_str: str) -> timedelta:
        """Parse duration string (e.g., 1d, 3h, 30m, 5s)."""
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
        except (ValueError, TypeError):
            return None

    @commands.command(name='clear', aliases=['purge'])
    @commands.has_permissions(manage_messages=True)
    async def clear_messages(self, ctx, amount: int = 10, member: discord.Member = None):
        """Nettoie le canal. Peut cibler un membre precis."""
        if not 1 <= amount <= 100:
            await ctx.send("Le nombre de messages, c'est entre 1 et 100.")
            return
        
        await ctx.message.delete()
        
        if member:
            def is_target(m):
                return m.author == member
            deleted = await ctx.channel.purge(limit=amount, check=is_target)
            msg = f"Supprime {len(deleted)} message(s) de {member.display_name}."
        else:
            deleted = await ctx.channel.purge(limit=amount)
            msg = f"Nettoyage termine: {len(deleted)} message(s) supprime(s)."
        
        await ctx.send(msg, delete_after=5)

    @commands.command(name='mute', aliases=['timeout'])
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, duration: str, *, reason="Aucune raison"):
        """Met un membre en sourdine."""
        dur = self.parse_duration(duration)
        if not dur:
            await ctx.send("Format invalide. Utilise: 10m, 1h, 1d, etc.")
            return
        
        try:
            await member.timeout(dur, reason=reason)
            await ctx.send(f"{member.display_name} est mute pour {duration}.")
        except discord.Forbidden:
            await ctx.send("Je n'ai pas les droits pour mute.")

    @commands.command(name='unmute')
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        """Redonne la parole a un membre."""
        if not member.is_timed_out():
            await ctx.send(f"{member.display_name} n'est pas mute.")
            return
        
        try:
            await member.timeout(None)
            await ctx.send(f"{member.display_name} peut parler a nouveau.")
        except discord.Forbidden:
            await ctx.send("Je n'ai pas la permission.")

    @commands.command(name='kick')
    @commands.has_permissions(kick_members=True)
    async def kick_member(self, ctx, member: discord.Member, *, reason="Aucune raison"):
        """Expulse un membre."""
        if member == ctx.author:
            await ctx.send("Tu ne peux pas te kick toi-meme!")
            return
        
        try:
            await member.kick(reason=reason)
            await ctx.send(f"{member.display_name} a ete expulse.")
        except discord.Forbidden:
            await ctx.send("Je n'ai pas la permission de kick.")

    @commands.command(name='ban')
    @commands.has_permissions(ban_members=True)
    async def ban_member(self, ctx, member: discord.Member, *, reason="Aucune raison"):
        """Bannit un membre."""
        try:
            await member.ban(reason=reason)
            await ctx.send(f"{member.display_name} a ete banni.")
        except discord.Forbidden:
            await ctx.send("Je n'ai pas la permission de ban.")

    @commands.command(name='unban')
    @commands.has_permissions(ban_members=True)
    async def unban_member(self, ctx, *, user_input: str):
        """Debannit un membre."""
        banned_users = [ban_entry async for ban_entry in ctx.guild.bans()]
        target_user = None
        
        if user_input.isdigit():
            user_id = int(user_input)
            target_user = discord.utils.get(banned_users, user__id=user_id)
            if target_user:
                target_user = target_user.user
        
        if target_user:
            await ctx.guild.unban(target_user)
            await ctx.send(f"{target_user.name} est debanni.")
        else:
            await ctx.send("Membre introuvable dans les bannis.")

    # --- HELP --- #
    @commands.command(name='help')
    async def custom_help(self, ctx, *, command_name: str = None):
        """Affiche l'aide du bot."""
        if command_name:
            cmd = self.bot.get_command(command_name.lower())
            if not cmd:
                await ctx.send(f"Commande '{command_name}' introuvable.")
                return
            embed = discord.Embed(
                title=f"Aide: {cmd.name}",
                description=cmd.help or "Pas de description.",
                color=0x2ECC71
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Aide du Bot",
                description=f"Prefixe actuel: `{PREFIX}`. Utilise {PREFIX}help [commande] pour plus de details.",
                color=0x3498DB
            )
            embed.add_field(name="Infos", value="pic, userinfo, serverinfo, ping, snipe", inline=False)
            embed.add_field(name="Moderation", value="clear, mute, unmute, kick, ban, unban", inline=False)
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Bot connecte en tant que {self.bot.user}")
        print(f"Prefixe: {PREFIX}")
        print(f"Base de donnees: {DB_PATH}")

async def main():
    async with bot:
        await bot.add_cog(Utility(bot))
        await bot.start(TOKEN)

if __name__ == "__main__":
    print(f"Demarrage du bot avec le prefixe: {PREFIX}")
    print(f"Configuration stockee dans: {DB_PATH}")
    
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot arrete.")
