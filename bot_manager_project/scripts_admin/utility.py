import discord
from discord.ext import commands
import os
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot Utilitaire connecte: {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send(f" Pong! {round(bot.latency * 1000)}ms")

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=guild.name, color=discord.Color.blue())
    embed.add_field(name="Membres", value=guild.member_count)
    embed.add_field(name="Cree le", value=guild.created_at.strftime("%d/%m/%Y"))
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=str(member), color=member.color)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Rejoint le", value=member.joined_at.strftime("%d/%m/%Y"))
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    await ctx.send(embed=embed)

bot.run(TOKEN)
