# Phase 2 Commands: Bot Logs and Stats
# These commands should be loaded in main.py

import discord
from discord.ext import commands
from discord import app_commands
import os

async def setup_phase2_commands(bot, LOGS_DIR, active_processes, is_admin_check, check_mark, fail_emoji):
    """Register Phase 2 commands on the bot."""
    
    @bot.hybrid_command(name="bot_logs", description="Voir les logs de l'un de vos bots")
    @app_commands.describe(bot_name="Nom du bot", lines="Nombre de lignes à afficher (défaut: 50)")
    async def bot_logs_cmd(ctx: commands.Context, bot_name: str, lines: int = 50):
        """Afficher les dernières lignes de log d'un bot."""
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
    
    @bot.hybrid_command(name="stats", description="[ADMIN] Voir les statistiques du serveur")
    async def stats_cmd(ctx: commands.Context):
        """Afficher les statistiques globales du Bot Manager."""
        if not is_admin_check(ctx):
            await ctx.send("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
            return
        
        from .database import get_all_users
        
        all_users = await get_all_users()
        active_bot_count = len(active_processes)
        
        total_bots = 0
        for user_data in all_users:
            from .database import get_user_bots
            user_bots = await get_user_bots(user_data['user_id'])
            total_bots += len(user_bots)
        
        stats_msg = f"📊 **Statistiques du Bot Manager**\n\n"
        stats_msg += f"👥 **Utilisateurs enregistrés:** {len(all_users)}\n"
        stats_msg += f"🤖 **Bots totaux créés:** {total_bots}\n"
        stats_msg += f"🟢 **Bots actuellement actifs:** {active_bot_count}\n"
        stats_msg += f"⚙️ **Latence:** {round(bot.latency * 1000)}ms\n"
        
        await ctx.send(stats_msg, ephemeral=True)
    
    print("✅ Commandes Phase 2 chargées (/bot_logs, /stats)")
