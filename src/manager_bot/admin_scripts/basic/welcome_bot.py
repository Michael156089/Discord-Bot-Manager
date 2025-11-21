# Template: Welcome Bot
# Messages de bienvenue avec auto-roles

import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

WELCOME_CHANNEL_NAME = "bienvenue"
AUTO_ROLE_NAME = "Membre"

class WelcomeBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Envoyer un message de bienvenue quand quelqu'un rejoint."""
        guild = member.guild
        
        welcome_channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)
        
        if not welcome_channel:
            print(f"⚠️ Channel '{WELCOME_CHANNEL_NAME}' introuvable sur {guild.name}")
            return
        
        embed = discord.Embed(
            title =f"👋 Bienvenue!",
            description=f"Bienvenue {member.mention} sur **{guild.name}**!\n\nNous sommes maintenant **{guild.member_count}** membres !",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        
        await welcome_channel.send(embed=embed)
        
        auto_role = discord.utils.get(guild.roles, name=AUTO_ROLE_NAME)
        if auto_role:
            try:
                await member.add_roles(auto_role)
                print(f"✅ Rôle '{AUTO_ROLE_NAME}' ajouté à {member}")
            except discord.Forbidden:
                print(f"❌ Pas les permissions pour ajouter le rôle à {member}")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Message quand quelqu'un quitte le serveur."""
        guild = member.guild
        
        welcome_channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)
        
        if welcome_channel:
            await welcome_channel.send(f"👋 **{member.display_name}** a quitté le serveur. Nous sommes maintenant **{guild.member_count}** membres.")
    
    @commands.command(name='setwelcome')
    @commands.has_permissions(administrator=True)
    async def set_welcome_channel(self, ctx, channel: discord.TextChannel):
        """[ADMIN] Définir le channel de bienvenue."""
        global WELCOME_CHANNEL_NAME
        WELCOME_CHANNEL_NAME = channel.name
        await ctx.send(f"✅ Channel de bienvenue défini sur {channel.mention}")
    
    @commands.command(name='setautorole')
    @commands.has_permissions(administrator=True)
    async def set_auto_role(self, ctx, role: discord.Role):
        """[ADMIN] Définir le rôle automatique."""
        global AUTO_ROLE_NAME
        AUTO_ROLE_NAME = role.name
        await ctx.send(f"✅ Rôle automatique défini sur **{role.name}**")
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"👋 Welcome Bot '{self.bot.user}' connecté!")
        print(f"   Channel bienvenue: '{WELCOME_CHANNEL_NAME}'")
        print(f"   Auto-rôle: '{AUTO_ROLE_NAME}'")
        print("[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE")

async def main():
    async with bot:
        await bot.add_cog(WelcomeBot(bot))
        TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        if not TOKEN:
            print("❌ Token manquant!")
            return
        await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
