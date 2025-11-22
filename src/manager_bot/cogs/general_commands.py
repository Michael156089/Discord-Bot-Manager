import discord
from discord.ext import commands
from discord import app_commands

from ..utils import get_user_cached
from ..database import get_user_bots
from ..bot_process import get_bot_status

class GeneralCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="status", description="Affiche le statut du Bot Manager et des bots de l'utilisateur.")
    async def status_cmd(self, ctx: commands.Context):
        user_id = ctx.author.id
        
        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
            return
            
        latency = round(self.bot.latency * 1000)
        status_msg = f"**Statut du Bot Manager**\n"
        status_msg += f"Latence: {latency}ms\n"
        status_msg += f"Utilisateur enregistré: Oui (Max Bots: {user_data[1]})\n"
        
        user_bots = await get_user_bots(user_id)
        if not user_bots:
            status_msg += "\n**Vos Bots**\nAucun bot enregistré. Utilisez `/add_bot`."
        else:
            status_msg += "\n**Vos Bots**\n"
            for bot_data in user_bots:
                bot_name = bot_data[2]
                process_status = get_bot_status(user_id, bot_name)
                status_msg += f"- **{bot_name}**: {process_status}\n"
                
        await ctx.send(status_msg, ephemeral=True)

    @commands.hybrid_command(name="ping", description="Verifie la latence du Bot Manager.")
    async def ping_cmd(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Latence du Bot Manager: {latency}ms", ephemeral=True)

async def setup(bot):
    await bot.add_cog(GeneralCommands(bot))
