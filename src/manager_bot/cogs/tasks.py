import discord
from discord.ext import commands, tasks
import asyncio
import time

from ..database import get_all_users

class background_tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_task.start()
        self.check_expirations.start()

    def cog_unload(self):
        self.backup_task.cancel()
        self.check_expirations.cancel()

    @tasks.loop(hours=24)
    async def backup_task(self):
        print("doing backup...")
        # simplified backup
        await asyncio.sleep(1)
        print("backup done")

    @backup_task.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)

    @tasks.loop(hours=24)
    async def check_expirations(self):
        print("checking expirations...")
        users = await get_all_users()
        now = time.time()
        
        for u in users:
            if u['revoked']:
                continue
                
            left = u['expires_at'] - now
            if 0 < left < (3 * 24 * 3600):
                days = int(left / 86400) + 1
                try:
                    user = await self.bot.fetch_user(u['id'])
                    await user.send(f"Warning: Your account expires in {days} days. Use /renew")
                except:
                    pass

    @check_expirations.before_loop
    async def before_expiration_check(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(120)

async def setup(bot):
    await bot.add_cog(background_tasks(bot))
