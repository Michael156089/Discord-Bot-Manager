import discord
from datetime import datetime
from .database import get_log_channel

async def log_action(bot, ctx, target, command_name, reason=None, duration=None):
    """Envoie un message de log dans le salon configuré."""
    log_channel_id = get_log_channel(ctx.guild.id)
    if not log_channel_id:
        return

    log_channel = bot.get_channel(log_channel_id)
    if not log_channel:
        return

    embed = discord.Embed(
        title=f"Commande exécutée : `{command_name}`",
        color=0xFFA500,  # Orange
        timestamp=datetime.utcnow()
    )
    embed.set_author(name=f"{ctx.author.name} ({ctx.author.id})", icon_url=ctx.author.display_avatar.url)
    embed.add_field(name="Cible", value=f"{target.name} ({target.id})", inline=True)
    embed.add_field(name="Salon", value=ctx.channel.mention, inline=True)
    
    if reason:
        embed.add_field(name="Raison", value=reason, inline=False)
    if duration:
        embed.add_field(name="Durée", value=duration, inline=True)

    embed.set_footer(text=f"ID du Modérateur : {ctx.author.id}")

    try:
        await log_channel.send(embed=embed)
    except discord.Forbidden:
        # Le bot n'a pas les permissions d'envoyer des messages dans le salon de logs
        print(f"Erreur: Impossible d'envoyer un message dans le salon de logs sur le serveur {ctx.guild.name}.")
    except Exception as e:
        print(f"Une erreur est survenue lors de l'envoi du log: {e}")
