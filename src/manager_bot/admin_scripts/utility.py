"""
Bot Discord Utilitaire - Script pour les utilisateurs.
Charge sa configuration (token) via la variable d'environnement DISCORD_BOT_TOKEN
fournie par le Bot Manager. Le prefixe est fixe.
"""

import discord
from discord.ext import commands
from datetime import timedelta
import os
import sys

# --- CONFIG SIMPLE --- #
# Le token vient TOUJOURS de la variable d'environnement fournie par le Bot Manager
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PREFIX = "!" # Le prefixe est fixe pour ce bot utilisateur

if not TOKEN:
    print("ERREUR: Le token du bot est manquant. Assurez-vous que DISCORD_BOT_TOKEN est defini.")
    sys.exit(1)

# --- BOT SETUP --- #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, description="Bot Utilitaire Discord", help_command=None)

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipe_cache = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        self.snipe_cache[message.channel.id] = {
            'content': message.content,
            'author': message.author,
            'created_at': message.created_at
        }

    @commands.command(name='snipe')
    async def snipe_message(self, ctx):
        if ctx.channel.id not in self.snipe_cache:
            await ctx.send("Aucun message a sniper.")
            return
        data = self.snipe_cache[ctx.channel.id]
        await ctx.send(f"Message supprime par {data['author'].display_name}:\n>>> {data['content']}")

    @commands.command(name='pic', aliases=['avatar', 'pp'])
    async def profile_picture(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        embed = discord.Embed(title=f"Avatar de {target.display_name}", color=0x7289DA)
        embed.set_image(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='userinfo', aliases=['ui'])
    async def user_info(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        embed = discord.Embed(title=f"Info {target.display_name}", color=target.color)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="ID", value=target.id)
        embed.add_field(name="Cree le", value=f"<t:{int(target.created_at.timestamp())}:D>")
        embed.add_field(name="Rejoint le", value=f"<t:{int(target.joined_at.timestamp())}:D>")
        await ctx.send(embed=embed)

    @commands.command(name='serverinfo', aliases=['si'])
    async def serverinfo(self, ctx):
        g = ctx.guild
        embed = discord.Embed(title=g.name, color=0x3498DB)
        embed.add_field(name="ID", value=g.id)
        embed.add_field(name="Membres", value=g.member_count)
        embed.add_field(name="Owner", value=g.owner.mention)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        await ctx.send(embed=embed)

    @commands.command(name='ping')
    async def ping(self, ctx):
        await ctx.send(f"Latence: {round(self.bot.latency * 1000)}ms")

    def parse_duration(self, duration_str: str):
        unit_map = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
        if not duration_str or not duration_str[:-1].isdigit():
            return None
        unit = duration_str[-1].lower()
        if unit not in unit_map:
            return None
        try:
            value = int(duration_str[:-1])
            return timedelta(**{unit_map[unit]: value})
        except:
            return None

    @commands.command(name='clear', aliases=['purge'])
    @commands.has_permissions(manage_messages=True)
    async def clear_messages(self, ctx, amount: int = 10, member: discord.Member = None):
        if not 1 <= amount <= 100:
            await ctx.send("Entre 1 et 100 messages.")
            return
        
        await ctx.message.delete()
        
        if member:
            deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author == member)
            msg = f"{len(deleted)} messages de {member.display_name} supprimes."
        else:
            deleted = await ctx.channel.purge(limit=amount)
            msg = f"{len(deleted)} messages supprimes."
        
        await ctx.send(msg, delete_after=5)

    @commands.command(name='mute', aliases=['timeout'])
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, duration: str, *, reason="Aucune raison"):
        dur = self.parse_duration(duration)
        if not dur:
            await ctx.send("Format invalide (ex: 10m, 1h, 1d)")
            return
        
        try:
            await member.timeout(dur, reason=reason)
            await ctx.send(f"{member.display_name} mute pour {duration}.")
        except discord.Forbidden:
            await ctx.send("Pas les permissions.")

    @commands.command(name='unmute')
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        if not member.is_timed_out():
            await ctx.send(f"{member.display_name} n'est pas mute.")
            return
        
        try:
            await member.timeout(None)
            await ctx.send(f"{member.display_name} peut parler.")
        except discord.Forbidden:
            await ctx.send("Pas les permissions.")

    @commands.command(name='kick')
    @commands.has_permissions(kick_members=True)
    async def kick_member(self, ctx, member: discord.Member, *, reason="Aucune raison"):
        if member == ctx.author:
            await ctx.send("Tu peux pas te kick!")
            return
        
        try:
            await member.kick(reason=reason)
            await ctx.send(f"{member.display_name} kick.")
        except discord.Forbidden:
            await ctx.send("Pas les permissions.")

    @commands.command(name='ban')
    @commands.has_permissions(ban_members=True)
    async def ban_member(self, ctx, member: discord.Member, *, reason="Aucune raison"):
        try:
            await member.ban(reason=reason)
            await ctx.send(f"{member.display_name} banni.")
        except discord.Forbidden:
            await ctx.send("Pas les permissions.")

    @commands.command(name='unban')
    @commands.has_permissions(ban_members=True)
    async def unban_member(self, ctx, *, user_input: str):
        banned_users = [ban_entry async for ban_entry in ctx.guild.bans()]
        target = None
        
        if user_input.isdigit():
            user_id = int(user_input)
            for entry in banned_users:
                if entry.user.id == user_id:
                    target = entry.user
                    break
        
        if target:
            await ctx.guild.unban(target)
            await ctx.send(f"{target.name} debanni.")
        else:
            await ctx.send("User introuvable dans les bannis.")

    @commands.command(name='help')
    async def custom_help(self, ctx, *, cmd: str = None):
        if cmd:
            command = self.bot.get_command(cmd.lower())
            if not command:
                await ctx.send(f"Commande '{cmd}' introuvable.")
                return
            await ctx.send(f"**{command.name}**: {command.help or 'Pas de description'}")
        else:
            embed = discord.Embed(title="Aide", description=f"Prefixe: `{PREFIX}`", color=0x3498DB)
            embed.add_field(name="Info", value="pic, userinfo, serverinfo, ping, snipe", inline=False)
            embed.add_field(name="Moderation", value="clear, mute, unmute, kick, ban, unban", inline=False)
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"✅ Bot {self.bot.user} connecte!")
        print(f"   Prefixe: {PREFIX}")
        print(f"   Serveurs: {len(self.bot.guilds)}")
        # ✅ Signal de connexion réussi pour le Bot Manager
        print("[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE")

async def main():
    async with bot:
        await bot.add_cog(Utility(bot))
        await bot.start(TOKEN)

if __name__ == "__main__":
    print(f"Demarrage du bot (prefixe: {PREFIX})...")
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot arrete.")
    except Exception as e:
        print(f"ERREUR FATALE: {e}")
        sys.exit(1)