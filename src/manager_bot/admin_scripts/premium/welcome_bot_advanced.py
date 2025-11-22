# Template: Welcome Bot Advanced
# Ported from JS: Custom welcome/leave messages, database support

SCRIPT_METADATA = {
    "name": "welcome_bot_advanced",
    "version": "1.1.0",
    "min_manager_version": "1.0.0",
    "author": "Bot Manager (Ported)",
    "description": "Système avancé de bienvenue/au revoir avec messages personnalisables et base de données",
    "changelog": {
        "1.1.0": "Ajout commandes VIP (setstatus) et Help personnalisé",
        "1.0.0": "Initial port from JS to Python"
    },
    "db_schema_version": 1,
    "deprecated": False
}

import discord
from discord.ext import commands
import sqlite3
import os
import datetime

def is_vip(ctx):
    vip_ids = os.getenv("VIP_IDS", "").split(",")
    return str(ctx.author.id) in vip_ids or ctx.author.id == ctx.guild.owner_id

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="👋 Aide Welcome Bot Advanced", color=discord.Color.blue())
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

class LocalDatabase:
    def __init__(self, db_name="welcome_advanced.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS guild_config (
                        guild_id TEXT PRIMARY KEY,
                        welcome_channel_id TEXT,
                        leave_channel_id TEXT,
                        welcome_message TEXT,
                        leave_message TEXT
                    )''')
        conn.commit()
        conn.close()

    def get_config(self, guild_id):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT * FROM guild_config WHERE guild_id=?", (str(guild_id),))
        res = c.fetchone()
        conn.close()
        return res

    def update_config(self, guild_id, **kwargs):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Check if exists
        c.execute("SELECT 1 FROM guild_config WHERE guild_id=?", (str(guild_id),))
        exists = c.fetchone()
        
        if not exists:
            c.execute("INSERT INTO guild_config (guild_id) VALUES (?)", (str(guild_id),))
        
        for key, value in kwargs.items():
            c.execute(f"UPDATE guild_config SET {key}=? WHERE guild_id=?", (value, str(guild_id)))
            
        conn.commit()
        conn.close()
        
    def clear_data(self, guild_id, data_type="all"):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        if data_type == "all":
            c.execute("DELETE FROM guild_config WHERE guild_id=?", (str(guild_id),))
        elif data_type == "welcome_channel":
            c.execute("UPDATE guild_config SET welcome_channel_id=NULL WHERE guild_id=?", (str(guild_id),))
        elif data_type == "leave_channel":
            c.execute("UPDATE guild_config SET leave_channel_id=NULL WHERE guild_id=?", (str(guild_id),))
        elif data_type == "welcome_message":
            c.execute("UPDATE guild_config SET welcome_message=NULL WHERE guild_id=?", (str(guild_id),))
        elif data_type == "leave_message":
            c.execute("UPDATE guild_config SET leave_message=NULL WHERE guild_id=?", (str(guild_id),))
            
        conn.commit()
        conn.close()

class WelcomeBotAdvanced(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = LocalDatabase()
        self.default_join_msg = "Welcome {member:mention}! We now have {server:members} member!"
        self.default_leave_msg = "😢 {member:name} just left the server... We are down to {server:members} members... "

    def format_message(self, msg, member, guild):
        return msg.replace("{member:mention}", member.mention)\
                  .replace("{member:name}", member.name)\
                  .replace("{member:id}", str(member.id))\
                  .replace("{member:tag}", str(member))\
                  .replace("{member:createdAt}", member.created_at.strftime("%Y-%m-%d %H:%M:%S"))\
                  .replace("{server:name}", guild.name)\
                  .replace("{server:members}", str(guild.member_count))

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"👋 Welcome Bot Advanced '{self.bot.user}' connecté!")
        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="new members"))
        print("[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = self.db.get_config(member.guild.id)
        if not config:
            return
            
        # config: guild_id, welcome_channel_id, leave_channel_id, welcome_message, leave_message
        welcome_channel_id = config[1]
        welcome_msg = config[3] or self.default_join_msg
        
        if welcome_channel_id:
            channel = member.guild.get_channel(int(welcome_channel_id))
            if channel:
                content = self.format_message(welcome_msg, member, member.guild)
                await channel.send(content)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        config = self.db.get_config(member.guild.id)
        if not config:
            return
            
        leave_channel_id = config[2]
        leave_msg = config[4] or self.default_leave_msg
        
        if leave_channel_id:
            channel = member.guild.get_channel(int(leave_channel_id))
            if channel:
                content = self.format_message(leave_msg, member, member.guild)
                await channel.send(content)

    @commands.command(name="joinchannel")
    @commands.has_permissions(administrator=True)
    async def set_join_channel(self, ctx, channel: discord.TextChannel):
        """Définit le salon de bienvenue."""
        self.db.update_config(ctx.guild.id, welcome_channel_id=str(channel.id))
        
        embed = discord.Embed(title="Succès!", description=f"Salon de bienvenue défini sur {channel.mention}", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name="leavechannel")
    @commands.has_permissions(administrator=True)
    async def set_leave_channel(self, ctx, channel: discord.TextChannel):
        """Définit le salon de départ."""
        self.db.update_config(ctx.guild.id, leave_channel_id=str(channel.id))
        
        embed = discord.Embed(title="Succès!", description=f"Salon de départ défini sur {channel.mention}", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name="joinmessage")
    @commands.has_permissions(administrator=True)
    async def set_join_message(self, ctx, *, message: str):
        """Définit le message de bienvenue. Variables: {member:mention}, {member:name}, {server:members}..."""
        self.db.update_config(ctx.guild.id, welcome_message=message)
        
        embed = discord.Embed(title="Succès!", description=f"Message de bienvenue défini:\n`{message}`", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name="leavemessage")
    @commands.has_permissions(administrator=True)
    async def set_leave_message(self, ctx, *, message: str):
        """Définit le message de départ. Variables: {member:mention}, {member:name}, {server:members}..."""
        self.db.update_config(ctx.guild.id, leave_message=message)
        
        embed = discord.Embed(title="Succès!", description=f"Message de départ défini:\n`{message}`", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name="emit")
    @commands.has_permissions(administrator=True)
    async def emit_event(self, ctx, event: str):
        """Simule un événement (join/leave)."""
        if event.lower() == "join":
            await self.on_member_join(ctx.author)
            await ctx.send("✅ Événement 'join' simulé.")
        elif event.lower() == "leave":
            await self.on_member_remove(ctx.author)
            await ctx.send("✅ Événement 'leave' simulé.")
        else:
            await ctx.send("❌ Événement inconnu. Utilisez `join` ou `leave`.")

    @commands.command(name="cleardata")
    @commands.has_permissions(administrator=True)
    async def clear_data_cmd(self, ctx):
        """Supprime les données de configuration (Interactive)."""
        view = ClearDataView(self.db, ctx.guild.id, ctx.author.id)
        embed = discord.Embed(title="Effacer les données", description="Que voulez-vous effacer ?", color=discord.Color.blue())
        await ctx.send(embed=embed, view=view)

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

class ClearDataView(discord.ui.View):
    def __init__(self, db, guild_id, author_id):
        super().__init__(timeout=60)
        self.db = db
        self.guild_id = guild_id
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Ce n'est pas votre commande.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Welcome Channel", style=discord.ButtonStyle.danger, emoji="🔴")
    async def clear_welcome_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.db.clear_data(self.guild_id, "welcome_channel")
        await interaction.response.send_message("✅ Welcome Channel effacé.", ephemeral=True)

    @discord.ui.button(label="Leave Channel", style=discord.ButtonStyle.danger, emoji="🟠")
    async def clear_leave_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.db.clear_data(self.guild_id, "leave_channel")
        await interaction.response.send_message("✅ Leave Channel effacé.", ephemeral=True)

    @discord.ui.button(label="Join Message", style=discord.ButtonStyle.primary, emoji="🟡")
    async def clear_join_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.db.clear_data(self.guild_id, "welcome_message")
        await interaction.response.send_message("✅ Join Message effacé.", ephemeral=True)

    @discord.ui.button(label="Leave Message", style=discord.ButtonStyle.primary, emoji="🟢")
    async def clear_leave_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.db.clear_data(self.guild_id, "leave_message")
        await interaction.response.send_message("✅ Leave Message effacé.", ephemeral=True)

    @discord.ui.button(label="TOUT EFFACER", style=discord.ButtonStyle.danger, emoji="⛔", row=1)
    async def clear_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.db.clear_data(self.guild_id, "all")
        await interaction.response.send_message("✅ TOUTES les données ont été effacées.", ephemeral=True)
        self.stop()

async def main():
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    bot.help_command = CustomHelpCommand()
    
    async with bot:
        await bot.add_cog(WelcomeBotAdvanced(bot))
        TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        if not TOKEN:
            print("❌ Token manquant!")
            return
        await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
