import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import shutil
import re
import time
from collections import defaultdict
import shutil

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
    renew_user_account,
    # New script management functions
    grant_script_access,
    revoke_script_access,
    get_user_allowed_scripts,
    is_script_allowed
)
from .encryption import encrypt_token, decrypt_token
from .bot_process import start_bot_process, stop_bot_process, get_bot_status, monitor_processes

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

# Simple cache for bot data (TTL 60s)
_bot_cache = {} # (user_id, bot_name) -> (data, timestamp)
_BOT_CACHE_TTL = 60

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

async def get_bot_cached(user_id: int, bot_name: str):
    """Retrieve bot data with simple TTL cache (60s)."""
    key = (user_id, bot_name)
    now = time.time()
    if key in _bot_cache:
        data, timestamp = _bot_cache[key]
        if now - timestamp < _BOT_CACHE_TTL:
            return data
    # Cache miss or expired: fetch fresh
    data = await get_bot(user_id, bot_name)
    _bot_cache[key] = (data, now)
    return data

def cleanup_expired_cooldowns():
    """Remove expired cooldowns from memory (call periodically)."""
    now = time.time()
    expired = [uid for uid, ts in _start_cooldowns.items() if now - ts > _START_COOLDOWN_SECONDS * 2]
    for uid in expired:
        del _start_cooldowns[uid]

async def cleanup_expired_cache():
    """Remove expired cache entries (TTL 60s)."""
    global _user_cache, _bot_cache
    now = time.time()
    
    # Nettoyage du cache utilisateur
    expired_users = [uid for uid, (_, ts) in _user_cache.items() if now - ts > _CACHE_TTL]
    for uid in expired_users:
        del _user_cache[uid]
        
    # Nettoyage du cache bot
    expired_bots = [key for key, (_, ts) in _bot_cache.items() if now - ts > _BOT_CACHE_TTL]
    for key in expired_bots:
        del _bot_cache[key]

async def cleanup_expired_secrets():
    """Remove expired secrets from database."""
    from .database import delete_expired_secrets
    await delete_expired_secrets()

async def cleanup_expired_users():
    """Revoke and cleanup users with expired accounts (30 days)."""
    from .database import delete_expired_users
    await delete_expired_users()

# --- Fonctions utilitaires --- #
def is_admin_check(ctx: commands.Context) -> bool: # ✅ Toujours attendre commands.Context
    """Check if user is admin (works for both Context and Interaction)."""
    # ctx.author est toujours disponible dans un commands.Context, meme si c'est une Interaction
    return ctx.author.id in ADMIN_IDS

def is_registered_check(interaction: discord.Interaction) -> bool:
    return os.path.exists(os.path.join(USERS_DIR, str(interaction.user.id)))

async def check_bot_ownership(user_id: int, bot_name: str) -> bool:
    """Verify that a user owns a specific bot."""
    bot_data = await get_bot_cached(user_id, bot_name) # Utiliser le cache
    return bot_data is not None

async def get_available_scripts_for_user(user_id: int) -> list:
    """Obtenir tous les scripts disponibles pour un utilisateur."""
    # Scripts de base (toujours disponibles)
    basic_scripts_dir = os.path.join(SCRIPTS_ADMIN_DIR, "basic")
    basic_scripts = []
    
    if os.path.exists(basic_scripts_dir):
        basic_scripts = [f for f in os.listdir(basic_scripts_dir) if f.endswith('.py')]
    
    # Scripts premium (si autorisés)
    allowed_premium = await get_user_allowed_scripts(user_id)
    
    # Combiner les deux
    all_scripts = []
    
    # Ajouter scripts de base avec préfixe
    for script in basic_scripts:
        all_scripts.append({
            "name": script,
            "display": f"[BASIC] {script}",
            "type": "basic",
            "path": os.path.join(basic_scripts_dir, script)
        })
    
    # Ajouter scripts premium autorisés
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

@bot.event
async def on_ready():
    print(f"Bot Manager connecté: {bot.user}")
    # Initialise la base de données du Manager
    await init_db() 
    print("Base de données du Manager initialisée.")
    
    # ✅ Synchronisation des commandes slash se fait ici après la connexion du bot
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synchronisé {len(synced)} commandes slash.")
        for cmd in synced:
            print(f"  - /{cmd.name}")
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation des commandes slash: {e}")

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

@bot.hybrid_command(name="status", description="Affiche le statut du Bot Manager et des bots de l'utilisateur.")
async def status_cmd(ctx: commands.Context):
    """Affiche le statut du Bot Manager et des bots de l'utilisateur."""
    user_id = ctx.author.id
    
    user_data = await get_user_cached(user_id)
    if not user_data:
        await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
        return
        
    # Vérifier l'état du Bot Manager
    latency = round(bot.latency * 1000)
    status_msg = f"**Statut du Bot Manager**\n"
    status_msg += f"Latence: {latency}ms\n"
    status_msg += f"Utilisateur enregistré: Oui (Max Bots: {user_data['max_bots']})\n"
    
    # Vérifier l'état des bots de l'utilisateur
    user_bots = await get_user_bots(user_id)
    if not user_bots:
        status_msg += "\n**Vos Bots**\nAucun bot enregistré. Utilisez `/add_bot`."
    else:
        status_msg += "\n**Vos Bots**\n"
        for bot_data in user_bots:
            bot_name = bot_data['bot_name']
            process_status = get_bot_status(user_id, bot_name)
            status_msg += f"- **{bot_name}**: {process_status}\n"
            
    await ctx.send(status_msg, ephemeral=True)

@commands.hybrid_command(name="ping", description="Verifie la latence du Bot Manager.")
async def ping_cmd(ctx: commands.Context):
    """Verifie la latence du Bot Manager."""
    latency = round(bot.latency * 1000)
    await ctx.send(f"Latence du Bot Manager: {latency}ms", ephemeral=True)


# --- COMMANDES ADMIN (HYBRIDES) --- #

@bot.hybrid_command(name="create_secret", description="Créer un secret pour un nouvel utilisateur")
@app_commands.describe(target_user="L'utilisateur pour qui créer un secret", max_bots="Nombre maximum de bots")
async def create_secret_cmd(ctx: commands.Context, target_user: discord.User, max_bots: int):
    if not is_admin_check(ctx):
        await ctx.send("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return
    
    if max_bots < 1:
        await ctx.send("Le nombre de bots doit être au minimum 1.", ephemeral=True)
        return
    
    secret_id = await create_secret(target_user.id, max_bots)
    try:
        await target_user.send(f"Votre secret pour le Bot Manager : `{secret_id}`. Utilisez-le rapidement !")
        await ctx.send(f"Secret créé et envoyé à {target_user.mention}.", ephemeral=True)
    except discord.Forbidden:
        await ctx.send(f"Impossible d'envoyer un DM à {target_user.mention}. Secret créé : `{secret_id}`", ephemeral=True)


@bot.hybrid_command(name="list_users", description="Lister tous les utilisateurs")
async def list_users_cmd(ctx: commands.Context):
    if not is_admin_check(ctx):
        await ctx.send("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return

    users = await get_all_users()
    if not users:
        await ctx.send("Aucun utilisateur trouvé.", ephemeral=True)
        return

    user_list = "\n".join([f"ID: {user[0]}, Max Bots: {user[1]}, Inscrit le: {user[2]}" for user in users])
    await ctx.send(f"Utilisateurs:\n{user_list}", ephemeral=True)

@bot.hybrid_command(name="revoke_user", description="Révoquer un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur à révoquer")
async def revoke_user_cmd(ctx: commands.Context, user_id: int):
    if not is_admin_check(ctx):
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


@bot.hybrid_command(name="grant_script", description="[ADMIN] Accorder l'accès à un script premium")
@app_commands.describe(
    target_user="L'utilisateur",
    script_name="Nom du script premium"
)
async def grant_script_cmd(ctx: commands.Context, target_user: discord.User, script_name: str):
    if not is_admin_check(ctx):
        await ctx.send("Vous n'êtes pas autorisé.", ephemeral=True)
        return
    
    # Vérifier que le script existe dans premium/
    premium_script_path = os.path.join(SCRIPTS_ADMIN_DIR, "premium", script_name)
    if not os.path.exists(premium_script_path):
        await ctx.send(f"❌ Le script '{script_name}' n'existe pas dans les scripts premium.", ephemeral=True)
        return
    
    await grant_script_access(target_user.id, script_name, ctx.author.id)
    
    # Copier le script chez l'utilisateur si déjà enregistré
    user_data = await get_user(target_user.id)
    if user_data:
        user_scripts_dir = os.path.join(USERS_DIR, str(target_user.id), "scripts")
        os.makedirs(user_scripts_dir, exist_ok=True)
        
        dest_path = os.path.join(user_scripts_dir, script_name)
        shutil.copy(premium_script_path, dest_path)
    
    await ctx.send(f"✅ Script premium '{script_name}' accordé à {target_user.mention}.", ephemeral=True)

@bot.hybrid_command(name="revoke_script", description="[ADMIN] Révoquer l'accès à un script premium")
@app_commands.describe(
    target_user="L'utilisateur",
    script_name="Nom du script premium"
)
async def revoke_script_cmd(ctx: commands.Context, target_user: discord.User, script_name: str):
    if not is_admin_check(ctx):
        await ctx.send("Vous n'êtes pas autorisé.", ephemeral=True)
        return
    
    await revoke_script_access(target_user.id, script_name)
    
    # Optional: Delete the script from the user's directory if it's a premium script
    user_scripts_dir = os.path.join(USERS_DIR, str(target_user.id), "scripts")
    script_path_in_user_dir = os.path.join(user_scripts_dir, script_name)
    if os.path.exists(script_path_in_user_dir):
        os.remove(script_path_in_user_dir)
        
    await ctx.send(f"✅ Script premium '{script_name}' révoqué pour {target_user.mention}.", ephemeral=True)

@bot.hybrid_command(name="list_user_scripts", description="[ADMIN] Voir les scripts d'un utilisateur")
@app_commands.describe(target_user="L'utilisateur")
async def list_user_scripts_cmd(ctx: commands.Context, target_user: discord.User):
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

# --- COMMANDES UTILISATEUR (HYBRIDES) --- #

@bot.hybrid_command(name="register", description="Enregistrer un utilisateur avec un secret")
@app_commands.describe(secret_id="ID du secret")
async def register_cmd(ctx: commands.Context, secret_id: str):
    secret, error = await validate_secret(secret_id) # ✅ AJOUT DE AWAIT
    
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
    await consume_secret(secret_id)

    user_dir = os.path.join(USERS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    scripts_dest_dir = os.path.join(user_dir, "scripts")
    os.makedirs(scripts_dest_dir, exist_ok=True)

    # Copy basic scripts for new user
    basic_scripts_dir = os.path.join(SCRIPTS_ADMIN_DIR, "basic")
    if os.path.exists(basic_scripts_dir):
        for item_name in os.listdir(basic_scripts_dir):
            src_path = os.path.join(basic_scripts_dir, item_name)
            dest_path = os.path.join(scripts_dest_dir, item_name)

            if os.path.isfile(src_path) and src_path.endswith('.py'):
                shutil.copy(src_path, scripts_dest_dir)
            elif os.path.isdir(src_path): # Should not happen with current basic scripts, but for robustness
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)

    await ctx.send(f"Vous êtes enregistré avec succès ! Max bots : {max_bots}. Utilisez `/add_bot` pour ajouter vos bots.", ephemeral=True)

@bot.hybrid_command(name="renew", description="Renouveler votre abonnement avec un nouveau secret")
@app_commands.describe(secret_id="ID du nouveau secret")
async def renew_cmd(ctx: commands.Context, secret_id: str):
    """Renew an expired user account for another 30 days."""
    user_id = ctx.author.id
    
    secret, error = await validate_secret(secret_id) # ✅ AJOUT DE AWAIT
    
    if error:
        await ctx.send(f"Erreur : {error}", ephemeral=True)
        return
    
    if secret["user_id"] != user_id:
        await ctx.send("Ce secret n'est pas valide pour votre ID utilisateur.", ephemeral=True)
        return
    
    try:
        await renew_user_account(user_id, secret["max_bots"])
        await consume_secret(secret_id)
        
        # Invalidate cache
        _user_cache.pop(user_id, None)
        
        await ctx.send(f"Votre abonnement a été renouvelé pour 30 jours ! Vos bots sont toujours là, utilisez `/my_bots` pour les voir.", ephemeral=True)
    except Exception as e:
        await ctx.send(f"Erreur lors du renouvellement : {e}", ephemeral=True)

@bot.hybrid_command(name="add_bot", description="Ajouter un bot")
@app_commands.describe(nom="Nom du bot", token="Token du bot", script="Script a utiliser")
# @app_commands.choices(script=[ # REMOVED: Replaced by dynamic autocomplete
#     app_commands.Choice(name="utility.py", value="utility.py"),
#     app_commands.Choice(name="basic_test_script.py", value="basic_test_script.py")
# ])
async def add_bot_cmd(ctx: commands.Context, nom: str, token: str, script: str):
    """Ajouter un bot avec copie du script si nécessaire."""
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

    max_bots = user_data[1] # user_data is a Row object, user_data[1] is max_bots
    bots = await get_user_bots(user_id)
    if len(bots) >= max_bots:
        await ctx.send(f"Vous avez déjà {len(bots)} bots. Limite atteinte ({max_bots} bots).", ephemeral=True)
        return

    existing_bot = await get_bot(user_id, nom)
    if existing_bot:
        await ctx.send(f"Un bot nommé `{nom}` existe déjà.", ephemeral=True)
        return
    
    # ✅ Vérifier l'accès au script
    available_scripts = await get_available_scripts_for_user(user_id)
    script_info = next((s for s in available_scripts if s["name"] == script), None)
    
    if not script_info:
        await ctx.send(f"❌ Vous n'avez pas accès au script '{script}'.", ephemeral=True)
        return
    
    # Copier le script depuis le bon emplacement
    user_scripts_dir = os.path.join(USERS_DIR, str(user_id), "scripts")
    os.makedirs(user_scripts_dir, exist_ok=True)
    
    user_script_path = os.path.join(user_scripts_dir, script)
    
    # Only copy if the script doesn't exist in the user's directory or is outdated (optional, simpler to just ensure it's there)
    if not os.path.exists(user_script_path):
        try:
            shutil.copy(script_info["path"], user_script_path)
            print(f"✅ Script '{script}' ({script_info['type']}) copied for user {user_id}")
        except Exception as e:
            await ctx.send(f"❌ Erreur copie du script: {e}", ephemeral=True)
            return
    
    encrypted_token = encrypt_token(token)
    await add_bot_to_db(user_id, nom, encrypted_token, script)
    
    # ✅ Invalider le cache
    _user_cache.pop(user_id, None)
    _bot_cache.pop((user_id, nom), None)
    
    script_type_display = "PREMIUM" if script_info["type"] == "premium" else "BASIC"
    await ctx.send(f"✅ Bot `{nom}` ajouté avec le script [{script_type_display}] `{script}`. Utilisez `/start_bot {nom}` pour le démarrer.", ephemeral=True)

@add_bot_cmd.autocomplete('script')
async def script_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete dynamique basé sur les scripts disponibles pour l'utilisateur."""
    user_id = interaction.user.id
    
    available_scripts = await get_available_scripts_for_user(user_id)
    
    # Filtrer selon ce que l'utilisateur tape
    filtered = [s for s in available_scripts if current.lower() in s["name"].lower()]
    
    # Retourner max 25 choix (limite Discord)
    return [
        app_commands.Choice(name=s["display"], value=s["name"])
        for s in filtered[:25]
    ]

@bot.hybrid_command(name="start_bot", description="Démarrer un de vos bots")
@app_commands.describe(nom="Nom du bot")
async def start_bot_cmd(ctx: commands.Context, nom: str):
    user_id = ctx.author.id

    user_data = await get_user_cached(user_id)
    if not user_data:
        await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
        return

    if not is_valid_bot_name(nom):
        await ctx.send("Nom de bot invalide.", ephemeral=True)
        return

    now = time.time()
    last = _start_cooldowns[user_id]
    if now - last < _START_COOLDOWN_SECONDS:
        await ctx.send(f"Vous devez attendre {int(_START_COOLDOWN_SECONDS - (now - last))}s avant de démarrer/redémarrer un bot.", ephemeral=True)
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
    # ✅ Gérer le cas "starting"
    if current_status == "starting":
        await ctx.send(f"Le bot `{nom}` est déjà en cours de démarrage. Veuillez patienter.", ephemeral=True)
        return

    try:
        if await start_bot_process(user_id, nom, bot_data[3], bot_data[4]):
            # Ne pas mettre à jour le statut DB ici, car la connexion n'est pas encore confirmée.
            # Le statut "starting" est géré par get_bot_status.
            await ctx.send(f"Bot `{nom}` démarré. En attente de sa connexion à Discord...", ephemeral=True)
        else:
            await ctx.send(
                f"Impossible de démarrer le bot `{nom}`. Vérifiez les logs pour plus de détails: `logs/{user_id}/{nom}.log`",
                ephemeral=True
            )
    except Exception as e:
        await ctx.send(f"Erreur inattendue : `{e}`. Consultez `logs/{user_id}/{nom}.log`.", ephemeral=True)

@bot.hybrid_command(name="stop_bot", description="Arrêter un de vos bots")
@app_commands.describe(nom="Nom du bot")
async def stop_bot_cmd(ctx: commands.Context, nom: str):
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

    if stop_bot_process(user_id, nom):
        await update_bot_status(user_id, nom, "stopped")
        await ctx.send(f"Bot `{nom}` arrêté.", ephemeral=True)
    else:
        await ctx.send(f"Impossible d'arrêter le bot `{nom}`.", ephemeral=True)

@bot.hybrid_command(name="restart_bot", description="Redémarrer un de vos bots")
@app_commands.describe(nom="Nom du bot")
async def restart_bot_cmd(ctx: commands.Context, nom: str):
    user_id = ctx.author.id

    user_data = await get_user_cached(user_id)
    if not user_data:
        await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
        return

    if not is_valid_bot_name(nom):
        await ctx.send("Nom de bot invalide.", ephemeral=True)
        return

    now = time.time()
    last = _start_cooldowns[user_id]
    if now - last < _START_COOLDOWN_SECONDS:
        await ctx.send(f"Vous devez attendre {int(_START_COOLDOWN_SECONDS - (now - last))}s avant de démarrer/redémarrer un bot.", ephemeral=True)
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
        if await start_bot_process(user_id, nom, bot_data[3], bot_data[4]):
            await ctx.send(f"Bot `{nom}` redémarré. En attente de sa connexion à Discord...", ephemeral=True)
        else:
            await ctx.send(
                f"Impossible de redémarrer le bot `{nom}`. Vérifiez les logs pour plus de détails: `logs/{user_id}/{nom}.log`",
                ephemeral=True
            )
    except Exception as e:
        await ctx.send(f"Erreur inattendue lors du redémarrage : `{e}`. Consultez `logs/{user_id}/{nom}.log`.", ephemeral=True)

@bot.hybrid_command(name="update_token", description="Mettre à jour le token d'un de vos bots")
@app_commands.describe(nom="Nom du bot", new_token="Nouveau token")
async def update_token_cmd(ctx: commands.Context, nom: str, new_token: str):
    user_id = ctx.author.id

    user_data = await get_user_cached(user_id)
    if not user_data:
        await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
        return

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
        return

    was_running = False
    current_status = get_bot_status(user_id, nom)
    if current_status in ["running", "starting"]: # ✅ Gérer aussi "starting"
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
                await ctx.send(
                    f"Token mis à jour, mais impossible de redémarrer le bot `{nom}`. Vérifiez les logs.",
                    ephemeral=True
                )
        except Exception as e:
            await ctx.send(f"Token mis à jour, mais erreur inattendue au redémarrage: {e}", ephemeral=True)
    else:
        await ctx.send(f"Token du bot `{nom}` mis à jour.", ephemeral=True)

@bot.hybrid_command(name="delete_bot", description="Supprimer un de vos bots")
@app_commands.describe(nom="Nom du bot")
async def delete_bot_cmd(ctx: commands.Context, nom: str):
    user_id = ctx.author.id

    user_data = await get_user_cached(user_id)
    if not user_data:
        await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
        return

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await ctx.send("Bot non trouvé ou non autorisé.", ephemeral=True)
        return

    if get_bot_status(user_id, nom) == "running":
        stop_bot_process(user_id, nom)
    
    await delete_bot(user_id, nom)
    await ctx.send(f"Bot `{nom}` supprimé.", ephemeral=True)

@bot.hybrid_command(name="my_bots", description="Lister vos bots")
async def my_bots_cmd(ctx: commands.Context):
    user_id = ctx.author.id

    user_data = await get_user_cached(user_id)
    if not user_data:
        await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
        return

    user_bots = await get_user_bots(user_id)
    if not user_bots:
        await ctx.send("Vous n'avez aucun bot enregistré. Utilisez `/add_bot`.", ephemeral=True)
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

@bot.hybrid_command(name="bot_info", description="Infos sur un de vos bots")
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


@bot.hybrid_command(name="my_scripts", description="Voir les scripts disponibles pour vous")
async def my_scripts_cmd(ctx: commands.Context):
    user_id = ctx.author.id
    
    user_data = await get_user_cached(user_id)
    if not user_data:
        await ctx.send("Vous n'êtes pas enregistré. Utilisez `/register`.", ephemeral=True)
        return
    
    available = await get_available_scripts_for_user(user_id)
    
    if not available:
        await ctx.send("Aucun script disponible.", ephemeral=True)
        return
    
    # Grouper par type
    basic = [s for s in available if s["type"] == "basic"]
    premium = [s for s in available if s["type"] == "premium"]
    
    msg = "**Vos scripts disponibles:**\n\n"
    
    if basic:
        msg += "**📦 Scripts de Base:**\n"
        msg += "\n".join([f"- `{s['name']}`" for s in basic])
        msg += "\n\n"
    
    if premium:
        msg += "**⭐ Scripts Premium:**\n"
        msg += "\n".join([f"- `{s['name']}`" for s in premium])
    
    await ctx.send(msg, ephemeral=True)

# --- COMMANDES DE DEBUG (Admin seulement) --- #

@bot.hybrid_command(name="debug_bot_process", description="[ADMIN] Voir les processus actifs")
async def debug_bot_process_cmd(ctx: commands.Context):
    if not is_admin_check(ctx):
        await ctx.send("Vous n'êtes pas autorisé.", ephemeral=True)
        return

    from .bot_process import active_processes
    process_info = "\n".join([f"Key: {k}, PID: {v.pid}, Status: {'Running' if v.poll() is None else 'Stopped'}" for k, v in active_processes.items()])
    if not process_info:
        process_info = "Aucun processus actif."
    await ctx.send(f"Processus actifs:\n{process_info}", ephemeral=True)


if __name__ == "__main__":
    if not BOT_MANAGER_TOKEN or BOT_MANAGER_TOKEN == "VOTRE_TOKEN_BOT_MANAGER":
        print("ERREUR: Token du Bot Manager non configuré.")
        exit()
    bot.run(BOT_MANAGER_TOKEN)