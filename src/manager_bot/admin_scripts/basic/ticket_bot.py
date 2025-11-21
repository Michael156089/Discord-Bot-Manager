# Template: Ticket Bot
# Système de tickets pour support

import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

class TicketBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_counter = 0
    
    @commands.command(name='ticket')
    async def create_ticket(self, ctx, *, reason="Aucune raison"):
        """Créer un ticket de support."""
        guild = ctx.guild
        self.ticket_counter += 1
        
        ticket_name = f"ticket-{self.ticket_counter}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        try:
            ticket_channel = await guild.create_text_channel(
                name=ticket_name,
                overwrites=overwrites,
                reason=f"Ticket créé par {ctx.author}"
            )
            
            embed = discord.Embed(
                title=f"🎫 Ticket #{self.ticket_counter}",
                description=f"**Créé par:** {ctx.author.mention}\n**Raison:** {reason}",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Utilisez !close pour fermer ce ticket")
            
            await ticket_channel.send(embed=embed)
            await ctx.send(f"✅ Ticket créé: {ticket_channel.mention}", delete_after=10)
            
        except Exception as e:
            await ctx.send(f"❌ Erreur création ticket: {e}")
    
    @commands.command(name='close')
    async def close_ticket(self, ctx):
        """Fermer un ticket (seulement dans un channel ticket)."""
        if not ctx.channel.name.startswith("ticket-"):
            await ctx.send(f"❌ Cette commande ne fonctionne que dans un ticket.")
            return
        
        await ctx.send(f"🔒 Fermeture du ticket dans 5 secondes...")
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.timedelta(seconds=5))
        await ctx.channel.delete(reason=f"Ticket fermé par {ctx.author}")
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"🎫 Ticket Bot '{self.bot.user}' connecté!")
        print("[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE")

async def main():
    async with bot:
        await bot.add_cog(TicketBot(bot))
        TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        if not TOKEN:
            print("❌ Token manquant!")
            return
        await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
