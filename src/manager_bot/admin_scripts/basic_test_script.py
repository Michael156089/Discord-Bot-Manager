"""
Script de test basique pour le Bot Manager.
Contient une seule commande simple pour confirmer que le bot est en ligne.
"""

import discord
from discord.ext import commands
import os
import sys

# --- BOT SETUP --- #
# Les intents par défaut sont suffisants pour ce bot simple
intents = discord.Intents.default()
intents.message_content = True # Nécessaire pour lire les messages et commandes

# Le préfixe sera '!' par défaut pour ce bot de test
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

async def main():
    async with bot:
        # Ajoute le cog de test au bot
        await bot.add_cog(BasicTestCog(bot))
        
        # Le token sera fourni par le Bot Manager via la variable d'environnement
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

