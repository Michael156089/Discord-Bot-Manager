# Template: Music Bot
# Fonctionnalités basiques de musique (sans voice support car complexe)

import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
    
    @commands.command(name='play')
    async def play(self, ctx, *, query):
        """Ajouter une chanson à la file d'attente."""
        self.queue.append(query)
        await ctx.send(f"🎵 Ajouté à la file: **{query}**\nPosition: {len(self.queue)}")
    
    @commands.command(name='queue')
    async def show_queue(self, ctx):
        """Afficher la file d'attente."""
        if not self.queue:
            await ctx.send(f"📭 File d'attente vide.")
            return
        
        queue_list = "\n".join([f"{i+1}. {song}" for i, song in enumerate(self.queue)])
        await ctx.send(f"📋 **File d'attente:**\n{queue_list}")
    
    @commands.command(name='skip')
    async def skip(self, ctx):
        """Passer à la chanson suivante."""
        if self.queue:
            skipped = self.queue.pop(0)
            await ctx.send(f"⏭️ Chanson passée: **{skipped}**")
        else:
            await ctx.send(f"Aucune chanson à passer.")
    
    @commands.command(name='clear')
    async def clear_queue(self, ctx):
        """Vider la file d'attente."""
        self.queue.clear()
        await ctx.send(f"🗑️ File d'attente vidée.")
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"🎵 Music Bot '{self.bot.user}' connecté!")
        print("[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE")

async def main():
    async with bot:
        await bot.add_cog(MusicBot(bot))
        TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        if not TOKEN:
            print("❌ Token manquant!")
            return
        await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
