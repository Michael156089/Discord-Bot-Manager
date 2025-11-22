import discord
from discord.ext import commands
from discord import app_commands
import os
import shutil
import time
import asyncio

from ..config import USERS_DIR, SCRIPTS_ADMIN_DIR
from ..validators import (
    validate_bot_name,
    validate_discord_token,
    validate_script_name
)
from ..script_validator import validate_script
from ..database import (
    validate_secret,
    consume_secret,
    register_user,
    get_user,
    renew_user_account,
    get_user_allowed_scripts,
    get_user_bots,
    get_bot,
    add_bot_to_db,
    update_bot_status,
    update_bot_token,
    delete_bot
)
from ..encryption import encrypt_token
from ..bot_process import start_bot_process, stop_bot_process, get_bot_status
from ..utils import (
    get_user_cached,
    get_bot_cached,
    check_mark,
    fail_emoji,
    _start_cooldowns,
    _START_COOLDOWN_SECONDS,
    is_valid_bot_name,
    _user_cache,
    _bot_cache
)

class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_available_scripts_for_user(self, user_id: int) -> list:
        basic_scripts_dir = os.path.join(SCRIPTS_ADMIN_DIR, "basic")
        basic_scripts = []
        
        if os.path.exists(basic_scripts_dir):
            basic_scripts = [f for f in os.listdir(basic_scripts_dir) if f.endswith('.py')]
        
        allowed_premium = await get_user_allowed_scripts(user_id)
        
        all_scripts = []
        
        for script in basic_scripts:
            all_scripts.append({
                "name": script,
                "display": f"[BASIC] {script}",
                "type": "basic",
                "path": os.path.join(basic_scripts_dir, script)
            })
        
        premium_scripts_dir = os.path.join(SCRIPTS_ADMIN_DIR, "premium")
        if os.path.exists(premium_scripts_dir):
            for script in allowed_premium:
                script_path = os.path.join(premium_scripts_dir, script)
                if os.path.exists(script_path):
                    all_scripts.append({
                        "name": script,
                        "display": f"[PREMIUM] {script}",
                        "type": "premium",
                        "path": script_path
                    })
        
        return all_scripts

    async def _ensure_script_exists(self, user_id: int, script_name: str) -> bool:
        user_scripts_dir = os.path.join(USERS_DIR, str(user_id), "scripts")
        user_script_path = os.path.join(user_scripts_dir, script_name)
        
        if os.path.exists(user_script_path):
            return True
            
        # Le script n'existe pas, on tente de le restaurer
        available_scripts = await self.get_available_scripts_for_user(user_id)
        script_info = next((s for s in available_scripts if s["name"] == script_name), None)
        
        if not script_info:
            return False
            
        try:
            os.makedirs(user_scripts_dir, exist_ok=True)
            shutil.copy(script_info["path"], user_script_path)
            print(f"♻️ Script '{script_name}' restauré automatiquement pour l'utilisateur {user_id}")
            return True
        except Exception as e:
            print(f"❌ Erreur lors de la restauration du script '{script_name}' pour {user_id}: {e}")
            return False

    @commands.hybrid_command(name="register", description="Enregistrer un utilisateur avec un secret")
    @app_commands.describe(secret_id="ID du secret")
    async def register_cmd(self, ctx: commands.Context, secret_id: str):
        secret, error = await validate_secret(secret_id) 
        
        if error:
            await ctx.send(f"Erreur : {error}", ephemeral=True)
            return
        
        if secret["user_id"] != ctx.author.id:
            await ctx.send(f"Ce secret n'est pas valide pour votre ID utilisateur {fail_emoji}.", ephemeral=True)
            return

        if await get_user(ctx.author.id):
            await ctx.send("Vous êtes déjà enregistré.", ephemeral=True)
            return

        user_id = secret["user_id"]
        max_bots = secret["max_bots"]

        await register_user(user_id, max_bots)
        await consume_secret(secret_id)

        user_dir = os.path.join(USERS_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        scripts_dest_dir = os.path.join(user_dir, "scripts")
        os.makedirs(scripts_dest_dir, exist_ok=True)

        basic_scripts_dir = os.path.join(SCRIPTS_ADMIN_DIR, "basic")
        if os.path.exists(basic_scripts_dir):
            for item_name in os.listdir(basic_scripts_dir):
                src_path = os.path.join(basic_scripts_dir, item_name)
                dest_path = os.path.join(scripts_dest_dir, item_name)

                if os.path.isfile(src_path) and src_path.endswith('.py'):
                    shutil.copy(src_path, scripts_dest_dir)
                elif os.path.isdir(src_path): 
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)

        await ctx.send(f"Vous êtes enregistré avec succès {check_mark}! Max bots : {max_bots}. Utilisez `/add_bot` pour ajouter vos bots.", ephemeral=True)

    @commands.hybrid_command(name="renew", description="Renouveler votre abonnement avec un nouveau secret")
    @app_commands.describe(secret_id="ID du nouveau secret")
    async def renew_cmd(self, ctx: commands.Context, secret_id: str):
        user_id = ctx.author.id
        
        secret, error = await validate_secret(secret_id) 
        
        if error:
            await ctx.send(f"Erreur : {error}", ephemeral=True)
            return
        
        if secret["user_id"] != user_id:
            await ctx.send(f"Ce secret n'est pas valide pour votre ID utilisateur {fail_emoji}.", ephemeral=True)
            return
        
        try:
            await renew_user_account(user_id, secret["max_bots"])
            await consume_secret(secret_id)

            _user_cache.pop(user_id, None)
            user_scripts_dir = os.path.join(USERS_DIR, str(user_id), "scripts")
            os.makedirs(user_scripts_dir, exist_ok=True) 

            available_scripts = await self.get_available_scripts_for_user(user_id)
            for script_info in available_scripts:
                dest_path = os.path.join(user_scripts_dir, script_info["name"])
                try:
                    shutil.copy(script_info["path"], dest_path)
                    print(f" Script '{script_info['name']}' re-copied for user {user_id} during renewal.")
                except Exception as e:
                    print(f" Error re-copying script '{script_info['name']}' for user {user_id} during renewal: {e}")
            
            await ctx.send(f"Votre abonnement a été renouvelé pour 30 jours ! Vos bots sont toujours là . Utilisez `/my_bots` pour les voir.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Erreur lors du renouvellement {fail_emoji}", ephemeral=True)

    @commands.hybrid_command(name="add_bot", description="Ajouter un bot")
    @app_commands.describe(nom="Nom du bot", token="Token du bot", script="Script a utiliser")
    async def add_bot_cmd(self, ctx: commands.Context, nom: str, token: str, script: str):
        is_valid, error_msg = validate_bot_name(nom )
        if not is_valid:
            await ctx.send(f"{error_msg} {fail_emoji}", ephemeral=True)
            return
        is_valid, error_msg = validate_discord_token(token)
        if not is_valid:
            await ctx.send(f"Token invalide: {error_msg} {fail_emoji}", ephemeral=True)
            return
        is_valid, error_msg = validate_script_name(script)
        if not is_valid:
            await ctx.send(f"Script invalide: {error_msg} {fail_emoji}", ephemeral=True)
            return

        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send("Utilisateur non enregistré. Utilisez d'abord `/register`.", ephemeral=True)
            return

        max_bots = user_data[1]
        bots = await get_user_bots(user_id)
        if len(bots) >= max_bots:
            await ctx.send(f"Vous avez déjà {len(bots)} bots. Limite atteinte ({max_bots} bots).", ephemeral=True)
            return

        existing_bot = await get_bot(user_id, nom)
        if existing_bot:
            await ctx.send(f"Un bot nommé `{nom}` existe déjà.", ephemeral=True)
            return
        
        available_scripts = await self.get_available_scripts_for_user(user_id)
        script_info = next((s for s in available_scripts if s["name"] == script), None)
        
        if not script_info:
            await ctx.send(f" Vous n'avez pas accès au script '{script}' {fail_emoji}", ephemeral=True)
            return
        
        user_scripts_dir = os.path.join(USERS_DIR, str(user_id), "scripts")
        os.makedirs(user_scripts_dir, exist_ok=True)
        
        user_script_path = os.path.join(user_scripts_dir, script)
        
        if not os.path.exists(user_script_path):
            try:
                shutil.copy(script_info["path"], user_script_path)
                print(f" Script '{script}' ({script_info['type']}) copied for user {user_id}")
            except Exception as e:
                await ctx.send(f" Erreur copie du script {fail_emoji}", ephemeral=True)
                return
        
        is_safe, issues, warnings = validate_script(user_script_path)
        if not is_safe:
            try:
                os.remove(user_script_path)
            except: pass
            
            error_details = "\n".join(issues)
            await ctx.send(f"❌ Script rejeté par la sécurité :\n{error_details}", ephemeral=True)
            return
        
        if warnings:
             print(f"⚠️ Avertissements pour le script de {nom} (user {user_id}): {warnings}")
        
        encrypted_token = encrypt_token(token)
        await add_bot_to_db(user_id, nom, encrypted_token, script)
        
        _user_cache.pop(user_id, None)
        _bot_cache.pop((user_id, nom), None)
        script_type_display = "PREMIUM" if script_info["type"] == "premium" else "BASIC"
        await ctx.send(f"Bot `{nom}` ajouté avec le script [{script_type_display}] `{script}` {check_mark}. Utilisez `/start_bot {nom}` pour le démarrer.", ephemeral=True)

    @add_bot_cmd.autocomplete('script')
    async def script_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = interaction.user.id
        available_scripts = await self.get_available_scripts_for_user(user_id)
        filtered = [s for s in available_scripts if current.lower() in s["name"].lower()]
        return [app_commands.Choice(name=s["display"], value=s["name"]) for s in filtered[:25]]

    @commands.hybrid_command(name="start_bot", description="Démarrer un de vos bots")
    @app_commands.describe(nom="Nom du bot")
    async def start_bot_cmd(self, ctx: commands.Context, nom: str):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
            return

        if not is_valid_bot_name(nom):
            await ctx.send(f"Nom de bot invalide {fail_emoji}.", ephemeral=True)
            return

        now = time.time()
        last = _start_cooldowns[user_id]
        if now - last < _START_COOLDOWN_SECONDS:
            await ctx.send(f"Vous devez attendre {int(_START_COOLDOWN_SECONDS - (now - last))}s avant de démarrer/redémarrer un bot {fail_emoji}.", ephemeral=True)
            return
        _start_cooldowns[user_id] = now

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            await ctx.send(f"Bot non trouvé ou non autorisé {fail_emoji}.", ephemeral=True)
            return
        
        current_status = get_bot_status(user_id, nom)
        if current_status == "running":
            await ctx.send(f"Le bot `{nom}` est déjà en cours d'exécution.", ephemeral=True)
            return
        if current_status == "starting":
            await ctx.send(f"Le bot `{nom}` est déjà en cours de démarrage. Veuillez patienter.", ephemeral=True)
            return

        # Vérification et restauration automatique du script
        script_name = bot_data[4]
        if not await self._ensure_script_exists(user_id, script_name):
            await ctx.send(f"❌ Impossible de démarrer le bot : le script `{script_name}` est introuvable et vous n'y avez plus accès (abonnement expiré ou script retiré).", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        try:
            if await start_bot_process(user_id, nom, bot_data[3], bot_data[4]):
                await ctx.edit_original_response(content=f"Bot `{nom}` démarré. En attente de sa connexion à Discord...") 
            else:
                await ctx.edit_original_response(content=f"Impossible de démarrer le bot `{nom}`. Vérifiez les logs pour plus de détails: `logs/{user_id}/{nom}.log`")
        except Exception as e:
            await ctx.edit_original_response(content=f"Erreur inattendue : `{e}`. Consultez `logs/{user_id}/{nom}.log`.") 

    @commands.hybrid_command(name="stop_bot", description="Arrêter un de vos bots")
    @app_commands.describe(nom="Nom du bot")
    async def stop_bot_cmd(self, ctx: commands.Context, nom: str):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
            return

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
            return
        
        current_status = get_bot_status(user_id, nom)
        if current_status == "stopped":
            await ctx.send(f"Le bot `{nom}` est déjà arrêté.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True) 

        if stop_bot_process(user_id, nom):
            await update_bot_status(user_id, nom, "stopped")
            await ctx.edit_original_response(content=f"Bot `{nom}` arrêté.") 
        else:
            await ctx.edit_original_response(content=f"Impossible d'arrêter le bot `{nom}`.") 

    @commands.hybrid_command(name="restart_bot", description="Redémarrer un de vos bots")
    @app_commands.describe(nom="Nom du bot")
    async def restart_bot_cmd(self, ctx: commands.Context, nom: str):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send(f"Vous n'êtes pas enregistré. Utilisez `/register`. {fail_emoji}", ephemeral=True)
            return

        if not is_valid_bot_name(nom):
            await ctx.send(f"Nom de bot invalide {fail_emoji}.", ephemeral=True)
            return

        now = time.time()
        last = _start_cooldowns[user_id]
        if now - last < _START_COOLDOWN_SECONDS:
            await ctx.send(f"Vous devez attendre {int(_START_COOLDOWN_SECONDS - (now - last))}s avant de démarrer/redémarrer un bot.", ephemeral=True)
            return
        _start_cooldowns[user_id] = now

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            await ctx.send(f"Bot non trouvé ou non autorisé. {fail_emoji}", ephemeral=True)
            return
            
        # Vérification et restauration automatique du script
        script_name = bot_data[4]
        if not await self._ensure_script_exists(user_id, script_name):
            await ctx.send(f"❌ Impossible de redémarrer le bot : le script `{script_name}` est introuvable et vous n'y avez plus accès.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        stop_bot_process(user_id, nom)
        await asyncio.sleep(1) 

        try:
            if await start_bot_process(user_id, nom, bot_data[3], bot_data[4]):
                await ctx.edit_original_response(content=f"Bot `{nom}` redémarré. En attente de sa connexion à Discord...") 
            else:
                await ctx.edit_original_response(content=f"Impossible de redémarrer le bot `{nom}` {fail_emoji}")
        except Exception as e:
            await ctx.edit_original_response(content=f"Erreur inattendue lors du redémarrage : `{e}`.") 

    @commands.hybrid_command(name="update_token", description="Mettre à jour le token d'un de vos bots")
    @app_commands.describe(nom="Nom du bot", new_token="Nouveau token")
    async def update_token_cmd(self, ctx: commands.Context, nom: str, new_token: str):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send(f"Vous n'êtes pas enregistré. Utilisez `/register` {fail_emoji}.", ephemeral=True)
            return

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            is_valid, error_msg = validate_discord_token(new_token)
            if not is_valid:
                await ctx.send(f"Token invalide: {error_msg} {fail_emoji}", ephemeral=True)
                return  
            await ctx.send(f"Bot non trouvé ou non autorisé {fail_emoji}.", ephemeral=True)
            return

        was_running = False
        current_status = get_bot_status(user_id, nom)
        if current_status in ["running", "starting"]:
            stop_bot_process(user_id, nom)
            was_running = True
            await asyncio.sleep(1)

        encrypted_token = encrypt_token(new_token)
        await update_bot_token(user_id, nom, encrypted_token)

        if was_running:
            try:
                if await start_bot_process(user_id, nom, encrypted_token, bot_data[4]):
                    await ctx.send(f"Token mis à jour et bot redémarré. En attente de sa connexion à Discord...", ephemeral=True)
                else:
                    await ctx.send(f"Token mis à jour, mais impossible de redémarrer le bot `{nom}` contactez lequipe de support si le probleme persiste.", ephemeral=True)
            except Exception as e:
                await ctx.send(f"Token mis à jour, mais erreur inattendue au redémarrage: {e}", ephemeral=True)
        else:
            await ctx.send(f"Token du bot `{nom}` mis à jour. {check_mark}", ephemeral=True)

    @commands.hybrid_command(name="delete_bot", description="Supprimer un de vos bots")
    @app_commands.describe(nom="Nom du bot")
    async def delete_bot_cmd(self, ctx: commands.Context, nom: str):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send(f"Vous n'êtes pas enregistré. Utilisez `/register` {fail_emoji}.", ephemeral=True)
            return

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            await ctx.send(f"Bot non trouvé ou non autorisé {fail_emoji}.", ephemeral=True)
            return

        if get_bot_status(user_id, nom) == "running":
            stop_bot_process(user_id, nom)
        
        await delete_bot(user_id, nom)
        await ctx.send(f"Bot `{nom}` supprimé. {check_mark}", ephemeral=True)

    @commands.hybrid_command(name="my_bots", description="Lister vos bots")
    async def my_bots_cmd(self, ctx: commands.Context):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send(f"Vous n'êtes pas enregistré. Utilisez `/register`. {fail_emoji}", ephemeral=True)
            return

        user_bots = await get_user_bots(user_id)
        if not user_bots:
            await ctx.send(f"Vous n'avez aucun bot enregistré. Utilisez `/add_bot`. {fail_emoji}", ephemeral=True)
            return

        lines = ["Vos bots:"]
        for bot_data in user_bots:
            bot_name = bot_data[2]
            status = get_bot_status(user_id, bot_name)
            
            if status == "starting":
                status_text = "DEMARRAGE..."
            elif status == "crashed":
                status_text = "CRASHÉ"
            else:
                status_text = status.upper()
            lines.append(f"`{bot_name}` - Script: {bot_data[4]} - Statut: {status_text}")
        now = time.time()
        last = _start_cooldowns[user_id]
        if now - last < _START_COOLDOWN_SECONDS:
            await ctx.send(f"Vous devez attendre {int(_START_COOLDOWN_SECONDS - (now - last))}s avant de démarrer/redémarrer un bot {fail_emoji}.", ephemeral=True)
            return
        _start_cooldowns[user_id] = now

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            await ctx.send(f"Bot non trouvé ou non autorisé {fail_emoji}.", ephemeral=True)
            return
        
        current_status = get_bot_status(user_id, nom)
        if current_status == "running":
            await ctx.send(f"Le bot `{nom}` est déjà en cours d'exécution.", ephemeral=True)
            return
        if current_status == "starting":
            await ctx.send(f"Le bot `{nom}` est déjà en cours de démarrage. Veuillez patienter.", ephemeral=True)
            return

        # Vérification et restauration automatique du script
        script_name = bot_data[4]
        if not await self._ensure_script_exists(user_id, script_name):
            await ctx.send(f"❌ Impossible de démarrer le bot : le script `{script_name}` est introuvable et vous n'y avez plus accès (abonnement expiré ou script retiré).", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        try:
            if await start_bot_process(user_id, nom, bot_data[3], bot_data[4]):
                await ctx.edit_original_response(content=f"Bot `{nom}` démarré. En attente de sa connexion à Discord...") 
            else:
                await ctx.edit_original_response(content=f"Impossible de démarrer le bot `{nom}`. Vérifiez les logs pour plus de détails: `logs/{user_id}/{nom}.log`")
        except Exception as e:
            await ctx.edit_original_response(content=f"Erreur inattendue : `{e}`. Consultez `logs/{user_id}/{nom}.log`.") 

    @commands.hybrid_command(name="stop_bot", description="Arrêter un de vos bots")
    @app_commands.describe(nom="Nom du bot")
    async def stop_bot_cmd(self, ctx: commands.Context, nom: str):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
            return

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
            return
        
        current_status = get_bot_status(user_id, nom)
        if current_status == "stopped":
            await ctx.send(f"Le bot `{nom}` est déjà arrêté.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True) 

        if stop_bot_process(user_id, nom):
            await update_bot_status(user_id, nom, "stopped")
            await ctx.edit_original_response(content=f"Bot `{nom}` arrêté.") 
        else:
            await ctx.edit_original_response(content=f"Impossible d'arrêter le bot `{nom}`.") 

    @commands.hybrid_command(name="restart_bot", description="Redémarrer un de vos bots")
    @app_commands.describe(nom="Nom du bot")
    async def restart_bot_cmd(self, ctx: commands.Context, nom: str):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send(f"Vous n'êtes pas enregistré. Utilisez `/register`. {fail_emoji}", ephemeral=True)
            return

        if not is_valid_bot_name(nom):
            await ctx.send(f"Nom de bot invalide {fail_emoji}.", ephemeral=True)
            return

        now = time.time()
        last = _start_cooldowns[user_id]
        if now - last < _START_COOLDOWN_SECONDS:
            await ctx.send(f"Vous devez attendre {int(_START_COOLDOWN_SECONDS - (now - last))}s avant de démarrer/redémarrer un bot.", ephemeral=True)
            return
        _start_cooldowns[user_id] = now

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            await ctx.send(f"Bot non trouvé ou non autorisé. {fail_emoji}", ephemeral=True)
            return
            
        # Vérification et restauration automatique du script
        script_name = bot_data[4]
        if not await self._ensure_script_exists(user_id, script_name):
            await ctx.send(f"❌ Impossible de redémarrer le bot : le script `{script_name}` est introuvable et vous n'y avez plus accès.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        stop_bot_process(user_id, nom)
        await asyncio.sleep(1) 

        try:
            if await start_bot_process(user_id, nom, bot_data[3], bot_data[4]):
                await ctx.edit_original_response(content=f"Bot `{nom}` redémarré. En attente de sa connexion à Discord...") 
            else:
                await ctx.edit_original_response(content=f"Impossible de redémarrer le bot `{nom}` {fail_emoji}")
        except Exception as e:
            await ctx.edit_original_response(content=f"Erreur inattendue lors du redémarrage : `{e}`.") 

    @commands.hybrid_command(name="update_token", description="Mettre à jour le token d'un de vos bots")
    @app_commands.describe(nom="Nom du bot", new_token="Nouveau token")
    async def update_token_cmd(self, ctx: commands.Context, nom: str, new_token: str):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send(f"Vous n'êtes pas enregistré. Utilisez `/register` {fail_emoji}.", ephemeral=True)
            return

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            is_valid, error_msg = validate_discord_token(new_token)
            if not is_valid:
                await ctx.send(f"Token invalide: {error_msg} {fail_emoji}", ephemeral=True)
                return  
            await ctx.send(f"Bot non trouvé ou non autorisé {fail_emoji}.", ephemeral=True)
            return

        was_running = False
        current_status = get_bot_status(user_id, nom)
        if current_status in ["running", "starting"]:
            stop_bot_process(user_id, nom)
            was_running = True
            await asyncio.sleep(1)

        encrypted_token = encrypt_token(new_token)
        await update_bot_token(user_id, nom, encrypted_token)

        if was_running:
            try:
                if await start_bot_process(user_id, nom, encrypted_token, bot_data[4]):
                    await ctx.send(f"Token mis à jour et bot redémarré. En attente de sa connexion à Discord...", ephemeral=True)
                else:
                    await ctx.send(f"Token mis à jour, mais impossible de redémarrer le bot `{nom}` contactez lequipe de support si le probleme persiste.", ephemeral=True)
            except Exception as e:
                await ctx.send(f"Token mis à jour, mais erreur inattendue au redémarrage: {e}", ephemeral=True)
        else:
            await ctx.send(f"Token du bot `{nom}` mis à jour. {check_mark}", ephemeral=True)

    @commands.hybrid_command(name="delete_bot", description="Supprimer un de vos bots")
    @app_commands.describe(nom="Nom du bot")
    async def delete_bot_cmd(self, ctx: commands.Context, nom: str):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send(f"Vous n'êtes pas enregistré. Utilisez `/register` {fail_emoji}.", ephemeral=True)
            return

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            await ctx.send(f"Bot non trouvé ou non autorisé {fail_emoji}.", ephemeral=True)
            return

        if get_bot_status(user_id, nom) == "running":
            stop_bot_process(user_id, nom)
        
        await delete_bot(user_id, nom)
        await ctx.send(f"Bot `{nom}` supprimé. {check_mark}", ephemeral=True)

    @commands.hybrid_command(name="my_bots", description="Lister vos bots")
    async def my_bots_cmd(self, ctx: commands.Context):
        user_id = ctx.author.id

        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send(f"Vous n'êtes pas enregistré. Utilisez `/register`. {fail_emoji}", ephemeral=True)
            return

        user_bots = await get_user_bots(user_id)
        if not user_bots:
            await ctx.send(f"Vous n'avez aucun bot enregistré. Utilisez `/add_bot`. {fail_emoji}", ephemeral=True)
            return

        lines = ["Vos bots:"]
        for bot_data in user_bots:
            bot_name = bot_data[2]
            status = get_bot_status(user_id, bot_name)
            
            if status == "starting":
                status_text = "DEMARRAGE..."
            elif status == "crashed":
                status_text = "CRASHÉ"
            else:
                status_text = status.upper()
            lines.append(f"`{bot_name}` - Script: {bot_data[4]} - Statut: {status_text}")
        
        await ctx.send("\n".join(lines), ephemeral=True)

    @commands.hybrid_command(name="bot_info", description="Infos sur un de vos bots")
    @app_commands.describe(nom="Nom du bot")
    async def user_bot_info_cmd(self, ctx: commands.Context, nom: str):
        user_id = ctx.author.id

        if not is_valid_bot_name(nom):
            await ctx.send(f"Nom de bot invalide {fail_emoji}.", ephemeral=True)
            return

        bot_data = await get_bot(user_id, nom)
        if not bot_data:
            await ctx.send(f"Bot non trouvé ou non autorisé {fail_emoji}.", ephemeral=True)
            return

        current_status = get_bot_status(user_id, nom)
        
        await ctx.send(
            f"Infos sur `{nom}`:\n"
            f"Script: {bot_data[4]}\n"
            f"Statut: {current_status}\n"
            f"Token: ||{bot_data[2][:10]}...||\n",
            ephemeral=True
        )

    @commands.hybrid_command(name="my_scripts", description="Voir les scripts disponibles pour vous")
    async def user_my_scripts_cmd(self, ctx: commands.Context):
        user_id = ctx.author.id
        
        user_data = await get_user_cached(user_id)
        if not user_data:
            await ctx.send(f"Vous n'êtes pas enregistré. Utilisez `/register` {fail_emoji}.", ephemeral=True)
            return
        
        available_scripts = await self.get_available_scripts_for_user(user_id)
        msg = "📜 **Vos scripts disponibles :**\n"
        for s in available_scripts:
            msg += f"- {s['display']}\n"
            
        await ctx.send(msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(UserCommands(bot))
