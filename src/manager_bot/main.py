import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import shutil
import re
import time
from collections import defaultdict

# Support both running as a package (relative import) and as a script (absolute import)

from .config import BOT_MANAGER_TOKEN, ADMIN_IDS, USERS_DIR, SCRIPTS_ADMIN_DIR 

from .database import (
    init_db,
    create_secret,
    validate_secret,
    consume_secret,
    register_user,
    add_bot_to_db,
    get_user_bots,
    get_bot,
    update_bot_status,
    update_bot_token,
    delete_bot,
    get_all_users,
    revoke_user,
    get_user,
    renew_user_account
)
from .encryption import encrypt_token, decrypt_token
from .bot_process import start_bot_process, stop_bot_process, get_bot_status, monitor_processes # monitor_processes est importé ici

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="&", intents=intents)

# Add simple cooldown storage with expiry (in-memory)
_start_cooldowns = defaultdict(lambda: 0)  # user_id -> last start/restart timestamp
_START_COOLDOWN_SECONDS = 30

# Simple cache for user data (TTL 60s)
_user_cache = {}  # user_id -> (data, timestamp)
_CACHE_TTL = 60

# Bot name validation regex (alphanumeric + hyphens, 1-32 chars)
_bot_name_re = re.compile(r"^[A-Za-z0-9\-]{1,32}$")

def is_valid_bot_name(name: str) -> bool:
    return bool(_bot_name_re.fullmatch(name))

async def get_user_cached(user_id: int):
    """Retrieve user data with simple TTL cache (60s)."""
    now = time.time()
    if user_id in _user_cache:
        data, timestamp = _user_cache[user_id]
        if now - timestamp < _CACHE_TTL:
            return data
    # Cache miss or expired: fetch fresh
    data = await get_user(user_id)
    _user_cache[user_id] = (data, now)
    return data

def cleanup_expired_cooldowns():
    """Remove expired cooldowns from memory (call periodically)."""
    now = time.time()
    expired = [uid for uid, ts in _start_cooldowns.items() if now - ts > _START_COOLDOWN_SECONDS * 2]
    for uid in expired:
        del _start_cooldowns[uid]

async def cleanup_expired_cache():
    """Remove expired cache entries (TTL 60s)."""
    global _user_cache
    now = time.time()
    expired = [uid for uid, (_, ts) in _user_cache.items() if now - ts > _CACHE_TTL]
    for uid in expired:
        del _user_cache[uid]

async def cleanup_expired_secrets():
    """Remove expired secrets from database."""
    from .database import delete_expired_secrets
    await delete_expired_secrets()

async def cleanup_expired_users():
    """Revoke and cleanup users with expired accounts (30 days)."""
    from .database import delete_expired_users
    await delete_expired_users()

# --- Fonctions utilitaires --- #
def is_admin_check(ctx) -> bool:
    """Check if user is admin (works for both Context and Interaction)."""
    user = ctx.author if hasattr(ctx, 'author') else ctx.user
    return user.id in ADMIN_IDS

def is_registered_check(interaction: discord.Interaction) -> bool:
    return os.path.exists(os.path.join(USERS_DIR, str(interaction.user.id)))

async def check_bot_ownership(user_id: int, bot_name: str) -> bool:
    """Verify that a user owns a specific bot."""
    bot_data = await get_bot(user_id, bot_name)
    return bot_data is not None

@bot.event
async def on_ready():
    print(f"Bot Manager connecté: {bot.user}")
    # Initialise la base de données du Manager
    await init_db() 
    print("Base de données du Manager initialisée.")
    
    try:
        # Synchronise les commandes slash avec l'API Discord
        synced = await bot.tree.sync()
        print(f"Synchronisé {len(synced)} commandes slash.")
    except Exception as e:
        print(f"Erreur lors de la synchronisation des commandes slash: {e}")

    # Lance la tâche de surveillance des processus de bot
    bot.loop.create_task(monitor_processes(bot))
    print("Tâche de surveillance des bots lancée.")
    
    # Nettoyage périodique des tâches
    async def cleanup_tasks():
        while True:
            await asyncio.sleep(300)  # 5 minutes
            cleanup_expired_cooldowns()
            await cleanup_expired_secrets()  # Secrets non utilisés après 24h
            await cleanup_expired_users()  # Accounts expirés après 30 jours (abonnement mensuel)
            await cleanup_expired_cache()  # Cache expiré (60s)
    
    bot.loop.create_task(cleanup_tasks())


# --- COMMANDES ADMIN (HYBRIDES) --- #

@commands.hybrid_command(name="create_secret", description="Créer un secret pour un nouvel utilisateur")
@app_commands.describe(target_user="L'utilisateur pour qui créer un secret", max_bots="Nombre maximum de bots")
async def create_secret_cmd(ctx: commands.Context, target_user: discord.User, max_bots: int):
    # Permission check for both slash and prefix
    if not is_admin_check(ctx):
        if not ctx.interaction:
            return  # Prefix mode: ignore silently
        await ctx.send("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return
    
    if max_bots < 1:
        await ctx.send("Le nombre de bots doit être au minimum 1.", ephemeral=True)
        return
    
    secret_id = create_secret(target_user.id, max_bots) 
    try:
        await target_user.send(f"Votre secret pour le Bot Manager : `{secret_id}`. Utilisez-le rapidement !")
        await ctx.send(f"Secret créé et envoyé à {target_user.mention}.", ephemeral=True)
    except discord.Forbidden:
        await ctx.send(f"Impossible d'envoyer un DM à {target_user.mention}. Secret créé : `{secret_id}`", ephemeral=True)


@commands.hybrid_command(name="list_users", description="Lister tous les utilisateurs")
async def list_users_cmd(ctx: commands.Context):
    if not is_admin_check(ctx):
        if not ctx.interaction:
            return
        await ctx.send("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return

    users = await get_all_users()
    if not users:
        await ctx.send("Aucun utilisateur trouvé.", ephemeral=True)
        return

    user_list = "\n".join([f"ID: {user[0]}, Max Bots: {user[1]}, Inscrit le: {user[2]}" for user in users])
    await ctx.send(f"Utilisateurs:\n{user_list}", ephemeral=True)

@commands.hybrid_command(name="revoke_user", description="Révoquer un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur à révoquer")
async def revoke_user_cmd(ctx: commands.Context, user_id: int):
    if not is_admin_check(ctx):
        if not ctx.interaction:
            return
        await ctx.send("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return

    # Verify user exists before revoking
    user = await get_user(user_id)
    if not user:
        await ctx.send(f"Utilisateur {user_id} introuvable.", ephemeral=True)
        return

    user_bots = await get_user_bots(user_id)
    for bot_data in user_bots:
        stop_bot_process(user_id, bot_data[1])
    
    await revoke_user(user_id)

    user_dir = os.path.join(USERS_DIR, str(user_id))
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)

    await ctx.send(f"Utilisateur {user_id} révoqué. Tous ses bots ont été arrêtés et supprimés.", ephemeral=True)


# --- COMMANDES UTILISATEUR (HYBRIDES) --- #

@commands.hybrid_command(name="register", description="Enregistrer un utilisateur avec un secret")
@app_commands.describe(secret_id="ID du secret")
async def register_cmd(ctx: commands.Context, secret_id: str):
    secret, error = validate_secret(secret_id)
    
    if error:
        await ctx.send(f"Erreur : {error}", ephemeral=True)
        return
    
    if secret["user_id"] != ctx.author.id:
        await ctx.send("Ce secret n'est pas valide pour votre ID utilisateur.", ephemeral=True)
        return

    if await get_user(ctx.author.id):
        await ctx.send("Vous êtes déjà enregistré.", ephemeral=True)
        return

    user_id = secret["user_id"]
    max_bots = secret["max_bots"]

    await register_user(user_id, max_bots)
    consume_secret(secret_id)

    user_dir = os.path.join(USERS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    scripts_dest_dir = os.path.join(user_dir, "scripts")
    os.makedirs(scripts_dest_dir, exist_ok=True)

    for item_name in os.listdir(SCRIPTS_ADMIN_DIR):
        src_path = os.path.join(SCRIPTS_ADMIN_DIR, item_name)
        dest_path = os.path.join(scripts_dest_dir, item_name)

        if os.path.isfile(src_path) and src_path.endswith('.py'):
            shutil.copy(src_path, scripts_dest_dir)
        elif os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)

    await ctx.send(f"Vous êtes enregistré avec succès ! Max bots : {max_bots}. Utilisez `/add_bot` pour ajouter vos bots.", ephemeral=True)

@commands.hybrid_command(name="renew", description="Renouveler votre abonnement avec un nouveau secret")
@app_commands.describe(secret_id="ID du nouveau secret")
async def renew_cmd(ctx: commands.Context, secret_id: str):
    """Renew an expired user account for another 30 days."""
    user_id = ctx.author.id
    
    secret, error = validate_secret(secret_id)
    
    if error:
        await ctx.send(f"Erreur : {error}", ephemeral=True)
        return
    
    # Verify secret is for this user
    if secret["user_id"] != user_id:
        await ctx.send("Ce secret n'est pas valide pour votre ID utilisateur.", ephemeral=True)
        return
    
    try:
        await renew_user_account(user_id, secret["max_bots"])
        consume_secret(secret_id)
        
        # Invalidate cache
        _user_cache.pop(user_id, None)
        
        await ctx.send(f"Votre abonnement a été renouvelé pour 30 jours ! Vos bots sont toujours là, utilisez `/my_bots` pour les voir.", ephemeral=True)
    except Exception as e:
        await ctx.send(f"Erreur lors du renouvellement : {e}", ephemeral=True)

@commands.hybrid_command(name="add_bot", description="Ajouter un bot")
@app_commands.describe(nom="Nom du bot", token="Token du bot", script="Script a utiliser")
@app_commands.choices(script=[
    app_commands.Choice(name="utility.py", value="utility.py")
])
async def add_bot_cmd(ctx: commands.Context, nom: str, token: str, script: str):
    if not is_valid_bot_name(nom):
        await ctx.send(
            "Nom de bot invalide. Utilisez uniquement lettres, chiffres et tirets (max 32 caractères).",
            ephemeral=True
        )
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
    
    encrypted_token = encrypt_token(token)
    await add_bot_to_db(user_id, nom, encrypted_token, script)
    _user_cache.pop(user_id, None)
    await ctx.send(f"Bot `{nom}` ajouté. Utilisez `/start_bot {nom}` pour le démarrer.", ephemeral=True)

@commands.hybrid_command(name="start_bot", description="Démarrer un de vos bots")
@app_commands.describe(nom="Nom du bot")
async def start_bot_cmd(ctx: commands.Context, nom: str):
    user_id = ctx.author.id

    if not is_valid_bot_name(nom):
        await ctx.send("Nom de bot invalide.", ephemeral=True)
        return

    now = time.time()
    last = _start_cooldowns[user_id]
    if now - last < _START_COOLDOWN_SECONDS:
        await ctx.send(f"Vous devez attendre {int(_START_COOLDOWN_SECONDS - (now - last))}s.", ephemeral=True)
        return
    _start_cooldowns[user_id] = now

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
        return
    
    current_status = get_bot_status(user_id, nom)
    if current_status == "running":
        await ctx.send(f"Le bot `{nom}` est déjà en cours d'exécution.", ephemeral=True)
        return

    try:
        start_bot_process(user_id, nom, bot_data[3], bot_data[4])
        await update_bot_status(user_id, nom, "running")
        await ctx.send(f"Bot `{nom}` démarré.", ephemeral=True)
    except Exception as e:
        await ctx.send(f"Erreur : `{e}`. Consultez `logs/{user_id}/{nom}.log`.", ephemeral=True)

@commands.hybrid_command(name="stop_bot", description="Arrêter un de vos bots")
@app_commands.describe(nom="Nom du bot")
async def stop_bot_cmd(ctx: commands.Context, nom: str):
    user_id = ctx.author.id

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
        return
    
    current_status = get_bot_status(user_id, nom)
    if current_status == "stopped":
        await ctx.send(f"Le bot `{nom}` est déjà arrêté.", ephemeral=True)
        return

    if stop_bot_process(user_id, nom):
        await update_bot_status(user_id, nom, "stopped")
        await ctx.send(f"Bot `{nom}` arrêté.", ephemeral=True)
    else:
        await ctx.send(f"Impossible d'arrêter le bot `{nom}`.", ephemeral=True)

@commands.hybrid_command(name="restart_bot", description="Redémarrer un de vos bots")
@app_commands.describe(nom="Nom du bot")
async def restart_bot_cmd(ctx: commands.Context, nom: str):
    user_id = ctx.author.id

    if not is_valid_bot_name(nom):
        await ctx.send("Nom de bot invalide.", ephemeral=True)
        return

    now = time.time()
    last = _start_cooldowns[user_id]
    if now - last < _START_COOLDOWN_SECONDS:
        await ctx.send(f"Vous devez attendre {int(_START_COOLDOWN_SECONDS - (now - last))}s.", ephemeral=True)
        return
    _start_cooldowns[user_id] = now

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    stop_bot_process(user_id, nom)
    await asyncio.sleep(1)
    try:
        start_bot_process(user_id, nom, bot_data[3], bot_data[4])
        await update_bot_status(user_id, nom, "running")
        await ctx.send(f"Bot `{nom}` redémarré.", ephemeral=True)
    except Exception as e:
        await ctx.send(f"Erreur : `{e}`. Consultez `logs/{user_id}/{nom}.log`.", ephemeral=True)

@commands.hybrid_command(name="update_token", description="Mettre à jour le token d'un de vos bots")
@app_commands.describe(nom="Nom du bot", new_token="Nouveau token")
async def update_token_cmd(ctx: commands.Context, nom: str, new_token: str):
    user_id = ctx.author.id

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
        return

    was_running = False
    current_status = get_bot_status(user_id, nom)
    if current_status == "running":
        stop_bot_process(user_id, nom)
        was_running = True
        await asyncio.sleep(1)

    encrypted_token = encrypt_token(new_token)
    await update_bot_token(user_id, nom, encrypted_token)

    if was_running:
        try:
            start_bot_process(user_id, nom, encrypted_token, bot_data[4])
            await update_bot_status(user_id, nom, "running")
            await ctx.send(f"Token mis à jour et bot redémarré.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Token mis à jour, mais erreur au redémarrage: {e}", ephemeral=True)
    else:
        await ctx.send(f"Token mis à jour.", ephemeral=True)

@commands.hybrid_command(name="delete_bot", description="Supprimer un de vos bots")
@app_commands.describe(nom="Nom du bot")
async def delete_bot_cmd(ctx: commands.Context, nom: str):
    user_id = ctx.author.id

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
        return

    if get_bot_status(user_id, nom) == "running":
        stop_bot_process(user_id, nom)
    
    await delete_bot(user_id, nom)
    await ctx.send(f"Bot `{nom}` supprimé.", ephemeral=True)

@commands.hybrid_command(name="my_bots", description="Voir vos bots")
async def my_bots_cmd(ctx: commands.Context):
    user_id = ctx.author.id
    bots_data = await get_user_bots(user_id)

    if not bots_data:
        await ctx.send("Vous n'avez pas encore de bots.", ephemeral=True)
        return

    lines = ["Vos bots:"]
    for bot_data in bots_data:
        bot_name = bot_data[2]
        status = get_bot_status(user_id, bot_name)
        if status == "running":
            status_text = "EN COURS"
        elif status == "stopped":
            status_text = "ARRÊTE"
        elif status == "crashed_permanently":
            status_text = "ARRETE (plantages repetes)"
        else:
            status_text = "ERREUR"
        lines.append(f"`{bot_name}` - Script: {bot_data[4]} - Statut: {status_text}")
    
    await ctx.send("\n".join(lines), ephemeral=True)

@commands.hybrid_command(name="bot_info", description="Infos sur un de vos bots")
@app_commands.describe(nom="Nom du bot")
async def bot_info_cmd(ctx: commands.Context, nom: str):
    user_id = ctx.author.id

    if not is_valid_bot_name(nom):
        await ctx.send("Nom de bot invalide.", ephemeral=True)
        return

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
        return

    current_status = get_bot_status(user_id, nom)
    
    await ctx.send(
        f"Infos sur `{nom}`:\n"
        f"Script: {bot_data[4]}\n"
        f"Statut: {current_status}\n"
        f"Token: (sécurisé). Utilisez `/update_token` pour le changer.\n"
        f"Logs: `logs/{user_id}/{nom}.log`",
        ephemeral=True
    )


# --- COMMANDES DE DEBUG (Admin seulement) --- #

@commands.hybrid_command(name="debug_bot_process", description="[ADMIN] Voir les processus actifs")
async def debug_bot_process_cmd(ctx: commands.Context):
    if not is_admin_check(ctx):
        if not ctx.interaction:
            return
        await ctx.send("Vous n'êtes pas autorisé.", ephemeral=True)
        return

    from .bot_process import active_processes
    process_info = "\n".join([f"Key: {k}, PID: {v.pid}, Status: {'Running' if v.poll() is None else 'Stopped'}" for k, v in active_processes.items()])
    if not process_info:
        process_info = "Aucun processus actif."
    await ctx.send(f"Processus actifs:\n{process_info}", ephemeral=True)


if __name__ == "__main__":
    # La fonction init_db est maintenant appelée dans on_ready
    # Le BOT_MANAGER_TOKEN est importé directement de config
    if not BOT_MANAGER_TOKEN or BOT_MANAGER_TOKEN == "VOTRE_TOKEN_BOT_MANAGER":
        print("ERREUR: Token du Bot Manager non configuré.")
        exit()
    bot.run(BOT_MANAGER_TOKEN)