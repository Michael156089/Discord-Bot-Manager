import discord
from discord.ext import commands
from discord import app_commands

from ..utils import get_user_cached
from ..database import get_user_bots
from ..bot_process import get_bot_status

class general_stuff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="status", description="show status")
    async def status_cmd(self, ctx):
        user = await get_user_cached(ctx.author.id)
        if not user:
            await ctx.send("Register first")
            return
            
        lat = round(self.bot.latency * 1000)
        msg = f"Manager Ping: {lat}ms\n"
        msg += f"Your Max Bots: {user[1]}\n"
        
        bots = await get_user_bots(ctx.author.id)
        if not bots:
            msg += "No bots."
        else:
            msg += "Your Bots:\n"
            for b in bots:
                st = get_bot_status(ctx.author.id, b[2])
                msg += f"- {b[2]}: {st}\n"
                
        await ctx.send(msg)

    @commands.hybrid_command(name="ping", description="pong")
    async def ping_cmd(self, ctx):
        lat = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! {lat}ms")

async def setup(bot):
    await bot.add_cog(general_stuff(bot))
