import discord
from discord.ext import commands, tasks
import asyncio
import time
from datetime import datetime, timedelta

from ..backup_manager import create_backup, cleanup_old_backups
from ..database import get_all_users

class ScheduledTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_backup.start()
        self.check_expirations.start()

    def cog_unload(self):
        self.daily_backup.cancel()
        self.check_expirations.cancel()

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
            user_id, _, _, expires_at_ts, revoked = user_data
            
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

async def setup(bot):
    await bot.add_cog(ScheduledTasks(bot))
