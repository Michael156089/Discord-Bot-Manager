import discord
from discord.ext import commands
from discord import app_commands
import json
from ..script_version_manager import (
    is_update_available,
    get_script_info,
    update_user_script,
    apply_migrations
)
from ..script_version_db import (
    get_user_script_version,
    get_users_with_deprecated_scripts,
    get_users_with_outdated_scripts
)
from ..database import get_user, is_script_allowed
from ..bot_process import stop_bot_process, start_bot_process, get_bot_status

class ScriptManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="script_check", description="Vérifier les mises à jour disponibles pour vos scripts")
    async def script_check(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        user = await get_user(interaction.user.id)
        if not user:
            return await interaction.followup.send("Vous n'êtes pas enregistré.")
        
        from ..database import get_user_allowed_scripts
        allowed_scripts = await get_user_allowed_scripts(interaction.user.id)
        
        if not allowed_scripts:
            return await interaction.followup.send("Vous n'avez accès à aucun script.")
        
        embed = discord.Embed(
            title="État de vos scripts",
            color=discord.Color.blue()
        )
        
        updates_available = []
        deprecated_scripts = []
        up_to_date = []
        
        for script_name in allowed_scripts:
            user_version_data = await get_user_script_version(interaction.user.id, script_name)
            
            if not user_version_data:
                embed.add_field(
                    name=f"{script_name}",
                    value="Non installé",
                    inline=False
                )
                continue
            
            installed_version = user_version_data[0]
            
            update_available, current_v, latest_v = await is_update_available(interaction.user.id, script_name)
            script_info = await get_script_info(script_name)
            
            if script_info and script_info['deprecated']:
                deprecated_scripts.append(script_name)
                embed.add_field(
                    name=f"⚠️ {script_name}",
                    value=f"Version: {installed_version}\n**DÉPRÉCIÉ:** {script_info['deprecation_message']}",
                    inline=False
                )
            elif update_available:
                updates_available.append(script_name)
                embed.add_field(
                    name=f"🔄 {script_name}",
                    value=f"Installé: {current_v}\nDisponible: {latest_v}\nUtilisez `/script_update {script_name}`",
                    inline=False
                )
            else:
                up_to_date.append(script_name)
                embed.add_field(
                    name=f"✅ {script_name}",
                    value=f"Version: {installed_version} (à jour)",
                    inline=False
                )
        
        summary = f"À jour: {len(up_to_date)} | Mises à jour: {len(updates_available)} | Dépréciés: {len(deprecated_scripts)}"
        embed.set_footer(text=summary)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="script_info", description="Voir les informations détaillées d'un script")
    @app_commands.describe(script_name="Nom du script")
    async def script_info(self, interaction: discord.Interaction, script_name: str):
        await interaction.response.defer(ephemeral=True)
        
        if not await is_script_allowed(interaction.user.id, script_name):
            return await interaction.followup.send("Vous n'avez pas accès à ce script.")
        
        script_info = await get_script_info(script_name)
        if not script_info:
            return await interaction.followup.send("Script introuvable.")
        
        user_version_data = await get_user_script_version(interaction.user.id, script_name)
        installed_version = user_version_data[0] if user_version_data else "Non installé"
        
        embed = discord.Embed(
            title=f"📦 {script_name}",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="Version installée", value=installed_version, inline=True)
        embed.add_field(name="Dernière version", value=script_info['version'], inline=True)
        embed.add_field(name="Schéma DB", value=f"v{script_info['db_schema_version']}", inline=True)
        
        if script_info['deprecated']:
            embed.add_field(
                name="⚠️ Statut",
                value=f"**DÉPRÉCIÉ**\n{script_info['deprecation_message']}",
                inline=False
            )
        
        if script_info['changelog']:
            changelog_text = ""
            for version, changes in sorted(script_info['changelog'].items(), reverse=True)[:3]:
                changelog_text += f"**{version}:** {changes}\n"
            
            if changelog_text:
                embed.add_field(name="Changelog récent", value=changelog_text, inline=False)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="script_update", description="Mettre à jour un script")
    @app_commands.describe(script_name="Nom du script à mettre à jour")
    async def script_update(self, interaction: discord.Interaction, script_name: str):
        await interaction.response.defer(ephemeral=True)
        
        if not await is_script_allowed(interaction.user.id, script_name):
            return await interaction.followup.send("Vous n'avez pas accès à ce script.")
        
        update_available, current_v, latest_v = await is_update_available(interaction.user.id, script_name)
        
        if not update_available:
            return await interaction.followup.send(f"{script_name} est déjà à jour (v{current_v}).")
        
        script_info = await get_script_info(script_name)
        changelog_text = script_info['changelog'].get(latest_v, "Pas de notes de version") if script_info else "N/A"
        
        embed = discord.Embed(
            title=f"Mise à jour de {script_name}",
            description=f"**{current_v}** → **{latest_v}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="Nouveautés", value=changelog_text, inline=False)
        embed.add_field(
            name="⚠️ Important",
            value="Le bot sera arrêté pendant la mise à jour.\nRéagissez avec ✅ pour confirmer (30s).",
            inline=False
        )
        
        msg = await interaction.followup.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        
        def check(reaction, user):
            return user == interaction.user and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                return await interaction.followup.send("Mise à jour annulée.")
            
            status_msg = await interaction.followup.send("Mise à jour en cours...")
            
            from ..database import get_bot
            bot_data = await get_bot(interaction.user.id, script_name)
            was_running = False
            
            if bot_data and bot_data['status'] == 'running':
                was_running = True
                stop_bot_process(interaction.user.id, script_name)
                await status_msg.edit(content="Bot arrêté. Copie des fichiers...")
            
            success, message = await update_user_script(interaction.user.id, script_name)
            
            if not success:
                await status_msg.edit(content=f"❌ Échec: {message}")
                return
            
            await status_msg.edit(content="Fichiers copiés. Application des migrations...")
            
            migration_success, migration_msg = await apply_migrations(
                interaction.user.id, script_name, current_v, latest_v
            )
            
            if not migration_success:
                await status_msg.edit(content=f"⚠️ Mise à jour réussie mais migrations échouées: {migration_msg}")
                return
            
            if was_running:
                await status_msg.edit(content="Redémarrage du bot...")
                start_bot_process(interaction.user.id, script_name, bot_data['bot_token'])
            
            await status_msg.edit(content=f"✅ {script_name} mis à jour vers v{latest_v} avec succès !")
        
        except Exception as e:
            await interaction.followup.send(f"Erreur lors de la mise à jour: {str(e)}")

async def setup(bot):
    await bot.add_cog(ScriptManagement(bot))
