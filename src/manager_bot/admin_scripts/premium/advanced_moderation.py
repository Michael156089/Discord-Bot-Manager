"""
Script de modération avancée avec système de warns, auto-mod, etc.
"""
import discord
from discord.ext import commands
import os
import sys
import json

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("ERREUR: Le token du bot est manquant. Assurez-vous que DISCORD_BOT_TOKEN est defini.")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, description="Bot de modération avancée", help_command=None)

# Système de warns
warns_file = "warns.json" # This will be in the user's bot scripts directory

def load_warns():
    if os.path.exists(warns_file):
        try:
            with open(warns_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"WARN: Could not decode {warns_file}. Starting with empty warns.")
            return {}
    return {}

def save_warns(warns):
    with open(warns_file, 'w', encoding='utf-8') as f:
        json.dump(warns, f, indent=2)

class AdvancedModeration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='warn')
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason="Aucune raison"):
        warns = load_warns()
        user_id = str(member.id)
        
        if user_id not in warns:
            warns[user_id] = []
        
        warns[user_id].append({
            "reason": reason,
            "mod": ctx.author.id,
            "timestamp": ctx.message.created_at.isoformat()
        })
        
        save_warns(warns)
        
        warn_count = len(warns[user_id])
        await ctx.send(f"⚠️ {member.mention} a été averti. Raison: {reason}\nTotal: {warn_count} warn(s)")
        
        # Auto-sanctions
        if warn_count >= 3:
            try:
                await member.ban(reason=f"3 warns atteints")
                await ctx.send(f"🔨 {member.mention} banni automatiquement (3 warns)")
            except discord.Forbidden:
                await ctx.send(f"❌ Impossible de bannir {member.mention}. Permissions insuffisantes.")

    @commands.command(name='warnings')
    async def list_warnings(self, ctx, member: discord.Member):
        warns = load_warns()
        user_id = str(member.id)

        if user_id not in warns or not warns[user_id]:
            await ctx.send(f"{member.display_name} n'a aucun avertissement.")
            return

        embed = discord.Embed(title=f"Avertissements de {member.display_name}", color=discord.Color.orange())
        for i, warn_data in enumerate(warns[user_id]):
            mod_user = self.bot.get_user(warn_data['mod'])
            mod_name = mod_user.display_name if mod_user else f"ID {warn_data['mod']}"
            embed.add_field(
                name=f"Warn #{i+1}",
                value=f"Raison: {warn_data['reason']}\nModérateur: {mod_name}\nDate: {warn_data['timestamp'][:10]}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name='clearwarns')
    @commands.has_permissions(moderate_members=True)
    async def clear_warnings(self, ctx, member: discord.Member):
        warns = load_warns()
        user_id = str(member.id)

        if user_id in warns:
            del warns[user_id]
            save_warns(warns)
            await ctx.send(f"✅ Tous les avertissements de {member.display_name} ont été effacés.")
        else:
            await ctx.send(f"{member.display_name} n'a aucun avertissement à effacer.")


    @commands.Cog.listener()
    async def on_ready(self):
        print(f"✅ Bot {self.bot.user} (Advanced Moderation) connecté!")
        print("[BOT_MANAGER_SIGNAL] CONNEXION_REUSSIE")

async def main():
    async with bot:
        await bot.add_cog(AdvancedModeration(bot))
        await bot.start(TOKEN)

if __name__ == "__main__":
    print(f"Demarrage du bot (Advanced Moderation)...")
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot arrete.")
    except Exception as e:
        print(f"ERREUR FATALE: {e}")
        sys.exit(1)
