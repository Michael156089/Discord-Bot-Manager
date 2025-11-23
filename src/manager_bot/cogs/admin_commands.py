import discord
from discord.ext import commands
from discord import app_commands
import os
import shutil
from datetime import datetime

# imports
from ..config import users_folder, admin_scripts_folder
from ..database import (
    create_secret,
    get_all_users,
    revoke_user,
    get_user,
    get_user_bots,
    log_admin_action,
    grant_script_access,
    revoke_script_access,
    get_user_allowed_scripts,
    set_vip_status
)
from ..bot_process import stop_bot_process

class admin_stuff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="create_secret", description="make a secret for user")
    async def create_secret_cmd(self, ctx, target_user: discord.User, max_bots: int):
        print(f"creating secret for {target_user}")
        
        if max_bots < 1:
            await ctx.send("max bots must be 1 or more")
            return
        
        secret = await create_secret(target_user.id, max_bots)
        try:
            await target_user.send(f"Here is your secret: {secret}")
            await ctx.send(f"Secret sent to {target_user.mention}")
            await log_admin_action(ctx.author.id, "create_secret", target_user.id, f"bots={max_bots}")
        except:
            await ctx.send(f"Cant dm user. Secret: {secret}")

    @commands.hybrid_command(name="list_users", description="show all users")
    async def list_users_cmd(self, ctx):
        users = await get_all_users()
        if not users:
            await ctx.send("no users found")
            return

        msg = "Users:\n"
        for u in users:
            msg += f"ID: {u['id']}, Bots: {u['max_bots']}\n"
            
        await ctx.send(msg)

    @commands.hybrid_command(name="revoke_user", description="ban a user")
    async def revoke_user_cmd(self, ctx, user_id: int):
        user = await get_user(user_id)
        if not user:
            await ctx.send("user not found")
            return

        bots = await get_user_bots(user_id)
        for b in bots:
            stop_bot_process(user_id, b[1])
        
        await revoke_user(user_id)

        # delete folder
        folder = os.path.join(users_folder, str(user_id))
        if os.path.exists(folder):
            shutil.rmtree(folder)

        await ctx.send(f"User {user_id} revoked.")
        await log_admin_action(ctx.author.id, "revoke_user", user_id, "")

    @commands.hybrid_command(name="grant_script", description="give premium script")
    async def grant_script_cmd(self, ctx, target_user: discord.User, script_name: str):
        path = os.path.join(admin_scripts_folder, "premium", script_name)
        if not os.path.exists(path):
            await ctx.send("script not found")
            return
        
        await grant_script_access(target_user.id, script_name, ctx.author.id)
        
        # copy script
        u_folder = os.path.join(users_folder, str(target_user.id), "scripts")
        if not os.path.exists(u_folder):
            os.makedirs(u_folder)
            
        shutil.copy(path, os.path.join(u_folder, script_name))
        
        await ctx.send(f"Script {script_name} given to {target_user.mention}")

    @commands.hybrid_command(name="revoke_script", description="remove premium script")
    async def revoke_script_cmd(self, ctx, target_user: discord.User, script_name: str):
        await revoke_script_access(target_user.id, script_name)
        
        # delete file
        f = os.path.join(users_folder, str(target_user.id), "scripts", script_name)
        if os.path.exists(f):
            os.remove(f)
            
        await ctx.send(f"Script {script_name} removed from {target_user.mention}")

    @app_commands.command(name="add_vip", description="make user vip")
    async def add_vip_cmd(self, interaction: discord.Interaction, user_id: str):
        try:
            uid = int(user_id)
            await set_vip_status(uid, True)
            await log_admin_action(interaction.user.id, "ADD_VIP", uid, "vip given")
            await interaction.response.send_message(f"User {uid} is now VIP")
        except:
            await interaction.response.send_message("error")

    @app_commands.command(name="remove_vip", description="remove vip")
    async def remove_vip_cmd(self, interaction: discord.Interaction, user_id: str):
        try:
            uid = int(user_id)
            await set_vip_status(uid, False)
            await log_admin_action(interaction.user.id, "REMOVE_VIP", uid, "vip removed")
            await interaction.response.send_message(f"User {uid} is not VIP anymore")
        except:
            await interaction.response.send_message("error")

async def setup(bot):
    await bot.add_cog(admin_stuff(bot))
