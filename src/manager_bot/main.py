import discord
from discord.ext import commands
import asyncio
import os

from .config import BOT_MANAGER_TOKEN
from .database import init_db, delete_expired_secrets, delete_expired_users
from .bot_process import monitor_processes, active_processes
from .resource_monitor import monitor_bot_resources
from .utils import cleanup_expired_cooldowns, cleanup_expired_cache

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class ManagerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="&", intents=intents, help_command=None)

    async def setup_hook(self):
        extensions = [
            "src.manager_bot.cogs.admin_commands",
            "src.manager_bot.cogs.user_commands",
            "src.manager_bot.cogs.general_commands",
            "src.manager_bot.cogs.phase2_commands",
            "src.manager_bot.cogs.tasks",
            "src.manager_bot.cogs.help_command"
        ]
        
        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"Extension chargée: {ext}")
            except Exception as e:
                print(f"Erreur chargement extension {ext}: {e}")
        
        await init_db()
        print("Base de données initialisée.")
        
        self.loop.create_task(monitor_processes(self))
        self.loop.create_task(monitor_bot_resources(active_processes, self))
        self.loop.create_task(self.cleanup_tasks())

    async def on_ready(self):
        print(f"Bot Manager connecté: {self.user}")
        try:
            synced = await self.tree.sync()
            print(f"Synchronisé {len(synced)} commandes slash.")
            for cmd in synced:
                print(f"  - /{cmd.name}")
        except Exception as e:
            print(f"Erreur sync commandes: {e}")

    async def cleanup_tasks(self):
        while True:
            await asyncio.sleep(300)
            cleanup_expired_cooldowns()
            await delete_expired_secrets()
            await delete_expired_users()
            await cleanup_expired_cache()

bot = ManagerBot()