import discord
from discord.ext import commands
from discord import app_commands
import os
import shutil
from datetime import datetime

from ..config import USERS_DIR, SCRIPTS_ADMIN_DIR
from ..database import (
    create_secret,
    get_all_users,
    revoke_user,
    get_user,
    get_user_bots,
    log_admin_action,
    grant_script_access,
    revoke_script_access,
    get_user_allowed_scripts
)
from ..bot_process import stop_bot_process
from ..utils import is_admin_check, check_mark, fail_emoji

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="create_secret", description="Créer un secret pour un nouvel utilisateur")
    @app_commands.describe(target_user="L'utilisateur pour qui créer un secret", max_bots="Nombre maximum de bots")
    async def create_secret_cmd(self, ctx: commands.Context, target_user: discord.User, max_bots: int):
        if not is_admin_check(ctx):
            await ctx.send(f"Vous n'êtes pas autorisé à utiliser cette commande. {fail_emoji}", ephemeral=True)
            return
        
        if max_bots < 1:
            await ctx.send(f"Le nombre de bots doit être au minimum 1. {fail_emoji}", ephemeral=True)
            return
        
        secret_id = await create_secret(target_user.id, max_bots)
        try:
            await target_user.send(f"Votre secret pour le Bot Manager : `{secret_id}`. Utilisez-le rapidement !")
            await ctx.send(f"Secret créé et envoyé à {target_user.mention} {check_mark}", ephemeral=True)
            await log_admin_action(ctx.author.id, "create_secret", target_user.id, f"max_bots={max_bots}, secret={secret_id}")
        except discord.Forbidden:
            await ctx.send(f"Impossible d'envoyer un DM à {target_user.mention}. Secret créé : `{secret_id}`", ephemeral=True)

    @commands.hybrid_command(name="list_users", description="Lister tous les utilisateurs")
    async def list_users_cmd(self, ctx: commands.Context):
        if not is_admin_check(ctx):
            await ctx.send(f"Vous n'êtes pas autorisé à utiliser cette commande. {fail_emoji}", ephemeral=True)
            return

        users = await get_all_users()
        if not users:
            await ctx.send(f"Aucun utilisateur trouvé. {fail_emoji}", ephemeral=True)
            return

        user_list_lines = []
        for user_data in users:
            user_id, max_bots, registered_at_ts, expires_at_ts, revoked = user_data
            
            registered_date = datetime.fromtimestamp(registered_at_ts).strftime('%Y-%m-%d %H:%M:%S')
            expires_date = datetime.fromtimestamp(expires_at_ts).strftime('%Y-%m-%d %H:%M:%S')
            
            status = "Révoqué" if revoked else "Actif"
            
            user_list_lines.append(f"ID: {user_id}, Max Bots: {max_bots}, Statut: {status}, Inscrit le: {registered_date}, Expire le: {expires_date}")
            
        await ctx.send(f"Utilisateurs:\n" + '\n'.join(user_list_lines), ephemeral=True)

    @commands.hybrid_command(name="revoke_user", description="Révoquer un utilisateur")
    @app_commands.describe(user_id="ID de l'utilisateur à révoquer")
    async def revoke_user_cmd(self, ctx: commands.Context, user_id: int):
        if not is_admin_check(ctx):
            await ctx.send(f"Vous n'êtes pas autorisé à utiliser cette commande. {fail_emoji}", ephemeral=True)
            return

        user = await get_user(user_id)
        if not user:
            await ctx.send(f"Utilisateur {user_id} introuvable. {fail_emoji}", ephemeral=True)
            return

        user_bots = await get_user_bots(user_id)
        for bot_data in user_bots:
            stop_bot_process(user_id, bot_data[1])
        
        await revoke_user(user_id)

        user_dir = os.path.join(USERS_DIR, str(user_id))
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir)

        await ctx.send(f"Utilisateur {user_id} révoqué. Tous ses bots ont été arrêtés et supprimés. {check_mark}", ephemeral=True)
        await log_admin_action(ctx.author.id, "revoke_user", user_id, "")

    @commands.hybrid_command(name="grant_script", description="[ADMIN] Accorder l'accès à un script premium")
    @app_commands.describe(target_user="L'utilisateur", script_name="Nom du script premium")
    async def grant_script_cmd(self, ctx: commands.Context, target_user: discord.User, script_name: str):
        if not is_admin_check(ctx):
            await ctx.send("Vous n'êtes pas autorisé.", ephemeral=True)
            return
        
        premium_script_path = os.path.join(SCRIPTS_ADMIN_DIR, "premium", script_name)
        if not os.path.exists(premium_script_path):
            await ctx.send(f"Le script '{script_name}' n'existe pas dans les scripts premium. {fail_emoji}", ephemeral=True)
            return
        
        await grant_script_access(target_user.id, script_name, ctx.author.id)
        user_data = await get_user(target_user.id)
        if user_data:
            user_scripts_dir = os.path.join(USERS_DIR, str(target_user.id), "scripts")
            os.makedirs(user_scripts_dir, exist_ok=True)
            
            dest_path = os.path.join(user_scripts_dir, script_name)
            shutil.copy(premium_script_path, dest_path)
        
        await ctx.send(f"Script premium '{script_name}' accordé à {target_user.mention}. {check_mark}", ephemeral=True)

    @commands.hybrid_command(name="revoke_script", description="[ADMIN] Révoquer l'accès à un script premium")
    @app_commands.describe(target_user="L'utilisateur", script_name="Nom du script premium")
    async def revoke_script_cmd(self, ctx: commands.Context, target_user: discord.User, script_name: str):
        if not is_admin_check(ctx):
            await ctx.send(f"Vous n'êtes pas autorisé {fail_emoji}.", ephemeral=True)
            return
        
        await revoke_script_access(target_user.id, script_name)
        
        user_scripts_dir = os.path.join(USERS_DIR, str(target_user.id), "scripts")
        script_path_in_user_dir = os.path.join(user_scripts_dir, script_name)
        if os.path.exists(script_path_in_user_dir):
            os.remove(script_path_in_user_dir)
            
        await ctx.send(f"Script premium '{script_name}' révoqué pour {target_user.mention} {check_mark}.", ephemeral=True)

    @commands.hybrid_command(name="list_user_scripts", description="[ADMIN] Voir les scripts d'un utilisateur")
    @app_commands.describe(target_user="L'utilisateur")
    async def list_user_scripts_cmd(self, ctx: commands.Context, target_user: discord.User):
        if not is_admin_check(ctx):
            await ctx.send("Vous n'êtes pas autorisé.", ephemeral=True)
            return
        
        allowed = await get_user_allowed_scripts(target_user.id)
        
        if not allowed:
            await ctx.send(f"{target_user.mention} n'a accès qu'aux scripts de base.", ephemeral=True)
        else:
            msg = f"**Scripts premium de {target_user.mention}:**\n"
            msg += "\n".join([f"- {script}" for script in allowed])
            await ctx.send(msg, ephemeral=True)

    @app_commands.command(name="add_vip", description="[ADMIN] Donner le statut VIP à un utilisateur")
    @app_commands.describe(user_id="ID de l'utilisateur")
    async def add_vip_cmd(self, interaction: discord.Interaction, user_id: str):
        if not is_admin_check(interaction):
            await interaction.response.send_message("❌ Réservé aux administrateurs.", ephemeral=True)
            return
            
        try:
            uid = int(user_id)
            from ..database import set_vip_status, get_user, log_admin_action
            
            user = await get_user(uid)
            if not user:
                await interaction.response.send_message(f"❌ Utilisateur {uid} introuvable.", ephemeral=True)
                return
                
            await set_vip_status(uid, True)
            await log_admin_action(interaction.user.id, "ADD_VIP", uid, "Granted VIP status")
            await interaction.response.send_message(f"✅ Utilisateur <@{uid}> est maintenant **VIP** ! 🌟", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ ID invalide.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur: {e}", ephemeral=True)

    @app_commands.command(name="remove_vip", description="[ADMIN] Retirer le statut VIP d'un utilisateur")
    @app_commands.describe(user_id="ID de l'utilisateur")
    async def remove_vip_cmd(self, interaction: discord.Interaction, user_id: str):
        if not is_admin_check(interaction):
            await interaction.response.send_message("❌ Réservé aux administrateurs.", ephemeral=True)
            return
            
        try:
            uid = int(user_id)
            from ..database import set_vip_status, get_user, log_admin_action
            
            user = await get_user(uid)
            if not user:
                await interaction.response.send_message(f"❌ Utilisateur {uid} introuvable.", ephemeral=True)
                return
                
            await set_vip_status(uid, False)
            await log_admin_action(interaction.user.id, "REMOVE_VIP", uid, "Revoked VIP status")
            await interaction.response.send_message(f"✅ Statut VIP retiré pour <@{uid}>.", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ ID invalide.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
