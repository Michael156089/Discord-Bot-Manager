import discord

async def get_target_user_async(ctx, user_input=None):
    """Tente de trouver un utilisateur via mention, ID, ou en réponse à un message."""
    # 1. Vérifie si c'est une réponse à un message
    if ctx.message.reference and ctx.message.reference.message_id:
        try:
            replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            return replied_message.author
        except (discord.NotFound, discord.HTTPException):
            pass  # Message introuvable

    # 2. Si un argument est fourni, tente de le convertir
    if user_input:
        if isinstance(user_input, discord.Member): # Déjà un membre
            return user_input

        if isinstance(user_input, str): # Tente la conversion depuis une chaîne
            try:
                converter = discord.ext.commands.MemberConverter()
                member = await converter.convert(ctx, user_input)
                return member
            except discord.ext.commands.BadArgument:
                pass # Échec de la conversion, continue

            if user_input.isdigit(): # Si c'est un ID numérique
                try:
                    member = ctx.guild.get_member(int(user_input))
                    if member:
                        return member
                except (ValueError, TypeError):
                    pass
    
    # 3. Retourne None si l'utilisateur n'est pas trouvé
    return None
