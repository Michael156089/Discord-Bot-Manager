# Template: Ticket Bot
# Système de tickets pour support

SCRIPT_METADATA = {
    "name": "ticket_bot",
    "version": "1.1.0",
    "min_manager_version": "1.0.0",
    "author": "Bot Manager",
    "description": "Système de tickets simple avec création de channels privés",
    "changelog": {
        "1.1.0": "Ajout commandes VIP (setstatus) et Help personnalisé",
        "1.0.0": "Version initiale"
    },
    "db_schema_version": 1,
    "deprecated": False
}

import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

def is_vip(ctx):
    vip_ids = os.getenv("VIP_IDS", "").split(",")
    return str(ctx.author.id) in vip_ids or ctx.author.id == ctx.guild.owner_id

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="🎫 Aide Ticket Bot", color=discord.Color.blue())
        for cog, commands in mapping.items():
            if commands:
                cog_name = cog.qualified_name if cog else "Commandes"
                cmd_list = [f"`{c.name}`" for c in commands]
                embed.add_field(name=cog_name, value=", ".join(cmd_list), inline=False)
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=f"Commande: {command.name}", description=command.help or "Pas de description", color=discord.Color.blue())
        if command.aliases:
            embed.add_field(name="Alias", value=", ".join(command.aliases))
        await self.get_destination().send(embed=embed)

bot = commands.Bot(command_prefix="!", intents=intents)
bot.help_command = CustomHelpCommand()

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

    @commands.command(name="setstatus")
    async def set_status(self, ctx, status_type: str, *, message: str):
        """[VIP] Changer le statut (playing, watching, listening, streaming)."""
        if not is_vip(ctx):
            return await ctx.send("❌ Réservé aux VIPs ou au propriétaire.")
        
        try:
            activity_type = getattr(discord.ActivityType, status_type.lower(), discord.ActivityType.playing)
            await self.bot.change_presence(activity=discord.Activity(type=activity_type, name=message))
            await ctx.send(f"✅ Statut mis à jour: **{status_type} {message}**")
        except AttributeError:
            await ctx.send("❌ Type de statut invalide. Utilisez: playing, watching, listening, streaming")
    
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
