import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from config import USERS_DIR, LOGS_DIR
from encryption import decrypt_token
from database import (
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

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot Manager connecté: {bot.user}")

# --- COMMANDES ADMIN --- #

@bot.tree.command(name="create_secret", description="Créer un secret pour un nouvel utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur", max_bots="Nombre maximum de bots")
async def create_secret_cmd(interaction: discord.Interaction, user_id: int, max_bots: int):
    secret_id = create_secret(user_id, max_bots)
    user = await bot.fetch_user(user_id)
    await user.send(f"Votre secret pour le Bot Manager : `{secret_id}`. Utilisez-le rapidement !")
    await interaction.response.send_message(f"Secret créé et envoyé à l'utilisateur {user_id}.")

@bot.tree.command(name="register", description="Enregistrer un utilisateur avec un secret")
@app_commands.describe(secret_id="ID du secret")
async def register_cmd(interaction: discord.Interaction, secret_id: str):
    secret, error = validate_secret(secret_id)
    if error:
        await interaction.response.send_message(f"Erreur : {error}")
        return

    user_id = secret["user_id"]
    max_bots = secret["max_bots"]

    await register_user(user_id, max_bots)
    consume_secret(secret_id)

    await interaction.response.send_message(f"Utilisateur {user_id} enregistré avec succès.")

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

    # Vérifie si l'utilisateur a atteint le nombre max de bots
    user_data = await get_user(user_id)
    if not user_data:
        await interaction.response.send_message("Utilisateur non enregistré. Utilisez d'abord la commande /register.")
        return

    max_bots = user_data[1]
    bots = await get_user_bots(user_id)
    if len(bots) >= max_bots:
        await interaction.response.send_message(f"Vous avez déjà {len(bots)} bots. Limite atteinte ({max_bots} bots).")
        return

    # Ajoute le bot à la base de données
    await add_bot_to_db(user_id, nom, token, script.value)
    await interaction.response.send_message(f"Bot `{nom}` ajouté avec le script `{script.name}`.")

@bot.tree.command(name="start_bot", description="Démarrer un bot")
@app_commands.describe(nom="Nom du bot")
async def start_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.")
        return

    # Démarre le processus du bot
    from bot_process import start_bot_process
    start_bot_process(user_id, nom, bot_data[3], bot_data[4])

    # Met à jour le statut dans la base de données
    await update_bot_status(user_id, nom, "running")

    await interaction.response.send_message(f"Bot `{nom}` démarré.")

@bot.tree.command(name="stop_bot", description="Arrêter un bot")
@app_commands.describe(nom="Nom du bot")
async def stop_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.")
        return

    # Arrête le processus du bot
    from bot_process import stop_bot_process
    stop_bot_process(user_id, nom)

    # Met à jour le statut dans la base de données
    await update_bot_status(user_id, nom, "stopped")

    await interaction.response.send_message(f"Bot `{nom}` arrêté.")

@bot.tree.command(name="restart_bot", description="Redémarrer un bot")
@app_commands.describe(nom="Nom du bot")
async def restart_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.")
        return

    # Redémarre le processus du bot
    from bot_process import stop_bot_process, start_bot_process
    stop_bot_process(user_id, nom)
    start_bot_process(user_id, nom, bot_data[3], bot_data[4])

    await interaction.response.send_message(f"Bot `{nom}` redémarré.")

@bot.tree.command(name="update_token", description="Changer le token d'un bot")
@app_commands.describe(nom="Nom du bot", new_token="Nouveau token")
async def update_token_cmd(interaction: discord.Interaction, nom: str, new_token: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.")
        return

    # Met à jour le token dans la base de données
    await update_bot_token(user_id, nom, new_token)

    await interaction.response.send_message(f"Token du bot `{nom}` mis à jour.")

@bot.tree.command(name="delete_bot", description="Supprimer un bot")
@app_commands.describe(nom="Nom du bot")
async def delete_bot_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Vérifie si le bot existe
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.")
        return

    # Supprime le bot de la base de données
    await delete_bot(user_id, nom)

    await interaction.response.send_message(f"Bot `{nom}` supprimé.")

@bot.tree.command(name="list_users", description="Lister tous les utilisateurs")
async def list_users_cmd(interaction: discord.Interaction):
    users = await get_all_users()
    if not users:
        await interaction.response.send_message("Aucun utilisateur trouvé.")
        return

    user_list = "\n".join([f"ID: {user[0]}, Max Bots: {user[1]}, Inscrit le: {user[2]}" for user in users])
    await interaction.response.send_message(f"Utilisateurs:\n{user_list}")

@bot.tree.command(name="revoke_user", description="Révoquer un utilisateur")
@app_commands.describe(user_id="ID de l'utilisateur")
async def revoke_user_cmd(interaction: discord.Interaction, user_id: int):
    # Révoque l'utilisateur
    await revoke_user(user_id)

    await interaction.response.send_message(f"Utilisateur {user_id} révoqué. Tous ses bots ont été arrêtés et supprimés.")

# --- COMMANDES UTILISATEUR --- #

@bot.tree.command(name="my_bots", description="Voir mes bots")
async def my_bots_cmd(interaction: discord.Interaction):
    user_id = interaction.user.id
    bots = await get_user_bots(user_id)

    if not bots:
        await interaction.response.send_message("Vous n'avez pas encore de bots. Ajoutez-en avec `/add_bot`.")
        return

    bot_list = "\n".join([f"Nom: {bot[2]}, Statut: {bot[5]}" for bot in bots])
    await interaction.response.send_message(f"Vos bots:\n{bot_list}")

@bot.tree.command(name="bot_info", description="Infos sur un bot")
@app_commands.describe(nom="Nom du bot")
async def bot_info_cmd(interaction: discord.Interaction, nom: str):
    user_id = interaction.user.id

    # Récupère les infos du bot
    bot_data = await get_bot(user_id, nom)
    if not bot_data:
        await interaction.response.send_message("Bot non trouvé. Vérifiez le nom et réessayez.")
        return

    await interaction.response.send_message(f"Infos sur le bot `{nom}`:\n"
                                          f"Token: ||{bot_data[3]}||\n"
                                          f"Script: {bot_data[4]}\n"
                                          f"Statut: {bot_data[5]}")

# --- COMMANDES DE DEBUG --- #

@bot.tree.command(name="debug_bot_process", description="Debug des processus de bot")
async def debug_bot_process_cmd(interaction: discord.Interaction):
    from bot_process import active_processes
    await interaction.response.send_message(f"Processus actifs: {active_processes}")

async def setup():
    # Synchronise les commandes avec l'API Discord
    await bot.tree.sync()

    # Charge les cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')

    print("Tous les cogs ont été chargés.")

if __name__ == "__main__":
    # Boucle principale
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup())
    bot.run(os.getenv("BOT_MANAGER_TOKEN"))