import discord
from discord.ext import commands
import os
import sys

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, description="Un bot de test basique.")

class BasicTestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='hello')
    async def hello_command(self, ctx):
        """Répond avec un simple message 'Hello!'."""
        await ctx.send(f"Hello, {ctx.author.display_name}! Je suis en ligne et je fonctionne.")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Bot de test '{self.bot.user}' est connecte a Discord. Prefix: !")
        print(f"Nombre de serveurs: {len(self.bot.guilds)}")
        print("[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE")

async def main():
    async with bot:
        await bot.add_cog(BasicTestCog(bot))
        
        TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        
        if not TOKEN:
            print("ERREUR: Le token du bot n'est pas configure dans la variable d'environnement DISCORD_BOT_TOKEN.")
            sys.exit(1)
            
        await bot.start(TOKEN)

if __name__ == "__main__":
    print("Demarrage du bot de test...")
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot de test arrete.")
    except Exception as e:
        print(f"Une erreur est survenue lors du demarrage du bot de test: {e}")
