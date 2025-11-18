import random

RESPONSES = {
    # Réponses en cas de succès
    "ban_success": [
        "C'est fait, **{target}** a été banni. La porte, c'est par là.",
        "Yes, **{target}** a pris son ban. On le reverra plus.",
        "**{target}** a été envoyé en exil. Adios.",
        "Mission accomplie. **{target}** est plus là.",
        "Ok, **{target}** a été éjecté. Zéro pitié.",
        "Voilà, **{target}** a été banni. On respire.",
        "C'est bon, **{target}** a été mis au coin, mais pour de vrai.",
        "**{target}** a été neutralisé. On est tranquilles.",
        "Le couperet est tombé pour **{target}**. Ban mérité.",
        "Et bim, **{target}** a été banni. Fallait pas chercher."
    ],
    "kick_success": [
        "**{target}** a été kick. Un peu d'air frais lui fera du bien.",
        "Allez, dehors ! **{target}** a été gentiment raccompagné à la sortie.",
        "**{target}** a été expulsé. Il pourra retenter sa chance, ou pas.",
        "C'est réglé, **{target}** a été mis à la porte.",
        "Ok, **{target}** a été sorti. Problème suivant.",
        "Un petit coup de pied aux fesses pour **{target}**. C'est fait.",
        "**{target}** a été viré. Il a compris le message.",
        "Expulsion de **{target}** réussie. On passe à autre chose.",
        "C'est bon, **{target}** est parti faire un tour. Pour de bon.",
        "Le kick est parti tout seul sur **{target}**. C'est la vie."
    ],
    "setprefix_success": [
        "C'est carré, le nouveau préfixe est : `{prefix}`",
        "Bien reçu, le préfixe c'est maintenant `{prefix}`. Fais pas l'con avec.",
        "Ok, le préfixe a été changé en `{prefix}`. T'as intérêt à t'en souvenir.",
        "Nouveau préfixe `{prefix}` enregistré. C'est toi le boss.",
        "C'est noté, le préfixe est `{prefix}`. Simple, basique.",
        "Voilà, `{prefix}` sera le nouveau signe de ralliement.",
        "Le préfixe est maintenant `{prefix}`. À tes ordres.",
        "Ça marche, le préfixe est `{prefix}`. On innove.",
        "Préfixe mis à jour : `{prefix}`. C'est frais.",
        "Validé. Le nouveau préfixe est `{prefix}`."
    ],

    # Réponses en cas d'erreurs
    "permission_denied": [
        "T'as pas les droits pour ça, frérot. Il te faut le niveau {level}.",
        "Essaie pas, t'as pas le niveau {level} pour ça.",
        "Non, non, non. Il te faut la perm {level} pour faire ça.",
        "T'as cru ? Niveau {level} requis, et tu l'as pas.",
        "C'est pas pour toi, ça. Reviens quand t'auras le niveau {level}.",
        "Accès refusé. Il te manque le niveau {level}.",
        "Tu peux pas faire ça. Il faut être niveau {level} minimum.",
        "T'es pas assez haut gradé pour ça. Niveau {level} demandé.",
        "Oublie, c'est pour les grands ça (niveau {level}).",
        "Hmm, il te manque des galons. Niveau {level} pour être précis."
    ],
    "ban_fail_immune": [
        "Tu peux pas toucher à **{target}**, il est protégé par l'immunité.",
        "Laisse **{target}** tranquille, il est intouchable.",
        "Même pas en rêve. **{target}** a un totem d'immunité.",
        "T'attaques un mur, là. **{target}** est immunisé.",
        "C'est non. **{target}** est un VIP, immunité activée."
    ],
     "kick_fail_immune": [
        "Tu peux pas toucher à **{target}**, il est protégé par l'immunité.",
        "Laisse **{target}** tranquille, il est intouchable.",
        "Même pas en rêve. **{target}** a un totem d'immunité.",
        "T'attaques un mur, là. **{target}** est immunisé.",
        "C'est non. **{target}** est un VIP, immunité activée."
    ],
    "mute_fail_immune": [
        "Tu peux pas mute **{target}**, il est protégé par l'immunité.",
        "Laisse **{target}** tranquille, il est intouchable.",
        "Même pas en rêve. **{target}** a un totem d'immunité pour le mute.",
        "T'attaques un mur, là. **{target}** est immunisé contre le mute.",
        "C'est non. **{target}** est un VIP, immunité activée."
    ],
    "unmute_fail_immune": [
        "Tu peux pas unmute **{target}**, il est protégé par l'immunité.",
        "Laisse **{target}** tranquille, il est intouchable.",
        "Même pas en rêve. **{target}** a un totem d'immunité pour le mute.",
        "T'attaques un mur, là. **{target}** est immunisé contre le mute.",
        "C'est non. **{target}** est un VIP, immunité activée."
    ],
    "warn_fail_immune": [
        "Tu peux pas warn **{target}**, il est protégé par l'immunité.",
        "Laisse **{target}** tranquille, il est intouchable.",
        "Même pas en rêve. **{target}** a un totem d'immunité.",
        "T'attaques un mur, là. **{target}** est immunisé.",
        "C'est non. **{target}** est un VIP, immunité activée."
    ],
     "rank_fail_immune": [
        "Tu peux pas toucher à **{target}**, il est protégé .",
        "Laisse **{target}** tranquille, il est intouchable.",
        "Même pas en rêve.",
        "T'ataques un mur, là.",
        "C'est non. **{target}** est un VIP."
    ]
}

def get_random_response(key, **kwargs):
    """
    Récupère une réponse aléatoire et la formate.
    Gère les clés inexistantes.
    """
    if key not in RESPONSES:
        return "Oups, y'a un bug dans la matrice des réponses."
    
    response = random.choice(RESPONSES[key])
    return response.format(**kwargs)
