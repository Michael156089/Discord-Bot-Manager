import discord
from discord.ext import commands
from datetime import datetime, timezone
from utils.database import get_user_level, get_rank_role, get_prefix
from utils.converters import get_target_user_async

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipe_cache = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Capture le contenu des messages supprimés pour la commande snipe."""
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
        """Affiche le dernier message supprimé dans le canal."""
        if ctx.channel.id not in self.snipe_cache:
            await ctx.send("Y'a R à snipe ici, personne n'a supprimé son message.")
            return

        snipe_data = self.snipe_cache[ctx.channel.id]
        content = snipe_data['content'] or "*Message sans contenu écrit.*"
        await ctx.send(f"**Dernier message supprimé par {snipe_data['author'].display_name} :**\n>>> {content}")

    @commands.command(name='pic', aliases=['avatar', 'pp'])
    async def profile_picture(self, ctx, *, member_input=None):
        """Affiche la photo de profil d'un membre ou de l'utilisateur."""
        target = await get_target_user_async(ctx, member_input) or ctx.author
        
        embed = discord.Embed(
            title=f"Photo de profil de {target.display_name}",
            color=0x7289DA # Couleur Discord standard
        )
        embed.set_image(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='userinfo', aliases=['ui', 'user'])
    async def user_info(self, ctx, *, member_input=None):
        """Donne des informations détaillées sur un membre ou l'utilisateur."""
        target = await get_target_user_async(ctx, member_input) or ctx.author
        level, xp = get_user_level(target.id, ctx.guild.id)

        embed = discord.Embed(
            title=f"Infos sur {target.display_name}",
            color=target.color
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Blaze", value=target.name, inline=True)
        embed.add_field(name="ID", value=target.id, inline=True)
        embed.add_field(name="Niveau", value=f"{level} ({xp} XP)", inline=True)
        embed.add_field(name="Compte créé le", value=f"<t:{int(target.created_at.timestamp())}:D>", inline=False)
        embed.add_field(name="A rejoint le serveur le", value=f"<t:{int(target.joined_at.timestamp())}:D>", inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name='level', aliases=['lvl'])
    async def check_level(self, ctx, *, member_input=None):
        """Affiche le niveau et l'XP d'un membre ou de l'utilisateur."""
        target = await get_target_user_async(ctx, member_input) or ctx.author
        level, xp = get_user_level(target.id, ctx.guild.id)

        await ctx.send(f"**{target.display_name}** est niveau **{level}** avec **{xp}** XP. Ça charbonne !")

    @commands.command(name='rankinfo')
    async def rank_info(self, ctx):
        """Affiche les rôles configurés pour chaque niveau de rang sur le serveur."""
        embed = discord.Embed(
            title="Les Rangs du Serveur",
            description="Voici les rôles associés à chaque niveau de rang (1 à 9).",
            color=0xE91E63 # Rose
        )
        
        for i in range(1, 10):
            role_id = get_rank_role(ctx.guild.id, i)
            role_name = "Aucun rôle assigné."
            if role_id:
                role = ctx.guild.get_role(int(role_id))
                if role:
                    role_name = f"@{role.name}"
            embed.add_field(name=f"Rang {i}", value=role_name, inline=True)

        await ctx.send(embed=embed)

    @commands.command(name='help')
    async def custom_help(self, ctx, *, command_name: str = None):
        """Affiche l'aide pour toutes les commandes ou une commande spécifique."""
        prefix = get_prefix(ctx.guild.id)
        
        if command_name:
            command = self.bot.get_command(command_name.lower())
            if not command:
                await ctx.send(f"La commande `{command_name}` ? Jamais entendu parler.")
                return

            embed = discord.Embed(
                title=f"Aide pour la commande `{command.name}`",
                description=command.help or "Pas de description pour cette commande, déso.",
                color=0x2ECC71 # Vert
            )
            usage = f"`{prefix}{command.name} {command.signature}`"
            embed.add_field(name="Utilisation", value=usage, inline=False)
            
            if command.aliases:
                aliases = ", ".join([f"`{alias}`" for alias in command.aliases])
                embed.add_field(name="Alias", value=aliases, inline=False)
            
            embed.set_footer(text=f"Utilise `{prefix}help` pour voir toutes les commandes.")
            await ctx.send(embed=embed)

        else:
            embed = discord.Embed(
                title="Aide du Bot Mouton",
                description=f"Salut ! Voici la liste de mes commandes. Le préfixe actuel est `{prefix}`.\n"
                            "Pour plus de détails sur une commande, tape `!help [nom de la commande]`.",
                color=0x3498DB # Bleu clair
            )

            cogs = sorted(self.bot.cogs.keys()) # Trie les cogs par nom
            
            for cog_name in cogs:
                cog = self.bot.get_cog(cog_name)
                commands = cog.get_commands()
                
                visible_commands = [c for c in commands if not c.hidden] # N'affiche que les commandes non cachées
                if not visible_commands:
                    continue

                command_list = [f"`{c.name}`" for c in visible_commands]
                embed.add_field(
                    name=f"**Catégorie : {cog_name}**",
                    value=" ".join(command_list),
                    inline=False
                )
            
            embed.set_footer(text=f"Astuce : `{prefix}perms` pour voir les niveaux de permission requis.")
            await ctx.send(embed=embed)


    @commands.command(name='perms')
    async def permissions_info(self, ctx):
        """Affiche les niveaux de permission requis pour chaque commande."""
        embed = discord.Embed(
            title="Niveaux de Permission des Commandes",
            description="Voici le niveau de permission requis pour utiliser chaque commande du bot (Niveau 9 = Admin).",
            color=0x9B59B6 # Violet
        )

        cogs = sorted(self.bot.cogs.keys())
        
        for cog_name in cogs:
            cog = self.bot.get_cog(cog_name)
            commands = cog.get_commands()
            visible_commands = [c for c in commands if not c.hidden]
            if not visible_commands:
                continue

            command_list = []
            for command in visible_commands:
                perm_level = "N/A" # Niveau par défaut si non spécifié
                if command.checks:
                    for check in command.checks:
                        # Extrait le niveau de permission du décorateur de check_permission_level
                        try:
                            code = check.__code__
                            # Cherche la première constante entière dans le code du check (le niveau requis)
                            level_str = next(str(const) for const in code.co_consts if isinstance(const, int))
                            perm_level = level_str
                        except (AttributeError, StopIteration):
                            continue
                
                command_list.append(f"`{command.name}` (Lvl {perm_level})")
            
            if command_list:
                embed.add_field(
                    name=f"**Catégorie : {cog_name}**",
                    value="\n".join(command_list),
                    inline=False
                )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(General(bot))