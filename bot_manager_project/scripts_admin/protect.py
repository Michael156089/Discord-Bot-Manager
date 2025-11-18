import discord
from discord.ext import commands
import os
from utils.database import init_database

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"[Bot Protection] Bot Protection connecté: {bot.user}")

@bot.event
async def on_member_join(member):
    age = (discord.utils.utcnow() - member.created_at).days
    if age < 7:
        try:
            await member.kick(reason="Compte trop recent")
            print(f"Compte recent kicke: {member}")
        except:
            pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    spam_words = ["spam", "pub", "discord.gg"]
    if any(word in message.content.lower() for word in spam_words):
        await message.delete()
        await message.channel.send(f"{message.author.mention} Spam detecte!", delete_after=3)
    
    await bot.process_commands(message)

if __name__ == "__main__":
    init_database()
    bot.run(TOKEN)
