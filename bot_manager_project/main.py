import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import shutil
from config import BOT_MANAGER_TOKEN, ADMIN_IDS, USERS_DIR, SCRIPTS_ADMIN_DIR
from database import (
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
    get_user 
)
from encryption import encrypt_token, decrypt_token
from bot_process import start_bot_process, stop_bot_process, get_bot_status, monitor_processes

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin_check(interaction: discord.Interaction) -> bool:
    return interaction.user.id in ADMIN_IDS

def is_registered_check(interaction: discord.Interaction) -> bool:
    return os.path.exists(os.path.join(USERS_DIR, str(interaction.user.id)))

@bot.event
async def on_ready():
    print(f"[Manager] Bot Manager connecté: {bot.user}") # Ajout de print
    await init_db() 
    print("[Manager] Base de données du Manager initialisée.") # Ajout de print
    
    try:
        synced = await bot.tree.sync()
        print(f"[Manager] Synchronisé {len(synced)} commandes slash.") # Ajout de print
    except Exception as e:
        print(f"[Manager] Erreur lors de la synchronisation des commandes slash: {e}") # Ajout de print

    bot.loop.create_task(monitor_processes(bot))
    print("[Manager] Tâche de surveillance des bots lancée.") # Ajout de print


# --- COMMANDES ADMIN --- #

@bot.tree.command(name="create_secret", description="Créer un secret pour un nouvel utilisateur")
@app_commands.describe(target_user="L'utilisateur pour qui créer un secret", max_bots="Nombre maximum de bots")
async def create_secret_cmd(interaction: discord.Interaction, target_user: discord.User, max_bots: int):
    if not is_admin_check(interaction):
        await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        print(f"[Manager] ADMIN_CHECK FAILED for {interaction.user.id} on /create_secret") # Ajout de print
        return
    
    print(f"[Manager] Commande /create_secret reçue de {interaction.user.id} pour {target_user.id} avec {max_bots} bots.") # Ajout de print
    secret_id = create_secret(target_user.id, max_bots) 
    await target_user.send(f"Votre secret pour le Bot Manager : `{secret_id}`. Utilisez-le rapidement !")
    await interaction.response.send_message(f"Secret créé et envoyé à l'utilisateur {target_user.display_name} ({target_user.id}).", ephemeral=True)
    print(f"[Manager] Secret '{secret_id}' créé pour {target_user.id}.") # Ajout de print


@bot.tree.command(name="list_users", description="Lister tous les utilisateurs")
async def list_users_cmd(interaction: discord.Interaction):
    if not is_admin_check(interaction):
        await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        print(f"[Manager] ADMIN_CHECK FAILED for {interaction.user.id} on /list_users") # Ajout de print
        return

    print(f"[Manager] Commande /list_users reçue de {interaction.user.id}.") # Ajout de print
    users = await get_all_users()
    if not users:
        await interaction.response.send_message("Aucun utilisateur trouvé.", ephemeral=True)
        print("[Manager] Aucun utilisateur trouvé dans la DB.") # Ajout de print
        return

    user_list = "\n".join([f"ID: {user[0]}, Max Bots: {user[1]}, Inscrit le: {user[2]}" for user in users])
    await interaction.response.send_message(f"Utilisateurs:\n{user_list}", ephemeral=True)
    print(f"[Manager] Liste des utilisateurs envoyée à {interaction.user.id}.") # Ajout de print

@bot.tree.command(name="revoke_user", description="Révoquer un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur")
async def revoke_user_cmd(interaction: discord.Interaction, user_id: int):
    if not is_admin_check(interaction):
        await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        print(f"[Manager] ADMIN_CHECK FAILED for {interaction.user.id} on /revoke_user") # Ajout de print
        return

    print(f"[Manager] Commande /revoke_user reçue de {interaction.user.id} pour {user_id}.") # Ajout de print
    user_bots = await get_user_bots(user_id)
    if user_bots:
        print(f"[Manager] Arrêt de {len(user_bots)} bots pour l'utilisateur {user_id}...") # Ajout de print
    for bot_data in user_bots:
        print(f"[Manager] Arrêt du bot '{bot_data[2]}' ({bot_data[1]}) pour la révocation.") # Ajout de print
        stop_bot_process(user_id, bot_data[2]) # bot_data[2] est le nom du bot
    
    await revoke_user(user_id)
    print(f"[Manager] Utilisateur {user_id} révoqué de la DB.") # Ajout de print

    user_dir = os.path.join(USERS_DIR, str(user_id))
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
        print(f"[Manager] Dossier utilisateur '{user_dir}' supprimé.") # Ajout de print
    else:
        print(f"[Manager] Dossier utilisateur '{user_dir}' non trouvé, pas de suppression nécessaire.") # Ajout de print

    await interaction.response.send_message(f"Utilisateur {user_id} révoqué. Tous ses bots ont été arrêtés et supprimés.", ephemeral=True)
    print(f"[Manager] Réponse de révocation envoyée à {interaction.user.id}.") # Ajout de print


# --- COMMANDES UTILISATEUR --- #

@bot.tree.command(name="register", description="Enregistrer un utilisateur avec un secret")
@app_commands.describe(secret_id="ID du secret")
async def register_cmd(interaction: discord.Interaction, secret_id: str):
    print(f"[Manager] Commande /register reçue de {interaction.user.id} avec secret '{secret_id}'.") # Ajout de print
    secret, error = validate_secret(secret_id)
    
    if error:
        await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)
        print(f"[Manager] Erreur de validation du secret pour {interaction.user.id}: {error}") # Ajout de print
        return
    
    if secret["user_id"] != interaction.user.id:
        await interaction.response.send_message("Ce secret n'est pas valide pour votre ID utilisateur.", ephemeral=True)
        print(f"[Manager] Secret non concordant pour {interaction.user.id}. Attendu: {secret['user_id']}.") # Ajout de print
        return

    if await get_user(interaction.user.id):
        await interaction.response.send_message("Vous êtes déjà enregistré.", ephemeral=True)
        print(f"[Manager] Utilisateur {interaction.user.id} déjà enregistré.") # Ajout de print
        return

    user_id = secret["user_id"]
    max_bots = secret["max_bots"]

    await register_user(user_id, max_bots)
    consume_secret(secret_id)
    print(f"[Manager] Utilisateur {user_id} enregistré dans la DB et secret consommé.") # Ajout de print

    user_dir = os.path.join(USERS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    scripts_dest_dir = os.path.join(user_dir, "scripts")
    os.makedirs(scripts_dest_dir, exist_ok=True)
    print(f"[Manager] Création de la structure de dossiers pour l'utilisateur {user_id}: {user_dir}, {scripts_dest_dir}.") # Ajout de print

    print(f"[Manager] Copie des scripts et utilitaires de '{SCRIPTS_ADMIN_DIR}' vers '{scripts_dest_dir}'.") # Ajout de print
    for item_name in os.listdir(SCRIPTS_ADMIN_DIR):
        src_path = os.path.join(SCRIPTS_ADMIN_DIR, item_name)
        dest_path = os.path.join(scripts_dest_dir, item_name)

        if os.path.isfile(src_path) and src_path.endswith('.py'):
            shutil.copy(src_path, scripts_dest_dir)
            print(f"[Manager] Copié fichier: '{item_name}'") # Ajout de print
        elif os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            print(f"[Manager] Copié dossier: '{item_name}'") # Ajout de print
    print(f"[Manager] Copie des scripts terminée pour l'utilisateur {user_id}.") # Ajout de print


    await interaction.response.send_message(f"Vous êtes enregistré avec succès ! Max bots : {max_bots}. Utilisez `/add_bot` pour ajouter vos bots.", ephemeral=True)
    print(f"[Manager] Réponse d'enregistrement envoyée à {interaction.user.id}.") # Ajout de print

@bot.tree.command(name="add_bot", description="Ajouter un bot")
@app_commands.describe(nom="Nom du bot", token="Token du bot", script="Script a utiliser")
@app_commands.choices(script=[
    app_commands.Choice(name="moderation.py", value="moderation.py"),
    app_commands.Choice(name="protect.py", value="protect.py"),
    app_commands.Choice(name="utility.py", value="utility.py"),
    app_commands.Choice(name="admin.py", value="admin.py")
])
async def add_bot_cmd(interaction: discord.Interaction, nom: str, token: str, script: app_commands.Choice[str]):
    user_id = interaction.user.id
    print(f"[Manager] Commande /add_bot reçue de {user_id} pour nom='{nom}', script='{script.value}'.") # Ajout de print

    user_data = await get_user(user_id)
    if not user_data:
        await interaction.response.send_message("Utilisateur non enregistré. Utilisez d'abord la commande `/register`.", ephemeral=True)
        print(f"[Manager] Erreur: Utilisateur {user_id} non enregistré pour /add_bot.") # Ajout de print
        return

    max_bots = user_data[1]
    bots = await get_user_bots(user_id)
    if len(bots) >= max_bots:
        await interaction.response.send_message(f"Vous avez déjà {len(bots)} bots. Limite atteinte ({max_bots} bots).", ephemeral=True)
        print(f"[Manager] Erreur: Limite de bots atteinte ({len(bots)}/{max_bots}) pour {user_id}.") # Ajout de print
        return

    existing_bot = await get_bot(user_id, nom)
    if existing_bot:
        await interaction.response.send_message(f"Un bot nommé `{nom}` existe déjà. Choisissez un nom unique.", ephemeral=True)
        print(f"[Manager] Erreur: Bot '{nom}' existe déjà pour {user_id}.") # Ajout de print
        return
    
    encrypted_token = encrypt_token(token)
    await add_bot_to_db(user_id, nom, encrypted_token, script.value)
    await interaction.response.send_message(f"Bot `{nom}` ajouté avec le script `{script.name}`. Utilisez `/start_bot {nom}` pour le démarrer.", ephemeral=True)
    print(f"[Manager] Bot '{nom}' ajouté à la DB pour {user_id}.") # Ajout de print

@bot.tree.command(name="start_bot", description="Démarrer un bot")
@app_commands.describe(nom="Nom du bot")
async def start_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id
    print(f"[Manager] Commande /start_bot reçue de {user_id} pour nom='{nom}'.") # Ajout de print

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        print(f"[Manager] Erreur: Bot '{nom}' non trouvé pour {user_id}.") # Ajout de print
        return
    
    current_status = get_bot_status(user_id, nom)
    if current_status == "running":
        await interaction.response.send_message(f"Le bot `{nom}` est déjà en cours d'exécution.", ephemeral=True)
        print(f"[Manager] Avertissement: Bot '{nom}' déjà en cours pour {user_id}.") # Ajout de print
        return

    try:
        print(f"[Manager] Tentative de démarrage du bot '{nom}' pour {user_id}...") # Ajout de print
        start_bot_process(user_id, nom, bot_data[3], bot_data[4])
        await update_bot_status(user_id, nom, "running")
        await interaction.response.send_message(f"Bot `{nom}` démarré.", ephemeral=True)
        print(f"[Manager] Bot '{nom}' démarré avec succès pour {user_id}.") # Ajout de print
    except Exception as e:
        await interaction.response.send_message(
            f"Erreur lors du démarrage du bot `{nom}`: `{e}`. "
            f"Veuillez consulter le fichier de log `logs/{user_id}/{nom}.log` "
            "pour plus de détails sur l'erreur.", ephemeral=True
        )
        print(f"[Manager] FATAL ERROR lors du démarrage du bot '{nom}' pour {user_id}: {e}") # Ajout de print

@bot.tree.command(name="stop_bot", description="Arrêter un bot")
@app_commands.describe(nom="Nom du bot")
async def stop_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id
    print(f"[Manager] Commande /stop_bot reçue de {user_id} pour nom='{nom}'.") # Ajout de print

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        print(f"[Manager] Erreur: Bot '{nom}' non trouvé pour {user_id}.") # Ajout de print
        return
    
    current_status = get_bot_status(user_id, nom)
    if current_status == "stopped":
        await interaction.response.send_message(f"Le bot `{nom}` est déjà arrêté.", ephemeral=True)
        print(f"[Manager] Avertissement: Bot '{nom}' déjà arrêté pour {user_id}.") # Ajout de print
        return

    print(f"[Manager] Tentative d'arrêt du bot '{nom}' pour {user_id}...") # Ajout de print
    if stop_bot_process(user_id, nom):
        await update_bot_status(user_id, nom, "stopped")
        await interaction.response.send_message(f"Bot `{nom}` arrêté.", ephemeral=True)
        print(f"[Manager] Bot '{nom}' arrêté avec succès pour {user_id}.") # Ajout de print
    else:
        await interaction.response.send_message(f"Impossible d'arrêter le bot `{nom}`. Il n'était peut-être pas en cours d'exécution.", ephemeral=True)
        print(f"[Manager] Erreur: Impossible d'arrêter le bot '{nom}' pour {user_id}, non trouvé dans les processus actifs.") # Ajout de print

@bot.tree.command(name="restart_bot", description="Redémarrer un bot")
@app_commands.describe(nom="Nom du bot")
async def restart_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id
    print(f"[Manager] Commande /restart_bot reçue de {user_id} pour nom='{nom}'.") # Ajout de print

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        print(f"[Manager] Erreur: Bot '{nom}' non trouvé pour {user_id}.") # Ajout de print
        return

    await interaction.response.defer(ephemeral=True)

    print(f"[Manager] Tentative de redémarrage du bot '{nom}' pour {user_id}...") # Ajout de print
    stop_bot_process(user_id, nom)
    await asyncio.sleep(1)
    try:
        start_bot_process(user_id, nom, bot_data[3], bot_data[4])
        await update_bot_status(user_id, nom, "running")
        await interaction.followup.send(f"Bot `{nom}` redémarré.", ephemeral=True)
        print(f"[Manager] Bot '{nom}' redémarré avec succès pour {user_id}.") # Ajout de print
    except Exception as e:
        await interaction.followup.send(
            f"Erreur lors du redémarrage du bot `{nom}`: `{e}`. "
            f"Veuillez consulter le fichier de log `logs/{user_id}/{nom}.log` "
            "pour plus de détails sur l'erreur.", ephemeral=True
        )
        print(f"[Manager] FATAL ERROR lors du redémarrage du bot '{nom}' pour {user_id}: {e}") # Ajout de print


@bot.tree.command(name="update_token", description="Changer le token d'un bot")
@app_commands.describe(nom="Nom du bot", new_token="Nouveau token")
async def update_token_cmd(interaction: discord.Interaction, nom: str, new_token: str):
    user_id = interaction.user.id
    print(f"[Manager] Commande /update_token reçue de {user_id} pour nom='{nom}'.") # Ajout de print

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        print(f"[Manager] Erreur: Bot '{nom}' non trouvé pour {user_id}.") # Ajout de print
        return

    was_running = False
    current_status = get_bot_status(user_id, nom)
    if current_status == "running":
        print(f"[Manager] Bot '{nom}' était en cours, arrêt avant mise à jour du token.") # Ajout de print
        stop_bot_process(user_id, nom)
        was_running = True
        await asyncio.sleep(1)

    encrypted_token = encrypt_token(new_token)
    await update_bot_token(user_id, nom, encrypted_token)
    print(f"[Manager] Token du bot '{nom}' mis à jour dans la DB pour {user_id}.") # Ajout de print

    if was_running:
        try:
            print(f"[Manager] Redémarrage du bot '{nom}' après mise à jour du token.") # Ajout de print
            start_bot_process(user_id, nom, encrypted_token, bot_data[4])
            await update_bot_status(user_id, nom, "running")
            await interaction.response.send_message(f"Token du bot `{nom}` mis à jour et bot redémarré.", ephemeral=True)
            print(f"[Manager] Bot '{nom}' redémarré avec succès après mise à jour.") # Ajout de print
        except Exception as e:
            await interaction.response.send_message(f"Token du bot `{nom}` mis à jour, mais erreur au redémarrage: {e}", ephemeral=True)
            print(f"[Manager] FATAL ERROR lors du redémarrage du bot '{nom}' après update token: {e}") # Ajout de print
    else:
        await interaction.response.send_message(f"Token du bot `{nom}` mis à jour.", ephemeral=True)
        print(f"[Manager] Bot '{nom}' token mis à jour (non redémarré car il était arrêté).") # Ajout de print

@bot.tree.command(name="delete_bot", description="Supprimer un bot")
@app_commands.describe(nom="Nom du bot")
async def delete_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id
    print(f"[Manager] Commande /delete_bot reçue de {user_id} pour nom='{nom}'.") # Ajout de print

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        print(f"[Manager] Erreur: Bot '{nom}' non trouvé pour {user_id}.") # Ajout de print
        return

    if get_bot_status(user_id, nom) == "running":
        print(f"[Manager] Arrêt du bot '{nom}' avant suppression.") # Ajout de print
        stop_bot_process(user_id, nom)
    
    await delete_bot(user_id, nom)
    await interaction.response.send_message(f"Bot `{nom}` supprimé.", ephemeral=True)
    print(f"[Manager] Bot '{nom}' supprimé de la DB pour {user_id}.") # Ajout de print

@bot.tree.command(name="my_bots", description="Voir mes bots")
async def my_bots_cmd(interaction: discord.Interaction):
    user_id = interaction.user.id
    print(f"[Manager] Commande /my_bots reçue de {user_id}.") # Ajout de print
    bots_data = await get_user_bots(user_id)

    if not bots_data:
        await interaction.response.send_message("Vous n'avez pas encore de bots. Ajoutez-en avec `/add_bot`.", ephemeral=True)
        print(f"[Manager] Aucun bot trouvé pour {user_id}.") # Ajout de print
        return

    lines = ["**Vos bots:**"]
    for bot_data in bots_data:
        bot_name = bot_data[2]
        status = get_bot_status(user_id, bot_name)
        if status == "running":
            emoji = "🟢"
        elif status == "stopped":
            emoji = "🔴"
        elif status == "crashed_permanently":
            emoji = "❌"
            status = "arrêté (plantages répétés)"
        else:
            emoji = "🟡"
        lines.append(f"{emoji} `{bot_name}` - Script: {bot_data[4]} - Statut: {status}")
    
    await interaction.response.send_message("\n".join(lines), ephemeral=True)
    print(f"[Manager] Liste des bots envoyée à {user_id}.") # Ajout de print


@bot.tree.command(name="bot_info", description="Infos sur un bot")
@app_commands.describe(nom="Nom du bot")
async def bot_info_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id
    print(f"[Manager] Commande /bot_info reçue de {user_id} pour nom='{nom}'.") # Ajout de print

    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.", ephemeral=True)
        print(f"[Manager] Erreur: Bot '{nom}' non trouvé pour {user_id}.") # Ajout de print
        return

    current_status = get_bot_status(user_id, nom)
    
    await interaction.response.send_message(f"Infos sur le bot `{nom}`:\n"
                                          f"Token: ||{decrypt_token(bot_data[3])}||\n"
                                          f"Script: {bot_data[4]}\n"
                                          f"Statut actuel: {current_status}\n"
                                          f"Consultez les logs ici: `logs/{user_id}/{nom}.log`", ephemeral=True)
    print(f"[Manager] Infos du bot '{nom}' envoyées à {user_id}.") # Ajout de print


# --- COMMANDES DE DEBUG (Admin seulement) --- #

@bot.tree.command(name="debug_bot_process", description="[ADMIN] Debug des processus de bot")
async def debug_bot_process_cmd(interaction: discord.Interaction):
    if not is_admin_check(interaction):
        await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
        print(f"[Manager] ADMIN_CHECK FAILED for {interaction.user.id} on /debug_bot_process") # Ajout de print
        return

    print(f"[Manager] Commande /debug_bot_process reçue de {interaction.user.id}.") # Ajout de print
    from bot_process import active_processes
    process_info = "\n".join([f"Key: {k}, PID: {v['process'].pid}, Status: {'Running' if v['process'].poll() is None else 'Stopped'}, Restarts: {v['auto_restart_count']}" for k, v in active_processes.items()]) # Affiche aussi le compteur de redémarrages
    if not process_info:
        process_info = "Aucun processus de bot actif."
    await interaction.response.send_message(f"Processus actifs:\n{process_info}", ephemeral=True)
    print(f"[Manager] Infos sur les processus actifs envoyées à {interaction.user.id}.") # Ajout de print


if __name__ == "__main__":
    if not BOT_MANAGER_TOKEN or BOT_MANAGER_TOKEN == "VOTRE_TOKEN_BOT_MANAGER":
        print("ERREUR: Le token du Bot Manager n'est pas configuré dans config.py.")
        exit()
    bot.run(BOT_MANAGER_TOKEN)