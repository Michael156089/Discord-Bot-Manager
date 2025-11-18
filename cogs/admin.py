import discord
from discord.ext import commands
from utils.responses import get_random_response
from utils.database import (
    get_user_permission_level,
    set_guild_prefix,
    set_rank_role,
    get_rank_role,
    get_all_rank_roles,
    set_user_level,
    get_user_level,
    set_immunity_role,
    get_immunity_role,
    set_log_channel,
    set_permission_role,
    remove_permission_role,
    get_permission_roles
)


def check_permission_level(required_level):
    """Décorateur pour vérifier si l'utilisateur a le niveau de permission requis."""
    async def predicate(ctx):
        user_level = get_user_permission_level(ctx.author)
        if user_level >= required_level:
            return True
        await ctx.send(get_random_response("permission_denied", level=required_level))
        return False
    return commands.check(predicate)


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setprefix')
    @check_permission_level(9)
    async def set_prefix(self, ctx, new_prefix: str):
        """Change le préfixe du bot sur le serveur. Nécessite le niveau 9."""
        if len(new_prefix) > 5:
            await ctx.send("Le préfixe doit faire 5 caractères max, pas un de plus.")
            return

        set_guild_prefix(ctx.guild.id, new_prefix)
        await ctx.send(get_random_response("setprefix_success", prefix=new_prefix))

    @commands.command(name='rankassign')
    @check_permission_level(9)
    async def rank_assign(self, ctx, rank_level: int, role: discord.Role):
        """Assigne un rôle Discord à un niveau de rang spécifique (1-9). Nécessite le niveau 9."""
        if not 1 <= rank_level <= 9:
            await ctx.send("Les rangs, c'est de 1 à 9. C'est tout.")
            return

        set_rank_role(ctx.guild.id, rank_level, role.id)
        await ctx.send(f"Ok, le rôle **{role.name}** est maintenant lié au rang **{rank_level}**.")

    @commands.command(name='rank')
    @check_permission_level(8)
    async def rank_user(self, ctx, target: discord.Member, new_rank: int):
        """Donne un nouveau rang (et rôle associé) à un membre. Nécessite le niveau 8."""
        author_level = get_user_permission_level(ctx.author)
        target_level = get_user_permission_level(target)

        # Vérifie l'immunité avant d'appliquer le rang
        immunity_role_id = get_immunity_role(ctx.guild.id)
        if immunity_role_id and immunity_role_id in [role.id for role in target.roles]:
            await ctx.send(get_random_response("rank_fail_immune", target=target.display_name))
            return

        # Vérifie les permissions pour les modérateurs (niveau 8)
        if author_level == 8:
            if target == ctx.author:
                await ctx.send("T'as cru que tu pouvais te rank toi-même ? C'est non.")
                return
            if target_level >= author_level:
                await ctx.send("Tu peux pas toucher à un gars de ton rang ou plus haut, c'est la base.")
                return
            if new_rank > 7:
                await ctx.send("Avec ton niveau, tu peux pas mettre un rang au-dessus de 7. Faut pas déconner.")
                return

        if not 1 <= new_rank <= 9:
            await ctx.send("Le rang, c'est entre 1 et 9. Point.")
            return

        role_id = get_rank_role(ctx.guild.id, new_rank)
        if not role_id:
            await ctx.send(f"Y'a pas de rôle pour le rang {new_rank}. Pense à en créer un avec `rankassign`.")
            return

        new_role = ctx.guild.get_role(int(role_id))
        if not new_role:
            await ctx.send(f"Le rôle pour le rang {new_rank} a l'air d'avoir été supprimé, chef.")
            return

        try:
            # Retire tous les rôles de rang existants du membre
            all_rank_role_ids = get_all_rank_roles(ctx.guild.id)
            roles_to_remove = [role for role in target.roles if role.id in all_rank_role_ids]
            if roles_to_remove:
                await target.remove_roles(*roles_to_remove, reason=f"Changement de rang par {ctx.author}")
            
            # Ajoute le nouveau rôle de rang
            await target.add_roles(new_role, reason=f"Rang {new_rank} assigné par {ctx.author}")
        
        except discord.Forbidden:
            await ctx.send("Oups, j'ai pas la permission de gérer les rôles. Vérifie que mon rôle est au-dessus des rôles de rang et que j'ai la perm 'Gérer les rôles'.")
            return
        
        # Met à jour le rang de l'utilisateur dans la base de données
        _, xp = get_user_level(target.id, ctx.guild.id)
        set_user_level(target.id, ctx.guild.id, new_rank, xp)

        await ctx.send(f"C'est bon, {target.display_name} est maintenant au rang {new_rank} avec le rôle **{new_role.name}**.")

    @commands.command(name='setimmunityrole')
    @check_permission_level(9)
    async def set_immunity_role_command(self, ctx, role: discord.Role = None):
        """Définit ou supprime le rôle d'immunité pour le serveur. Nécessite le niveau 9."""
        if role:
            set_immunity_role(ctx.guild.id, role.id)
            await ctx.send(f"C'est noté. Le rôle **{role.name}** rendra les membres intouchables.")
        else:
            set_immunity_role(ctx.guild.id, None) # Supprime le rôle d'immunité
            await ctx.send("Le rôle d'immunité a été supprimé. Tout le monde est logé à la même enseigne maintenant.")

    @commands.command(name='setlogchannel')
    @check_permission_level(9)
    async def set_log_channel_command(self, ctx, channel: discord.TextChannel = None):
        """Définit ou supprime le salon de logs pour le serveur. Nécessite le niveau 9."""
        if channel:
            set_log_channel(ctx.guild.id, channel.id)
            await ctx.send(f"Parfait, le salon {channel.mention} sera maintenant utilisé pour les logs.")
        else:
            set_log_channel(ctx.guild.id, None) # Désactive le salon de logs
            await ctx.send("Le salon de logs a été désactivé.")

    @commands.command(name='setperm')
    @check_permission_level(9)
    async def set_permission(self, ctx, role: discord.Role, level: int):
        """Assigne un niveau de permission (1-8) à un rôle Discord. Nécessite le niveau 9."""
        if not 1 <= level <= 8:
            await ctx.send("Le niveau de permission doit être entre 1 et 8. Le niveau 9 est réservé aux admins.")
            return
        
        set_permission_role(ctx.guild.id, role.id, level)
        await ctx.send(f"C'est fait. Le rôle **{role.name}** a maintenant le niveau de permission **{level}**.")

    @commands.command(name='delperm')
    @check_permission_level(9)
    async def delete_permission(self, ctx, role: discord.Role):
        """Supprime le niveau de permission d'un rôle. Nécessite le niveau 9."""
        remove_permission_role(ctx.guild.id, role.id)
        await ctx.send(f"Voilà, le rôle **{role.name}** n'a plus de niveau de permission spécial.")

    @commands.command(name='listperm')
    @check_permission_level(8)
    async def list_permissions(self, ctx):
        """Affiche la liste des rôles avec un niveau de permission configuré. Nécessite le niveau 8."""
        roles_with_perms = get_permission_roles(ctx.guild.id)
        if not roles_with_perms:
            await ctx.send("Aucun rôle n'a de permission spéciale sur ce serveur.")
            return

        embed = discord.Embed(title="Permissions des Rôles", color=discord.Color.blue())
        description = ""
        for role_id, level in roles_with_perms:
            role = ctx.guild.get_role(int(role_id))
            if role:
                description += f"**{role.name}** : Niveau **{level}**\n"
        
        embed.description = description
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))