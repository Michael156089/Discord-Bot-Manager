import discord
from discord.ext import commands, tasks
import asyncio
import time
from datetime import datetime, timedelta

from ..backup_manager import create_backup, cleanup_old_backups
from ..database import get_all_users
from ..script_version_db import get_users_with_deprecated_scripts, get_users_with_outdated_scripts
from ..script_version_manager import scan_and_register_scripts

class ScheduledTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_backup.start()
        self.check_expirations.start()
        self.check_script_versions.start()

    def cog_unload(self):
        self.daily_backup.cancel()
        self.check_expirations.cancel()
        self.check_script_versions.cancel()

    @tasks.loop(hours=24)
    async def daily_backup(self):
        print("🔄 Exécution du backup quotidien...")
        await asyncio.to_thread(create_backup)
        await asyncio.to_thread(cleanup_old_backups)

    @daily_backup.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)

    @tasks.loop(hours=24)
    async def check_expirations(self):
        print("🔄 Vérification des expirations...")
        users = await get_all_users()
        now = time.time()
        three_days = 3 * 24 * 3600
        
        for user_data in users:
            # Unpack only what we need, ignore the rest (is_vip, last_crash_notification, last_expiry_notification)
            user_id = user_data['id']
            expires_at_ts = user_data['expires_at']
            revoked = user_data['revoked']
            
            if revoked:
                continue
                
            remaining = expires_at_ts - now
            
            if 0 < remaining < three_days:
                days_left = int(remaining / (24 * 3600)) + 1
                user = self.bot.get_user(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except:
                        continue
                
                if user:
                    try:
                        await user.send(f"⚠️ Attention ! Votre abonnement Bot Manager expire dans **{days_left} jours**. Pensez à le renouveler avec `/renew` pour éviter l'arrêt de vos bots.")
                    except:
                        pass

    @check_expirations.before_loop
    async def before_expiration_check(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(120)

    @tasks.loop(hours=6)
    async def check_script_versions(self):
        print("🔄 Vérification des versions de scripts...")
        
        await scan_and_register_scripts()
        
        deprecated_users = await get_users_with_deprecated_scripts()
        for user_id, script_name, version, deprecation_msg in deprecated_users:
            user = self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except:
                    continue
            
            if user:
                try:
                    await user.send(
                        f"⚠️ **Script déprécié**\n\n"
                        f"Votre script **{script_name}** (v{version}) est déprécié.\n"
                        f"**Raison:** {deprecation_msg}\n\n"
                        f"Utilisez `/script_check` pour voir les détails."
                    )
                except:
                    pass
        
        outdated_users = await get_users_with_outdated_scripts()
        for user_id, script_name, installed_version, latest_version in outdated_users:
            user = self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except:
                    continue
            
            if user:
                try:
                    await user.send(
                        f"🔔 **Mise à jour disponible**\n\n"
                        f"Une nouvelle version de **{script_name}** est disponible !\n"
                        f"Version actuelle: {installed_version}\n"
                        f"Nouvelle version: {latest_version}\n\n"
                        f"Utilisez `/script_update {script_name}` pour mettre à jour."
                    )
                except:
                    pass

    @check_script_versions.before_loop
    async def before_script_check(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(180)

async def setup(bot):
    await bot.add_cog(ScheduledTasks(bot))
