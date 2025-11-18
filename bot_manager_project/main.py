import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import shutil # <-- Assurez-vous que shutil est importé ici
from config import BOT_MANAGER_TOKEN, ADMIN_IDS, USERS_DIR, SCRIPTS_ADMIN_DIR # Importe BOT_MANAGER_TOKEN et ADMIN_IDS de config
from database import (
    init_db, # Importe init_db pour l'initialisation de la base de données du manager
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
    get_user 
)
from encryption import encrypt_token, decrypt_token
from bot_process import start_bot_process, stop_bot_process, get_bot_status, monitor_processes # monitor_processes est importé ici

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Fonctions utilitaires (à garder pour l'admin, si nécessaire) --- #
# Ces fonctions devraient être déplacées vers un module d'aide si elles deviennent plus complexes
# ou si d'autres commandes ont besoin d'une vérification d'admin.
def is_admin_check(interaction: discord.Interaction) -> bool:
    return interaction.user.id in ADMIN_IDS

def is_registered_check(interaction: discord.Interaction) -> bool:
    return os.path.exists(os.path.join(USERS_DIR, str(interaction.user.id)))

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


# --- COMMANDES ADMIN --- #

@bot.tree.command(name="create_secret", description="Créer un secret pour un nouvel utilisateur")
@app_commands.describe(target_user="L'utilisateur pour qui créer un secret", max_bots="Nombre maximum de bots")
async def create_secret_cmd(interaction: discord.Interaction, target_user: discord.User, max_bots: int): # Modifié de user_id: int à target_user: discord.User
    if not is_admin_check(interaction): # Vérification si l'utilisateur est admin
        await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return
    
    # Utilisez target_user.id pour obtenir l'ID de l'utilisateur sélectionné
    secret_id = create_secret(target_user.id, max_bots) 
    # Utilisez target_user directement pour envoyer le message privé
    await target_user.send(f"Votre secret pour le Bot Manager : `{secret_id}`. Utilisez-le rapidement !")
    await interaction.response.send_message(f"Secret créé et envoyé à l'utilisateur {target_user.display_name} ({target_user.id}).", ephemeral=True)


@bot.tree.command(name="list_users", description="Lister tous les utilisateurs")
async def list_users_cmd(interaction: discord.Interaction):
    if not is_admin_check(interaction): # Vérification si l'utilisateur est admin
        await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return

    users = await get_all_users()
    if not users:
        await interaction.response.send_message("Aucun utilisateur trouvé.", ephemeral=True)
        return

    user_list = "\n".join([f"ID: {user[0]}, Max Bots: {user[1]}, Inscrit le: {user[2]}" for user in users])
    await interaction.response.send_message(f"Utilisateurs:\n{user_list}", ephemeral=True)

@bot.tree.command(name="revoke_user", description="Révoquer un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur")
async def revoke_user_cmd(interaction: discord.Interaction, user_id: int):
    if not is_admin_check(interaction): # Vérification si l'utilisateur est admin
        await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return

    # Révoque l'utilisateur
    # Arrête tous les bots de l'utilisateur avant de révoquer
    user_bots = await get_user_bots(user_id)
    for bot_data in user_bots:
        stop_bot_process(user_id, bot_data[1]) # bot_data[1] est le nom du bot
    
    await revoke_user(user_id)

    # Supprime le dossier de l'utilisateur
    user_dir = os.path.join(USERS_DIR, str(user_id))
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir) # Nécessite l'import de shutil

    await interaction.response.send_message(f"Utilisateur {user_id} révoqué. Tous ses bots ont été arrêtés et supprimés.", ephemeral=True)


# --- COMMANDES UTILISATEUR --- #

@bot.tree.command(name="register", description="Enregistrer un utilisateur avec un secret")
@app_commands.describe(secret_id="ID du secret")
async def register_cmd(interaction: discord.Interaction, secret_id: str):
    secret, error = validate_secret(secret_id)
    
    if error:
        await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)
        return
    
    # Vérifie si le secret est destiné à cet utilisateur
    if secret["user_id"] != interaction.user.id:
        await interaction.response.send_message("Ce secret n'est pas valide pour votre ID utilisateur.", ephemeral=True)
        return

    # Vérifie si l'utilisateur est déjà enregistré
    if await get_user(interaction.user.id):
        await interaction.response.send_message("Vous êtes déjà enregistré.", ephemeral=True)
        return

    user_id = secret["user_id"]
    max_bots = secret["max_bots"]

    await register_user(user_id, max_bots)
    consume_secret(secret_id)

    # Crée le dossier utilisateur et copie les scripts
    user_dir = os.path.join(USERS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    scripts_dest_dir = os.path.join(user_dir, "scripts")
    os.makedirs(scripts_dest_dir, exist_ok=True)

    for script_file in os.listdir(SCRIPTS_ADMIN_DIR):
        if script_file.endswith('.py'):
            shutil.copy(os.path.join(SCRIPTS_ADMIN_DIR, script_file), scripts_dest_dir)


    await interaction.response.send_message(f"Vous êtes enregistré avec succès ! Max bots : {max_bots}. Utilisez `/add_bot` pour ajouter vos bots.", ephemeral=True)

@bot.tree.command(name="add_bot", description="Ajouter un bot")
@app_commands.describe(nom="Nom du bot", token="Token du bot", script="Script a utiliser")
@app_commands.choices(script=[
    app_commands.Choice(name="moderation.py", value="moderation.py"),
    app_commands.Choice(name="protect.py", value="protect.py"),
    app_commands.Choice(name="utility.py", value="utility.py"),
    app_commands.Choice(name="admin.py", value="admin.py") # Nouveau script Admin
])
async def add_bot_cmd(interaction: discord.Interaction, nom: str, token: str, script: app_commands.Choice[str]):
    user_id = interaction.user.id

    # Vérifie si l'utilisateur est enregistré
    user_data = await get_user(user_id)
    if not user_data:
        await interaction.response.send_message("Utilisateur non enregistré. Utilisez d'abord la commande `/register`.", ephemeral=True)
        return

    # Vérifie si l'utilisateur a atteint le nombre max de bots
    max_bots = user_data[1]
    bots = await get_user_bots(user_id)
    if len(bots) >= max_bots:
        await interaction.response.send_message(f"Vous avez déjà {len(bots)} bots. Limite atteinte ({max_bots} bots).", ephemeral=True)
        return

    # Vérifie si un bot avec ce nom existe déjà pour cet utilisateur
    existing_bot = await get_bot(user_id, nom)
    if existing_bot:
        await interaction.response.send_message(f"Un bot nommé `{nom}` existe déjà. Choisissez un nom unique.", ephemeral=True)
        return
    
    encrypted_token = encrypt_token(token) # Chiffre le token avant de l'ajouter
    await add_bot_to_db(user_id, nom, encrypted_token, script.value)
    await interaction.response.send_message(f"Bot `{nom}` ajouté avec le script `{script.name}`. Utilisez `/start_bot {nom}` pour le démarrer.", ephemeral=True)

@bot.tree.command(name="start_bot", description="Démarrer un bot")
@app_commands.describe(nom="Nom du bot")
async def start_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        return
    
    # Vérifie le statut actuel pour éviter de démarrer un bot déjà en cours
    current_status = get_bot_status(user_id, nom)
    if current_status == "running":
        await interaction.response.send_message(f"Le bot `{nom}` est déjà en cours d'exécution.", ephemeral=True)
        return

    # Démarre le processus du bot
    try:
        start_bot_process(user_id, nom, bot_data[3], bot_data[4]) # bot_data[3] est le token chiffré, bot_data[4] est le script
        # Met à jour le statut dans la base de données
        await update_bot_status(user_id, nom, "running")
        await interaction.response.send_message(f"Bot `{nom}` démarré.", ephemeral=True)
    except Exception as e:
        # Message d'erreur amélioré pour indiquer de vérifier les logs
        await interaction.response.send_message(
            f"Erreur lors du démarrage du bot `{nom}`: `{e}`. "
            f"Veuillez consulter le fichier de log `logs/{user_id}/{nom}.log` "
            "pour plus de détails sur l'erreur.", ephemeral=True
        )

@bot.tree.command(name="stop_bot", description="Arrêter un bot")
@app_commands.describe(nom="Nom du bot")
async def stop_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        return
    
    # Vérifie le statut actuel pour éviter d'arrêter un bot déjà arrêté
    current_status = get_bot_status(user_id, nom)
    if current_status == "stopped":
        await interaction.response.send_message(f"Le bot `{nom}` est déjà arrêté.", ephemeral=True)
        return

    # Arrête le processus du bot
    if stop_bot_process(user_id, nom):
        # Met à jour le statut dans la base de données
        await update_bot_status(user_id, nom, "stopped")
        await interaction.response.send_message(f"Bot `{nom}` arrêté.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Impossible d'arrêter le bot `{nom}`. Il n'était peut-être pas en cours d'exécution.", ephemeral=True)

@bot.tree.command(name="restart_bot", description="Redémarrer un bot")
@app_commands.describe(nom="Nom du bot")
async def restart_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True) # Defer la réponse car le redémarrage peut prendre un peu de temps

    # Redémarre le processus du bot
    stop_bot_process(user_id, nom)
    await asyncio.sleep(1) # Attendre un peu pour que le processus s'arrête complètement
    try:
        start_bot_process(user_id, nom, bot_data[3], bot_data[4])
        await update_bot_status(user_id, nom, "running")
        await interaction.followup.send(f"Bot `{nom}` redémarré.", ephemeral=True)
    except Exception as e:
        # Message d'erreur amélioré pour indiquer de vérifier les logs
        await interaction.followup.send(
            f"Erreur lors du redémarrage du bot `{nom}`: `{e}`. "
            f"Veuillez consulter le fichier de log `logs/{user_id}/{nom}.log` "
            "pour plus de détails sur l'erreur.", ephemeral=True
        )

@bot.tree.command(name="update_token", description="Changer le token d'un bot")
@app_commands.describe(nom="Nom du bot", new_token="Nouveau token")
async def update_token_cmd(interaction: discord.Interaction, nom: str, new_token: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        return

    # Arrête le bot s'il est en cours pour appliquer le nouveau token
    was_running = False
    current_status = get_bot_status(user_id, nom)
    if current_status == "running":
        stop_bot_process(user_id, nom)
        was_running = True
        await asyncio.sleep(1) # Attendre un peu

    encrypted_token = encrypt_token(new_token) # Chiffre le nouveau token
    await update_bot_token(user_id, nom, encrypted_token)

    if was_running:
        try:
            start_bot_process(user_id, nom, encrypted_token, bot_data[4])
            await update_bot_status(user_id, nom, "running")
            await interaction.response.send_message(f"Token du bot `{nom}` mis à jour et bot redémarré.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Token du bot `{nom}` mis à jour, mais erreur au redémarrage: {e}", ephemeral=True)
    else:
        await interaction.response.send_message(f"Token du bot `{nom}` mis à jour.", ephemeral=True)

@bot.tree.command(name="delete_bot", description="Supprimer un bot")
@app_commands.describe(nom="Nom du bot")
async def delete_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        return

    # Arrête le bot s'il est en cours
    if get_bot_status(user_id, nom) == "running":
        stop_bot_process(user_id, nom)
    
    # Supprime le bot de la base de données
    await delete_bot(user_id, nom)

    await interaction.response.send_message(f"Bot `{nom}` supprimé.", ephemeral=True)

@bot.tree.command(name="my_bots", description="Voir mes bots")
async def my_bots_cmd(interaction: discord.Interaction):
    user_id = interaction.user.id
    bots_data = await get_user_bots(user_id) # Renommé pour éviter le conflit avec 'bots' dans les boucles

    if not bots_data:
        await interaction.response.send_message("Vous n'avez pas encore de bots. Ajoutez-en avec `/add_bot`.", ephemeral=True)
        return

    lines = ["**Vos bots:**"]
    for bot_data in bots_data:
        bot_name = bot_data[2] # Le nom du bot est à l'index 2 dans le tuple bot_data
        status = get_bot_status(user_id, bot_name) # Récupère le statut en temps réel
        # Ajout d'un emoji pour le statut et clarification de 'crashed_permanently'
        if status == "running":
            emoji = "🟢"
        elif status == "stopped":
            emoji = "🔴"
        elif status == "crashed_permanently":
            emoji = "❌"
            status = "arrêté (plantages répétés)"
        else:
            emoji = "🟡" # crashed, but will retry
        lines.append(f"{emoji} `{bot_name}` - Script: {bot_data[4]} - Statut: {status}")
    
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bot.tree.command(name="bot_info", description="Infos sur un bot")
@app_commands.describe(nom="Nom du bot")
async def bot_info_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Récupère les infos du bot
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        return

    current_status = get_bot_status(user_id, nom)
    
    await interaction.response.send_message(f"Infos sur le bot `{nom}`:\n"
                                          f"Token: ||{decrypt_token(bot_data[3])}||\n" # Déchiffre pour afficher, à utiliser avec prudence
                                          f"Script: {bot_data[4]}\n"
                                          f"Statut actuel: {current_status}\n"
                                          f"Consultez les logs ici: `logs/{user_id}/{nom}.log`", ephemeral=True) # Ajout du chemin vers les logs


# --- COMMANDES DE DEBUG (Admin seulement) --- #

@bot.tree.command(name="debug_bot_process", description="[ADMIN] Debug des processus de bot")
async def debug_bot_process_cmd(interaction: discord.Interaction):
    if not is_admin_check(interaction):
        await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        return

    from bot_process import active_processes
    process_info = "\n".join([f"Key: {k}, PID: {v.pid}, Status: {'Running' if v.poll() is None else 'Stopped'}" for k, v in active_processes.items()])
    if not process_info:
        process_info = "Aucun processus de bot actif."
    await interaction.response.send_message(f"Processus actifs:\n{process_info}", ephemeral=True)


if __name__ == "__main__":
    # La fonction init_db est maintenant appelée dans on_ready
    # Le BOT_MANAGER_TOKEN est importé directement de config
    if not BOT_MANAGER_TOKEN or BOT_MANAGER_TOKEN == "VOTRE_TOKEN_BOT_MANAGER":
        print("ERREUR: Le token du Bot Manager n'est pas configuré dans config.py.")
        exit()
    bot.run(BOT_MANAGER_TOKEN)