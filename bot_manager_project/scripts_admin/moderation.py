import discord
from discord.ext import commands
import typing
from datetime import datetime, timedelta
from .utils.database import get_user_permission_level, get_prefix, get_immunity_role
from .utils.converters import get_target_user_async
from .utils.logger import log_action
from .utils.responses import get_random_response
import os

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

def parse_duration(duration_str: str) -> timedelta | None:
    """Convertit une chaîne de durée (ex: 1d, 3h, 30m, 5s) en objet timedelta."""
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

def check_permission_level(required_level):
    """Décorateur pour vérifier si l'utilisateur a le niveau de permission requis."""
    async def predicate(ctx):
        user_level = get_user_permission_level(ctx.author)
        if user_level >= required_level:
            return True
        
        await ctx.send(get_random_response("permission_denied", level=required_level))
        return False
    return commands.check(predicate)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_immune(self, ctx, member: discord.Member, action: str):
        """Vérifie si un membre est immunisé contre une action modérative."""
        immunity_role_id = get_immunity_role(ctx.guild.id)
        if immunity_role_id:
            immunity_role = ctx.guild.get_role(immunity_role_id)
            if immunity_role and immunity_role in member.roles:
                response_key = f"{action}_fail_immune"
                await ctx.send(get_random_response(response_key, target=member.display_name))
                return True
        return False

    @commands.command(name='ban')
    @check_permission_level(7)
    async def ban_member(self, ctx, *, user_input: str):
        """Bannit un membre du serveur. Nécessite le niveau 7."""
        # Sépare la cible de la raison
        parts = user_input.split()
        target_str = parts[0]
        reason = ' '.join(parts[1:]) if len(parts) > 1 else "Aucune raison fournie."

        target = await get_target_user_async(ctx, target_str)
        if not target:
            await ctx.send("J'trouve pas ce membre. Mentionne-le, donne son ID, ou réponds à un de ses messages.")
            return
            
        if await self.is_immune(ctx, target, 'ban'):
            return

        # Empêche de bannir un membre de rang égal ou supérieur
        if target.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("Tu peux pas ban un gars plus haut gradé que toi, c'est la base.")
            return

        try:
            await target.ban(reason=f"Banni par {ctx.author}: {reason}")
            await ctx.send(get_random_response("ban_success", target=target.display_name))
            await log_action(self.bot, ctx, target, 'ban', reason)
        except discord.Forbidden:
            await ctx.send("J'ai pas la perm de ban, chef.")

    @commands.command(name='unban')
    @check_permission_level(7)
    async def unban_member(self, ctx, *, user_input: str):
        """Débannit un membre. Nécessite le niveau 7."""
        banned_users = [ban_entry async for ban_entry in ctx.guild.bans()]
        target_user = None

        # Recherche l'utilisateur banni par nom/discriminator ou ID
        if '#' in user_input:
            name, discriminator = user_input.split('#')
            target_entry = discord.utils.get(banned_users, user__name=name, user__discriminator=discriminator)
            if target_entry:
                target_user = target_entry.user
        elif user_input.isdigit():
            user_id = int(user_input)
            target_entry = discord.utils.get(banned_users, user__id=user_id)
            if target_entry:
                target_user = target_entry.user

        if target_user:
            await ctx.guild.unban(target_user, reason=f"Débanni par {ctx.author.name}")
            await ctx.send(f"**{target_user.name}** est de retour. Tenez-vous à carreau.")
            await log_action(self.bot, ctx, target_user, 'unban', f"Débanni par {ctx.author.name}")
        else:
            await ctx.send(f"J'trouve pas ce gars dans la liste des bannis. T'es sûr de son nom ?")

    @commands.command(name='kick')
    @check_permission_level(6)
    async def kick_member(self, ctx, *, user_input: str):
        """Expulse un membre du serveur. Nécessite le niveau 6."""
        parts = user_input.split()
        target_str = parts[0]
        reason = ' '.join(parts[1:]) if len(parts) > 1 else "Aucune raison fournie."

        target = await get_target_user_async(ctx, target_str)
        if not target:
            await ctx.send("Membre introuvable. Mentionne-le, donne son ID, ou réponds à un de ses messages pour que ça marche.")
            return
            
        if await self.is_immune(ctx, target, 'kick'):
            return
            
        if target == ctx.author:
            await ctx.send("Te kick pas toi-même, t'es fou ou quoi ?")
            return

        # Empêche de kicker un membre de rang égal ou supérieur
        if target.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("Tu peux pas kick un gars plus gradé, respecte la hiérarchie.")
            return

        try:
            await target.kick(reason=f"Expulsé par {ctx.author}: {reason}")
            await ctx.send(get_random_response("kick_success", target=target.display_name))
            await log_action(self.bot, ctx, target, 'kick', reason)
        except discord.Forbidden:
            await ctx.send("J'ai pas la perm de kick, désolé.")

    @commands.command(name="mute", aliases=["timeout"])
    @check_permission_level(5)
    async def mute(self, ctx, user_input: str, duration_str: str, *, reason="Aucune raison donnée"):
        """Met un membre en sourdine pour une durée spécifiée. Nécessite le niveau 5."""
        target = await get_target_user_async(ctx, user_input)
        if not target:
            await ctx.send("Je vois pas de qui tu parles. Mentionne-le, donne son ID, ou réponds à un de ses messages.")
            return

        if await self.is_immune(ctx, target, 'mute'):
            return

        # Empêche de mute un membre de rang égal ou supérieur
        if target.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("Tu peux pas mute un boss, c'est la règle.")
            return

        duration = parse_duration(duration_str)
        if not duration:
            await ctx.send("La durée, c'est pas bon. Utilise un format comme `10m`, `1h`, ou `1d`.")
            return

        try:
            await target.timeout(duration, reason=reason)
            await ctx.send(f"**{target.display_name}** est en sourdine pour {duration_str}. Fini de parler pour un temps.")
            await log_action(self.bot, ctx, target, 'mute', reason, duration_str)
        except discord.Forbidden:
            await ctx.send("J'peux pas le mute, j'ai pas les droits.")

    @commands.command(name="unmute")
    @check_permission_level(5)
    async def unmute(self, ctx, *, user_input: str):
        """Redonne la parole à un membre. Nécessite le niveau 5."""
        parts = user_input.split()
        target_str = parts[0]
        reason = ' '.join(parts[1:]) if len(parts) > 1 else "Raison non spécifiée."

        target = await get_target_user_async(ctx, target_str)
        if not target:
            await ctx.send("Impossible de trouver ce membre. Mentionne-le, donne son ID, ou réponds à un de ses messages.")
            return

        if await self.is_immune(ctx, target, 'unmute'):
            return

        if not target.is_timed_out():
            await ctx.send(f"**{target.display_name}** n'est même pas mute, en fait.")
            return

        try:
            await target.timeout(None, reason=reason) # Retire le timeout
            await ctx.send(f"C'est bon, **{target.display_name}** peut de nouveau parler. Soyez sympa avec lui.")
            await log_action(self.bot, ctx, target, 'unmute', reason)
        except discord.Forbidden:
            await ctx.send("J'ai pas la permission de faire ça, chef.")

    @commands.command(name='clear', aliases=['purge'])
    @check_permission_level(4)
    async def clear_messages(self, ctx, arg1: typing.Union[int, discord.Member], arg2: typing.Optional[typing.Union[int, discord.Member]] = None):
        """Nettoie le canal en supprimant un nombre spécifié de messages. Peut cibler un membre précis. Nécessite le niveau 4."""
        amount = None
        target = None

        # Détermine le nombre de messages et la cible à partir des arguments
        if isinstance(arg1, int):
            amount = arg1
            target = arg2 if isinstance(arg2, discord.Member) else None
        elif isinstance(arg1, discord.Member):
            target = arg1
            amount = arg2 if isinstance(arg2, int) else None
        
        if amount is None:
            await ctx.send(f"T'as oublié de me dire combien de messages je dois supprimer. La syntaxe : `{get_prefix(ctx.guild.id)}clear <nombre> [@membre]`")
            return

        if not 1 <= amount <= 100:
            await ctx.send("Le nombre de messages, c'est entre 1 et 100, pas plus.")
            return

        await ctx.message.delete() # Supprime le message de commande

        if target:
            # Purge les messages d'un membre spécifique
            def is_target(m):
                return m.author == target
            deleted = await ctx.channel.purge(limit=amount, check=is_target)
            msg = f"J'ai viré {len(deleted)} message(s) de **{target.display_name}**. C'est clean."
        else:
            # Purge tous les messages
            deleted = await ctx.channel.purge(limit=amount)
            msg = f"J'ai fait le ménage, {len(deleted)} message(s) ont disparu. Propre."

        await ctx.send(msg, delete_after=5)

    @commands.command(name='warn')
    @check_permission_level(5)
    async def warn_user(self, ctx, user_input: str, *, reason="Aucune raison spécifiée"):
        """Met un avertissement à un membre. Nécessite le niveau 5."""
        target = await get_target_user_async(ctx, user_input)
        if not target:
            await ctx.send("Membre introuvable. Mentionne-le, donne son ID, ou réponds à un de ses messages.")
            return

        if await self.is_immune(ctx, target, 'warn'):
            return

        # Enregistre l'avertissement (nécessite une implémentation DB)
        await ctx.send(f"**{target.display_name}** a été averti pour : {reason}. Fais gaffe à toi maintenant.")
        await log_action(self.bot, ctx, target, 'warn', reason)

        try:
            await target.send(f"T'as reçu un avertissement sur le serveur **{ctx.guild.name}** pour la raison suivante : **{reason}**.")
        except discord.Forbidden:
            pass # L'utilisateur a bloqué ses MPs

    @commands.command(name='warnings')
    @check_permission_level(5)
    async def show_warnings(self, ctx, member: discord.Member):
        """Affiche les avertissements d'un membre. Nécessite le niveau 5."""
        # Récupère et affiche les avertissements depuis la base de données (fonctionnalité à implémenter)
        await ctx.send(f"Je check les dossiers de {member.display_name}... (Fonctionnalité en cours de dev)")

@bot.event
async def on_ready():
    print(f"Bot Moderation connecté: {bot.user}")
    await bot.add_cog(Moderation(bot))

if __name__ == "__main__":
    # La fonction init_database doit être appelée pour s'assurer que les tables sont créées
    # Cela devrait être géré au niveau du Manager ou dans un mécanisme d'initialisation propre au bot.
    # Pour un script indépendant, on peut l'appeler ici, mais il est préférable que le bot Manager gère la création des DB.
    # from .utils.database import init_database
    # init_database()
    bot.run(TOKEN)
