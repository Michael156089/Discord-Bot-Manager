import discord
from discord.ext import commands
from discord import app_commands
import os

from ..config import LOGS_DIR
from ..bot_process import active_processes
from ..utils import is_admin_check
from ..database import get_all_users, get_user_bots

class Phase2Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="bot_logs", description="Voir les logs de l'un de vos bots")
    @app_commands.describe(bot_name="Nom du bot", lines="Nombre de lignes à afficher (défaut: 50)")
    async def user_bot_logs_cmd(self, ctx: commands.Context, bot_name: str, lines: int = 50):
        user_id = ctx.author.id
        
        log_file = os.path.join(LOGS_DIR, str(user_id), f"{bot_name}.log")
        
        if not os.path.exists(log_file):
            await ctx.send(f"❌ Aucun log trouvé pour le bot '{bot_name}'.", ephemeral=True)
            return
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                
                content = "".join(last_lines)
                
                if len(content) > 1900:
                    content = "..." + content[-1900:]
                
                await ctx.send(f"**📋 Logs de '{bot_name}' ({len(last_lines)} dernières lignes):**\n```\n{content}\n```", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Erreur lecture logs: {e}", ephemeral=True)
    
    @commands.hybrid_command(name="stats", description="[ADMIN] Voir les statistiques du serveur")
    async def stats_cmd(self, ctx: commands.Context):
        if not is_admin_check(ctx):
            await ctx.send("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
            return
        
        all_users = await get_all_users()
        active_bot_count = 0 # Changed from len(active_processes)
        
        # The original total_bots calculation is removed as per the instruction's snippet
        # total_bots = 0
        # for user_data in all_users:
        #     user_bots = await get_user_bots(user_data['user_id'])
        #     total_bots += len(user_bots)
        
        stats_msg = f"📊 **Statistiques du Bot Manager**\n\n" # Kept the extra newline for consistency with original
        stats_msg += f"👥 **Utilisateurs enregistrés:** {len(all_users)}\n"
        # stats_msg += f"🤖 **Bots totaux créés:** {total_bots}\n" # Removed as per instruction's snippet
        stats_msg += f"🟢 **Bots actuellement actifs:** {active_bot_count}\n"
        stats_msg += f"⚙️ **Latence:** {round(self.bot.latency * 1000)}ms\n"
        
        await ctx.send(stats_msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Phase2Commands(bot))
