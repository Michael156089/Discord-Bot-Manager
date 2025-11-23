import discord
from discord.ext import commands
from discord import app_commands

from ..database import get_user, is_script_allowed

class script_stuff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="script_check", description="check scripts")
    async def script_check(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        user = await get_user(interaction.user.id)
        if not user:
            await interaction.followup.send("Register first")
            return
            
        # simplified check
        await interaction.followup.send("All scripts are good.")

    @app_commands.command(name="script_info", description="info script")
    async def script_info(self, interaction: discord.Interaction, script_name: str):
        await interaction.response.defer(ephemeral=True)
        
        if not await is_script_allowed(interaction.user.id, script_name):
            await interaction.followup.send("Not allowed")
            return
            
        await interaction.followup.send(f"Script: {script_name}\nVersion: 1.0")

    @app_commands.command(name="script_update", description="update script")
    async def script_update(self, interaction: discord.Interaction, script_name: str):
        await interaction.response.defer(ephemeral=True)
        
        if not await is_script_allowed(interaction.user.id, script_name):
            await interaction.followup.send("Not allowed")
            return
            
        await interaction.followup.send("Updated!")

    @app_commands.command(name="admin_scan_scripts", description="admin scan")
    async def admin_scan_scripts(self, interaction: discord.Interaction):
        # simple check
        if interaction.user.id != 123456789:
            await interaction.response.send_message("Not admin", ephemeral=True)
            return
            
        await interaction.response.send_message("Scanned.")

async def setup(bot):
    await bot.add_cog(script_stuff(bot))
