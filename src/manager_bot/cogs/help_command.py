import discord
from discord.ext import commands
from discord import app_commands

from ..utils import is_admin_check

class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Affiche la liste détaillée des commandes.")
    async def help_cmd(self, ctx: commands.Context):
        is_admin = is_admin_check(ctx)
        
        embed = discord.Embed(
            title="📚 Guide des Commandes du Bot Manager",
            description="Voici la liste de toutes les commandes disponibles pour gérer vos bots Discord.",
            color=discord.Color.blue()
        )
        
        general_cmds = (
            "**/status** : Affiche l'état du système et de vos bots.\n"
            "**/ping** : Vérifie la latence du Bot Manager.\n"
            "**/help** : Affiche ce message."
        )
        embed.add_field(name="🌐 Général", value=general_cmds, inline=False)
        
        user_cmds = (
            "**/register [secret_id]** : Créer votre compte utilisateur.\n"
            "**/renew [secret_id]** : Renouveler votre abonnement.\n"
            "**/add_bot [nom] [token] [script]** : Ajouter un nouveau bot.\n"
            "**/start_bot [nom]** : Démarrer un bot.\n"
            "**/stop_bot [nom]** : Arrêter un bot.\n"
            "**/restart_bot [nom]** : Redémarrer un bot.\n"
            "**/delete_bot [nom]** : Supprimer définitivement un bot.\n"
            "**/my_bots** : Lister tous vos bots et leur état.\n"
            "**/bot_info [nom]** : Voir les détails d'un bot.\n"
            "**/bot_logs [nom]** : Voir les logs récents d'un bot.\n"
            "**/update_token [nom] [token]** : Changer le token d'un bot.\n"
            "**/my_scripts** : Voir les scripts auxquels vous avez accès."
        )
        embed.add_field(name="👤 Gestion des Bots", value=user_cmds, inline=False)
        
        if is_admin:
            admin_cmds = (
                "**/create_secret [user_id] [max_bots] [days]** : Générer une clé d'activation.\n"
                "**/list_users** : Lister tous les utilisateurs enregistrés.\n"
                "**/revoke_user [user_id]** : Révoquer l'accès d'un utilisateur.\n"
                "**/grant_script [user_id] [script]** : Donner accès à un script premium.\n"
                "**/revoke_script [user_id] [script]** : Retirer l'accès à un script.\n"
                "**/list_user_scripts [user_id]** : Voir les scripts d'un utilisateur.\n"
                "**/stats** : Voir les statistiques globales du serveur."
            )
            embed.add_field(name="🛡️ Administration", value=admin_cmds, inline=False)
            
        embed.set_footer(text="Bot Manager v2.0 - Production Ready")
        
        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))
