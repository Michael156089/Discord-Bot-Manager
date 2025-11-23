import discord
from discord.ext import commands
from discord import app_commands

class help_stuff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="help me")
    async def help_cmd(self, ctx):
        embed = discord.Embed(title="Help", description="commands list", color=discord.Color.blue())
        
        gen = "/status, /ping, /help"
        embed.add_field(name="General", value=gen, inline=False)
        
        user = (
            "/register [secret]\n"
            "/renew [secret]\n"
            "/add_bot [name] [token] [script]\n"
            "/start_bot [name]\n"
            "/stop_bot [name]\n"
            "/restart_bot [name]\n"
            "/delete_bot [name]\n"
            "/my_bots\n"
            "/bot_info [name]\n"
            "/bot_logs [name]\n"
            "/update_token [name] [token]\n"
            "/my_scripts"
        )
        embed.add_field(name="User", value=user, inline=False)
        
        # simple check
        if ctx.author.id == 123456789: # Placeholder
            admin = (
                "/create_secret [user] [bots]\n"
                "/list_users\n"
                "/revoke_user [id]\n"
                "/grant_script [user] [script]\n"
                "/revoke_script [user] [script]\n"
                "/stats"
            )
            embed.add_field(name="Admin", value=admin, inline=False)
            
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(help_stuff(bot))
