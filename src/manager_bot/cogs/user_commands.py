import discord
from discord.ext import commands
import discord
from discord.ext import commands
from discord import app_commands
import os
import shutil
import time
import asyncio

from ..config import users_folder, admin_scripts_folder
from ..validators import (
    validate_bot_name,
    validate_discord_token,
    validate_script_name
)
from ..script_validator import validate_script
from ..database import (
    validate_secret,
    consume_secret,
    register_user,
    get_user,
    renew_user_account,
    get_user_allowed_scripts,
    get_user_bots,
    get_bot,
    add_bot_to_db,
    update_bot_status,
    update_bot_token,
    delete_bot
)
from ..encryption import encrypt_token
from ..bot_process import start_bot_process, stop_bot_process, get_bot_status
from ..utils import (
    get_user_cached,
    get_bot_cached,
    check_mark,
    fail_emoji,
    _start_cooldowns,
    _START_COOLDOWN_SECONDS,
    is_valid_bot_name,
    _user_cache,
    _bot_cache
)

class commands_for_users(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_scripts(self, user_id):
        basic_folder = os.path.join(admin_scripts_folder, "basic")
        scripts = []
        
        if os.path.exists(basic_folder):
            for f in os.listdir(basic_folder):
                if f.endswith('.py'):
                    scripts.append({"name": f, "path": os.path.join(basic_folder, f), "type": "basic"})
        
        user = await get_user(user_id)
        is_vip = user and user['is_vip'] == 1
        allowed = await get_user_allowed_scripts(user_id)
        
        premium_folder = os.path.join(admin_scripts_folder, "premium")
        if os.path.exists(premium_folder):
            for f in os.listdir(premium_folder):
                if f.endswith('.py'):
                    if is_vip or f in allowed:
                        scripts.append({"name": f, "path": os.path.join(premium_folder, f), "type": "premium"})
        
        return scripts

    @commands.hybrid_command(name="register", description="register with secret")
    async def register_cmd(self, ctx, secret_id: str):
        secret, err = await validate_secret(secret_id)
        if err:
            await ctx.send(f"Error: {err}")
            return
        
        if secret["user_id"] != ctx.author.id:
            await ctx.send("Not your secret")
            return

        if await get_user(ctx.author.id):
            await ctx.send("Already registered")
            return

        await register_user(secret["user_id"], secret["max_bots"])
        await consume_secret(secret_id)
        
        # make folders
        u_folder = os.path.join(users_folder, str(ctx.author.id))
        if not os.path.exists(u_folder):
            os.makedirs(u_folder)
            os.makedirs(os.path.join(u_folder, "scripts"))
            
        # copy basic scripts
        scripts = await self.get_scripts(ctx.author.id)
        for s in scripts:
            if s["type"] == "basic":
                shutil.copy(s["path"], os.path.join(u_folder, "scripts", s["name"]))

        await ctx.send("Registered!")

    @commands.hybrid_command(name="renew", description="renew account")
    async def renew_cmd(self, ctx, secret_id: str):
        secret, err = await validate_secret(secret_id)
        if err:
            await ctx.send(f"Error: {err}")
            return
            
        if secret["user_id"] != ctx.author.id:
            await ctx.send("Not your secret")
            return
            
        await renew_user_account(ctx.author.id, secret["max_bots"])
        await consume_secret(secret_id)
        await ctx.send("Renewed!")

    @commands.hybrid_command(name="add_bot", description="add a bot")
    async def add_bot_cmd(self, ctx, nom: str, token: str, script: str):
        user = await get_user(ctx.author.id)
        if not user:
            await ctx.send("Register first")
            return
            
        bots = await get_user_bots(ctx.author.id)
        if len(bots) >= user['max_bots']:
            await ctx.send("Too many bots")
            return
            
        existing = await get_bot(ctx.author.id, nom)
        if existing:
            await ctx.send("Bot name taken")
            return
            
        scripts = await self.get_scripts(ctx.author.id)
        found = False
        script_path = ""
        for s in scripts:
            if s["name"] == script:
                found = True
                script_path = s["path"]
                break
        
        if not found:
            await ctx.send("Script not allowed")
            return
            
        # copy script
        dest = os.path.join(users_folder, str(ctx.author.id), "scripts", script)
        shutil.copy(script_path, dest)
        
        enc_token = encrypt_token(token)
        await add_bot_to_db(ctx.author.id, nom, enc_token, script)
        
        await ctx.send(f"Bot {nom} added")

    @commands.hybrid_command(name="start_bot", description="start bot")
    async def start_bot_cmd(self, ctx, nom: str):
        bot = await get_bot(ctx.author.id, nom)
        if not bot:
            await ctx.send("Bot not found")
            return
            
        status = get_bot_status(ctx.author.id, nom)
        if status == "running":
            await ctx.send("Already running")
            return
            
        await ctx.defer()
        if await start_bot_process(ctx.author.id, nom, bot['bot_token'], bot['script']):
            await ctx.send("Started")
        else:
            await ctx.send("Failed to start")

    @commands.hybrid_command(name="stop_bot", description="stop bot")
    async def stop_bot_cmd(self, ctx, nom: str):
        bot = await get_bot(ctx.author.id, nom)
        if not bot:
            await ctx.send("Bot not found")
            return
            
        if stop_bot_process(ctx.author.id, nom):
            await update_bot_status(ctx.author.id, nom, "stopped")
            await ctx.send("Stopped")
        else:
            await ctx.send("Failed to stop")

    @commands.hybrid_command(name="restart_bot", description="restart bot")
    async def restart_bot_cmd(self, ctx, nom: str):
        bot = await get_bot(ctx.author.id, nom)
        if not bot:
            await ctx.send("Bot not found")
            return
            
        await ctx.defer()
        stop_bot_process(ctx.author.id, nom)
        await asyncio.sleep(1)
        
        if await start_bot_process(ctx.author.id, nom, bot['bot_token'], bot['script']):
            await ctx.send("Restarted")
        else:
            await ctx.send("Failed to restart")

    @commands.hybrid_command(name="update_token", description="update token")
    async def update_token_cmd(self, ctx, nom: str, new_token: str):
        bot = await get_bot(ctx.author.id, nom)
        if not bot:
            await ctx.send("Bot not found")
            return
            
        enc = encrypt_token(new_token)
        await update_bot_token(ctx.author.id, nom, enc)
        await ctx.send("Token updated")

    @commands.hybrid_command(name="delete_bot", description="delete bot")
    async def delete_bot_cmd(self, ctx, nom: str):
        bot = await get_bot(ctx.author.id, nom)
        if not bot:
            await ctx.send("Bot not found")
            return
            
        stop_bot_process(ctx.author.id, nom)
        await delete_bot(ctx.author.id, nom)
        await ctx.send("Deleted")

    @commands.hybrid_command(name="my_bots", description="list bots")
    async def my_bots_cmd(self, ctx):
        bots = await get_user_bots(ctx.author.id)
        if not bots:
            await ctx.send("No bots")
            return
            
        msg = "Your bots:\n"
        for b in bots:
            status = get_bot_status(ctx.author.id, b['bot_name'])
            msg += f"{b['bot_name']} - {status}\n"
            
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(commands_for_users(bot))
