# GUIDE DE DEMARRAGE RAPIDE

## Etape 1: Configuration initiale

1. Clonez/telechargez le projet
2. Installez les dependances:
   ```bash
   pip install -r requirements.txt
   ```

3. Creez votre Bot Manager sur Discord Developer Portal:
   - Allez sur https://discord.com/developers/applications
   - Creez une nouvelle application
   - Allez dans "Bot" et creez un bot
   - Copiez le token
   - Activez "MESSAGE CONTENT INTENT" et "SERVER MEMBERS INTENT"

4. Modifiez `config.py`:
   ```python
   BOT_MANAGER_TOKEN = "VOTRE_TOKEN_ICI"
   ADMIN_IDS = [VOTRE_ID_DISCORD]
   ```

5. Lancez le bot:
   ```bash
   python main.py
   ```

## Etape 2: Premier utilisateur

1. En tant qu'admin, utilisez:
   ```
   /create_secret user_id:123456789 max_bots:5
   ```
   Le bot vous donnera un code secret.

2. L'utilisateur utilise:
   ```
   /register secret_id:LE_CODE_SECRET
   ```
   Il recevra automatiquement le lien d'invitation du Bot Manager.

3. L'utilisateur peut maintenant ajouter ses bots:
   ```
   /add_bot nom:MonBot token:TOKEN_DU_BOT script:moderation.py
   ```

4. Demarrer le bot:
   ```
   /start_bot nom:MonBot
   ```

## Etape 3: Gestion quotidienne

### Pour les utilisateurs:

- **Voir mes bots**: `/my_bots`
- **Infos d'un bot**: `/bot_info nom:MonBot`
- **Arreter**: `/stop_bot nom:MonBot`
- **Redemarrer**: `/restart_bot nom:MonBot`
- **Changer token**: `/update_token nom:MonBot new_token:NOUVEAU_TOKEN`

### Pour les admins:

- **Lister users**: `/list_users`
- **Revoquer user**: `/revoke_user user_id:123456789`

## Personnalisation des scripts

Vous pouvez modifier les scripts dans `scripts_admin/`:

### Ajouter une commande dans moderation.py:
```python
@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member):
    # Votre code ici
    pass
```

### Ajouter un filtre dans protect.py:
```python
@bot.event
async def on_message(message):
    if "mot_interdit" in message.content.lower():
        await message.delete()
```

## Monitoring

Les logs de chaque bot sont dans:
```
logs/USER_ID/BOT_NAME.log
```

Le systeme surveille automatiquement les bots et les redemarre en cas de crash.

## Resolution de problemes

### Le bot ne repond pas aux commandes:
- Verifiez que le bot est bien invite avec les permissions administrateur
- Verifiez que les slash commands sont synchronisees (redemarrez le bot)

### Un bot utilisateur ne demarre pas:
- Verifiez le token dans la base de donnees
- Consultez les logs dans `logs/USER_ID/BOT_NAME.log`
- Verifiez que les intents sont actives sur le Discord Developer Portal

### Erreur de permissions:
- Le Bot Manager a besoin des permissions administrateur
- Les bots utilisateurs ont besoin des intents MESSAGE CONTENT et SERVER MEMBERS

## Securite avancee

### Changer la cle de chiffrement:

Dans `config.py`, la cle est generee automatiquement. Pour utiliser une cle fixe:

```python
ENCRYPTION_KEY = b'votre_cle_32_bytes_en_base64=='
cipher = Fernet(ENCRYPTION_KEY)
```

Ne partagez JAMAIS cette cle !

### Sauvegarde de la base de donnees:

```bash
cp data/bot_manager.db data/bot_manager.db.backup
```

### Sauvegarde des secrets:

```bash
cp secrets.json secrets.json.backup
```

## Evolutions possibles

- Interface web pour la gestion
- Statistiques d'utilisation
- Logs centralises
- Notifications webhook
- Support de plus de scripts
- Rate limiting personalise
- Dashboard en temps reel

## Conseils

1. Testez toujours les nouveaux bots dans un serveur de test
2. Limitez le nombre de bots par utilisateur selon vos ressources serveur
3. Surveillez regulierement les logs
4. Faites des sauvegardes regulieres de la DB et des secrets
5. Ne donnez jamais les tokens des bots

## Support

En cas de probleme:
1. Consultez les logs
2. Verifiez la configuration
3. Testez avec un bot simple d'abord
4. Verifiez les permissions Discord

---

## EXEMPLES D'UTILISATION

### Scenario 1: Creer un utilisateur premium avec 10 bots

```
Admin: /create_secret user_id:123456789 max_bots:10
Bot:  Secret cree: abc123def456...
```

### Scenario 2: Utilisateur s'inscrit

```
User: /register secret_id:abc123def456...
Bot:  Inscription reussie! Max bots: 10
     Lien d'invitation Bot Manager: https://discord.com/oauth2/...
```

### Scenario 3: Ajouter et demarrer un bot de moderation

```
User: /add_bot nom:MonBot token:MTk5... script:moderation.py
Bot:  Bot `ModBot` ajoute avec moderation.py

User: /start_bot nom:ModBot
Bot:  Bot `ModBot` demarre
```

### Scenario 4: Bot crash et auto-restart

```
[Le bot ModBot crash]
User recoit en MP:  Votre bot `ModBot` s'est arrete. Redemarrage automatique...
User recoit en MP:  Bot `ModBot` redemarre avec succes.
```

### Scenario 5: Revoquer un utilisateur abusif

```
Admin: /revoke_user user_id:123456789
Bot:  Utilisateur 123456789 revoque
[Tous ses bots sont arretes et supprimes]
```

## CHECKLIST DE MISE EN PRODUCTION

- [ ] Token Bot Manager configure
- [ ] Admin IDs configures
- [ ] Dependances installees
- [ ] Intents actives sur Discord
- [ ] Bot demarre et commandes synchronisees
- [ ] Test de creation de secret
- [ ] Test d'inscription utilisateur
- [ ] Test d'ajout de bot
- [ ] Test de demarrage de bot
- [ ] Logs fonctionnels
- [ ] Auto-restart teste
- [ ] Permissions Discord verifiees
- [ ] Sauvegarde DB configuree

## NOTES TECHNIQUES

### Architecture:
- Bot Manager: Processus principal (main.py)
- Bots utilisateurs: Sous-processus isoles (subprocess.Popen)
- Base de donnees: SQLite avec aiosqlite
- Chiffrement: Fernet (cryptography)

### Isolation:
Chaque bot utilisateur tourne dans son propre processus Python, avec:
- Son propre environnement (token en variable d'env)
- Ses propres logs
- Son propre repertoire de travail

### Monitoring:
Une tache asyncio verifie toutes les 30 secondes l'etat des processus.
Si un bot est mort (process.poll() != None), il est automatiquement redemarre.

### Securite:
- Les tokens ne sont jamais stockes en clair
- Chaque utilisateur ne peut acceder qu'a ses propres bots
- Les secrets d'inscription expirent apres 30 jours
- Un secret ne peut etre utilise qu'une seule fois