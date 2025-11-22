import discord
from discord.ext import commands
import wavelink
import os
import asyncio
import time
import aiohttp
import logging
import json

# --- Configuration ---
TOKEN = "MTQxNjU0MDU4NTM4MDI4MjQyOQ.GdOy-k.nk-bse3dqQFjLTmdX2GRnVwtsJ74CTox7q63Zg"

class LavalinkNode:
    def __init__(self, name, uri, password, region="unknown"):
        self.name = name
        self.uri = uri
        self.password = password
        self.region = region
        self.latency = float('inf')
        self.is_available = False
        self.last_check = 0
        self.failures = 0

class IntelligentNodeManager:
    def __init__(self):
        self.nodes = [
            LavalinkNode("Jirayu", "http://lavalink.jirayu.net:13592", "youshallnotpass", "Asia"),
            LavalinkNode("Hatry4", "http://lavahatry4.techbyte.host:3000", "NAIGLAVA-dash.techbyte.host", "Europe"),
            LavalinkNode("AjieDev-1", "http://lava-v4.ajieblogs.eu.org:80", "https://dsc.gg/ajidevserver", "Global"),
            LavalinkNode("Serenetia", "http://lavalinkv4.serenetia.com:80", "https://dsc.gg/ajidevserver", "Global"),
            LavalinkNode("Embotic", "http://46.202.82.164:1027", "jmlitelavalink", "Europe"),
            LavalinkNode("Yumi", "http://173.249.0.115:13592", "https://camming.xyz", "Global"),
            LavalinkNode("AneFaiz", "http://194.102.181.219:3956", "https://discord.gg/mjS5J2K3ep", "Europe"),
            LavalinkNode("Trinium-4x", "http://181.215.45.8:2333", "kirito", "America"),
            LavalinkNode("Trinium-3x", "http://181.215.45.8:2334", "free", "America"),
            LavalinkNode("dctv (sgp)", "http://s13.oddblox.us:28405", "quangloc2018", "Asia"),
            LavalinkNode("Serenetia-LDP-NonSSL", "http://lavalink.serenetia.com:80", "https://dsc.gg/ajidevserver", "Global"),
            LavalinkNode("Lavalink APGB", "http://airplanegobrr.us.to:2333", "youshallnotpass", "America"),
            LavalinkNode("Elysia-V4", "http://zeus.hidencloud.com:24729", "https://dsc.gg/galaxyserver", "Global"),
            LavalinkNode("RY4N", "http://vip.visionhost.cloud:7023", "youshallnotpass", "unknown"),
        ]
        self.connected_nodes = []
        self.primary_node = None
        self.fallback_nodes = []
        self.monitoring_task = None

    async def test_node_latency(self, node):
        """Test la latence d'un nœud"""
        try:
            start_time = time.time()
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{node.uri}/version") as response:
                    if response.status == 200:
                        node.latency = (time.time() - start_time) * 1000
                        node.is_available = True
                        node.failures = 0
                        return True
        except:
            pass
        
        node.latency = float('inf')
        node.is_available = False
        node.failures += 1
        return False

    async def find_best_nodes(self):
        """Trouve les meilleurs nœuds disponibles"""
        print("🔍 Test des serveurs Lavalink...")
        
        # Tester tous les nœuds en parallèle
        tasks = [self.test_node_latency(node) for node in self.nodes]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Trier par latence
        available_nodes = [node for node in self.nodes if node.is_available]
        available_nodes.sort(key=lambda x: x.latency)
        
        if available_nodes:
            self.primary_node = available_nodes[0]
            self.fallback_nodes = available_nodes[1:4]  # Garder 3 serveurs de backup
            
            print(f"✅ Serveur principal: {self.primary_node.name} ({self.primary_node.latency:.0f}ms)")
            for i, node in enumerate(self.fallback_nodes, 1):
                print(f"🔄 Backup {i}: {node.name} ({node.latency:.0f}ms)")
        else:
            print("❌ Aucun serveur Lavalink disponible!")

    async def connect_nodes(self, client):
        """Connecte aux meilleurs nœuds"""
        if not self.primary_node:
            return False

        try:
            # Connecter le nœud principal
            primary_wavelink_node = wavelink.Node(
                identifier=self.primary_node.name,
                uri=self.primary_node.uri,
                password=self.primary_node.password
            )
            
            # Connecter aussi les backups
            backup_nodes = []
            for backup in self.fallback_nodes:
                backup_wavelink_node = wavelink.Node(
                    identifier=backup.name,
                    uri=backup.uri,
                    password=backup.password
                )
                backup_nodes.append(backup_wavelink_node)
            
            all_nodes = [primary_wavelink_node] + backup_nodes
            await wavelink.Pool.connect(client=client, nodes=all_nodes)
            
            return True
        except Exception as e:
            print(f"❌ Erreur connexion: {e}")
            return False

    async def start_monitoring(self, bot):
        """Démarre le monitoring continu"""
        while True:
            try:
                await asyncio.sleep(60)  # Vérifier toutes les minutes
                
                # Vérifier l'état du nœud principal
                if self.primary_node:
                    is_healthy = await self.test_node_latency(self.primary_node)
                    
                    if not is_healthy:
                        print(f"⚠️ Nœud principal {self.primary_node.name} indisponible!")
                        await self.handle_node_failure(bot)
                        
            except Exception as e:
                print(f"Erreur monitoring: {e}")

    async def handle_node_failure(self, bot):
        """Gère la panne d'un nœud"""
        try:
            # Chercher un nouveau nœud principal
            await self.find_best_nodes()
            
            if self.primary_node:
                print(f"🔄 Basculement vers {self.primary_node.name}")
                
                # Envoyer message d'optimisation dans tous les canaux actifs
                for guild in bot.guilds:
                    player = guild.voice_client
                    if player and hasattr(player, 'channel') and player.channel:
                        try:
                            embed = discord.Embed(
                                title="🧠 Optimisation Intelligente",
                                description="Basculement automatique vers un serveur plus performant...",
                                color=0x00ff00
                            )
                            await player.channel.send(embed=embed, delete_after=5)
                        except:
                            pass
        except Exception as e:
            print(f"Erreur lors du basculement: {e}")

# Custom Exceptions for Music Cog checks
class VoiceChannelCheckFailure(commands.CheckFailure):
    """Base exception for voice channel checks."""
    pass

class NotInVoiceChannel(VoiceChannelCheckFailure):
    """Exception raised when the user is not in a voice channel."""
    pass

class NotInSameVoiceChannel(VoiceChannelCheckFailure):
    """Exception raised when the user is not in the same voice channel as the bot."""
    pass


class MusicCog(commands.Cog, name="Musique"):
    """Commandes liées à la musique."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.now_playing_messages = {}
        self.update_tasks = {}
        self.node_manager = bot.node_manager
        self.disconnect_timers = {}
        self.playlist_file = "playlists.json"
        self.playlists = self._load_playlists()
        self.connection_retries = {}  # Nouveau: compteur de tentatives de connexion

    def _load_playlists(self):
        """Loads playlists from the JSON file."""
        try:
            with open(self.playlist_file, 'r') as f:
                return {int(k): v for k, v in json.load(f).items()}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_playlists(self):
        """Saves playlists to the JSON file."""
        with open(self.playlist_file, 'w') as f:
            json.dump(self.playlists, f, indent=4)

    async def safe_voice_connect(self, channel, timeout=30.0, retries=3):
        """Connexion sécurisée au salon vocal avec retry automatique."""
        guild_id = channel.guild.id
        
        for attempt in range(retries):
            try:
                print(f"🔌 Tentative de connexion {attempt + 1}/{retries} au salon {channel.name}")
                
                # Augmenter le timeout pour les tentatives suivantes
                current_timeout = timeout + (attempt * 10)
                
                # Si le bot est déjà connecté ailleurs dans ce serveur, se déconnecter d'abord
                if channel.guild.voice_client:
                    await channel.guild.voice_client.disconnect(force=True)
                    await asyncio.sleep(2)  # Attendre un peu avant de reconnecter
                
                # Tentative de connexion
                player = await channel.connect(cls=wavelink.Player, timeout=current_timeout, reconnect=True)
                print(f"✅ Connecté avec succès au salon {channel.name}")
                
                # Reset le compteur de tentatives en cas de succès
                if guild_id in self.connection_retries:
                    del self.connection_retries[guild_id]
                
                return player
                
            except asyncio.TimeoutError:
                print(f"⏰ Timeout lors de la connexion (tentative {attempt + 1})")
                if attempt < retries - 1:
                    await asyncio.sleep(3)  # Attendre avant de réessayer
                    
            except discord.ClientException as e:
                print(f"❌ Erreur Discord: {e}")
                if "already connected" in str(e).lower():
                    # Le bot est déjà connecté, essayer de récupérer la connexion
                    existing_player = channel.guild.voice_client
                    if existing_player and existing_player.channel == channel:
                        print("♻️ Utilisation de la connexion existante")
                        return existing_player
                    else:
                        # Forcer la déconnexion et réessayer
                        if existing_player:
                            await existing_player.disconnect(force=True)
                            await asyncio.sleep(2)
                        continue
                        
            except Exception as e:
                print(f"❌ Erreur inattendue lors de la connexion: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5)
        
        # Incrémenter le compteur d'échecs
        self.connection_retries[guild_id] = self.connection_retries.get(guild_id, 0) + 1
        
        # Si trop d'échecs, essayer de changer de serveur Lavalink
        if self.connection_retries[guild_id] >= 3:
            print("🔄 Trop d'échecs de connexion, changement de serveur Lavalink...")
            await self.node_manager.handle_node_failure(self.bot)
            # Reset le compteur après changement de serveur
            self.connection_retries[guild_id] = 0
        
        raise discord.DiscordException("Impossible de se connecter au salon vocal après plusieurs tentatives")

    async def ensure_voice_connection(self, ctx):
        """S'assure qu'une connexion vocale valide existe."""
        player = ctx.voice_client
        
        # Vérifier si le player existe et est connecté
        if player and player.is_connected():
            # Vérifier si on est dans le bon salon
            if player.channel == ctx.author.voice.channel:
                return player
            else:
                # Mauvais salon, se déconnecter et reconnecter
                await player.disconnect()
                player = None
        
        # Pas de connexion ou connexion invalide, créer une nouvelle
        if not player:
            player = await self.safe_voice_connect(ctx.author.voice.channel)
            setattr(player, 'text_channel', ctx.channel)
        
        return player

    async def disconnect_after_idle(self, player: wavelink.Player):
        await asyncio.sleep(180)  # 3 minutes
        if player.is_connected() and len(player.channel.members) == 1:
            text_channel = getattr(player, 'text_channel', None)
            if text_channel:
                await text_channel.send("👋 Déconnexion car je suis seul dans le salon.")
            await player.disconnect()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        player: wavelink.Player = member.guild.voice_client
        if not player or not player.channel:
            return

        # Check only for events in the bot's channel
        if before.channel != player.channel and after.channel != player.channel:
            return

        human_members = [m for m in player.channel.members if not m.bot]
        guild_id = member.guild.id

        if len(human_members) == 0:
            if guild_id not in self.disconnect_timers:
                self.disconnect_timers[guild_id] = asyncio.create_task(self.disconnect_after_idle(player))
        else:
            if guild_id in self.disconnect_timers:
                self.disconnect_timers[guild_id].cancel()
                del self.disconnect_timers[guild_id]

    async def cog_check(self, ctx: commands.Context):
        """A check that applies to all commands in this cog."""
        if ctx.command.name == 'servers':
            return True

        if not ctx.author.voice:
            raise NotInVoiceChannel("Vous devez être dans un canal vocal pour utiliser cette commande.")

        player: wavelink.Player = ctx.voice_client
        if player and player.channel and player.channel != ctx.author.voice.channel:
            raise NotInSameVoiceChannel("Vous devez être dans le même canal vocal que le bot.")
        
        return True

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error handler for the MusicCog."""
        if isinstance(error, (NotInVoiceChannel, NotInSameVoiceChannel)):
            await ctx.send(str(error))
        elif isinstance(error, discord.DiscordException):
            if "connexion" in str(error).lower():
                await ctx.send("❌ Problème de connexion au salon vocal. Réessayez dans quelques instants.")
            else:
                await ctx.send(f"❌ Erreur Discord: {str(error)}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """Événement pour un nœud Lavalink prêt."""
        print(f'🔗 Node: <{payload.node.identifier}> est prêt.')

    @commands.Cog.listener()
    async def on_wavelink_node_disconnected(self, payload):
        """Événement pour un nœud déconnecté."""
        print(f'⚠️ Node: <{payload.node.identifier}> déconnecté.')
        # Le monitoring gérera la reconnexion

    def format_time(self, milliseconds):
        """Convertit les millisecondes en format mm:ss."""
        seconds = int(milliseconds // 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

    def generate_progress_bar(self, current_pos, total_length):
        """Génère une barre de progression avec un seul point rond."""
        if total_length == 0:
            return "─────────────────"
        
        progress = min(current_pos / total_length, 1.0)
        bar_length = 17
        cursor_position = int(bar_length * progress)
        
        # Créer la barre avec un seul point rond à la position actuelle
        bar = ""
        for i in range(bar_length):
            if i == cursor_position and cursor_position < bar_length:
                bar += "●"
            else:
                bar += "─"
        
        return bar

    def generate_animated_equalizer(self):
        """Génère l'égaliseur animé simple."""
        # Base de l'égaliseur exactement comme demandé
        base_pattern = "ılılılllıılılıllllıılılllıllı"
        animated = ""
        
        # Animation plus fluide basée sur le temps
        time_factor = int(time.time() * 3)
        
        for i, char in enumerate(base_pattern):
            # Animation en gardant les vrais caractères ı et l
            if (i + time_factor) % 4 == 0:
                # Alterner avec des variations subtiles
                if char == "ı":
                    animated += "|"  # Barre verticale pour l'animation
                elif char == "l":
                    animated += "|"  # Barre verticale pour l'animation
                else:
                    animated += char
            else:
                animated += char
        
        return f".{animated}."

    async def create_now_playing_message(self, track, current_position=0):
        """Crée le message 'En cours de lecture' animé."""
        duration_minutes = int(track.length // 60000)
        duration_seconds = int((track.length % 60000) // 1000)
        total_formatted = f"{duration_minutes}:{duration_seconds:02d}"
        
        current_formatted = self.format_time(current_position)
        progress_bar = self.generate_progress_bar(current_position, track.length)
        animated_equalizer = self.generate_animated_equalizer()
        
        # Afficher le serveur actuel
        current_node = "Optimisé"
        if self.node_manager.primary_node:
            current_node = self.node_manager.primary_node.name
        
        ascii_art = f"""```md
# En cours de lecture... | Serveur: {current_node}

> 🎵 Titre: {track.title}
> 👤 Auteur: {track.author}
> ⏳ Durée: {total_formatted}

{animated_equalizer}
{current_formatted} ─{progress_bar}─ {total_formatted}
        ↻      ◁ II ▷     ↺
```"""
        return ascii_art

    async def update_now_playing_loop(self, player, channel, track):
        """Boucle de mise à jour du message en cours de lecture."""
        message = None
        start_time = time.time() * 1000  # Temps de début en millisecondes
        
        try:
            while player.playing and player.current == track:
                # Calculer la position actuelle
                current_time = time.time() * 1000
                current_position = current_time - start_time
                
                # Créer le contenu mis à jour
                content = await self.create_now_playing_message(track, current_position)
                
                if message is None:
                    # Créer le premier message
                    message = await channel.send(content)
                    self.now_playing_messages[channel.guild.id] = message.id
                else:
                    # Mettre à jour le message existant
                    try:
                        await message.edit(content=content)
                    except discord.NotFound:
                        # Le message a été supprimé, en créer un nouveau
                        message = await channel.send(content)
                        self.now_playing_messages[channel.guild.id] = message.id
                    except discord.HTTPException:
                        # Erreur lors de l'édition, passer cette fois
                        pass
                
                # Attendre 0.5 seconde avant la prochaine mise à jour (très fluide)
                await asyncio.sleep(0.5)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Erreur dans la mise à jour: {e}")

    async def start_now_playing_ui(self, channel, track, player):
        """Démarre l'interface 'En cours de lecture'."""
        guild_id = channel.guild.id
        
        # Arrêter l'ancienne tâche si elle existe
        if guild_id in self.update_tasks:
            self.update_tasks[guild_id].cancel()
        
        # Supprimer l'ancien message
        if guild_id in self.now_playing_messages:
            try:
                old_message = await channel.fetch_message(self.now_playing_messages[guild_id])
                await old_message.delete()
            except (discord.NotFound, discord.HTTPException):
                pass
        
        # Démarrer la nouvelle tâche
        task = asyncio.create_task(self.update_now_playing_loop(player, channel, track))
        self.update_tasks[guild_id] = task

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Événement pour la fin d'un morceau."""
        player = payload.player
        
        # Vérifier que le player a une guild
        if not player or not player.guild:
            return
            
        guild_id = player.guild.id

        # Arrêter la tâche de mise à jour
        if guild_id in self.update_tasks:
            self.update_tasks[guild_id].cancel()
            del self.update_tasks[guild_id]

        text_channel = getattr(player, 'text_channel', None)

        # Supprimer l'ancien message
        if guild_id in self.now_playing_messages and text_channel:
            try:
                old_message = await text_channel.fetch_message(self.now_playing_messages[guild_id])
                await old_message.delete()
            except (discord.NotFound, discord.HTTPException):
                pass
            del self.now_playing_messages[guild_id]

        # Jouer la piste suivante si disponible
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)
            if text_channel:
                await self.start_now_playing_ui(text_channel, next_track, player)

    @commands.command(name="jouer", aliases=['p', 'play'])
    async def jouer(self, ctx: commands.Context, *, recherche: str):
        """Joue une chanson ou l'ajoute à la file d'attente."""
        try:
            # Utiliser la fonction de connexion sécurisée
            player = await self.ensure_voice_connection(ctx)
            
            # Rechercher des pistes avec gestion d'erreur intelligente
            try:
                tracks = await wavelink.Playable.search(recherche)
            except Exception as e:
                # Basculer vers un autre serveur en cas d'erreur
                await self.node_manager.handle_node_failure(self.bot)
                try:
                    tracks = await wavelink.Playable.search(recherche)
                except:
                    return await ctx.send(f"❌ Erreur lors de la recherche. Réessayez dans quelques instants.")
            
            if not tracks:
                return await ctx.send(f"Aucun résultat trouvé pour `{recherche}`.")

            track = tracks[0]
            
            if not player.playing and player.queue.is_empty:
                await player.play(track)
                await self.start_now_playing_ui(ctx.channel, track, player)
            else:
                await player.queue.put_wait(track)
                await ctx.send(f"👍 Ajouté à la file d'attente : **{track.title}**")
                
        except discord.DiscordException as e:
            if "connexion" in str(e).lower() or "timeout" in str(e).lower():
                await ctx.send("❌ Problème de connexion au salon vocal. Vérifiez que je dispose des permissions nécessaires et réessayez.")
            else:
                await ctx.send(f"❌ Erreur : {str(e)}")
        except Exception as e:
            print(f"Erreur dans jouer: {e}")
            await ctx.send("❌ Une erreur inattendue s'est produite. Réessayez.")

    @commands.command(name="sauter", aliases=['skip'])
    async def sauter(self, ctx: commands.Context):
        """Passe à la chanson suivante."""
        player: wavelink.Player = ctx.voice_client
        if player and player.playing:
            await player.skip(force=True)
            await ctx.message.add_reaction('👍')
        else:
            await ctx.send("Aucune musique en cours de lecture.")

    @commands.command(name="arreter", aliases=['stop'])
    async def arreter(self, ctx: commands.Context):
        """Arrête la musique et déconnecte le bot."""
        player: wavelink.Player = ctx.voice_client
        if player:
            guild_id = ctx.guild.id
            
            # Arrêter la tâche de mise à jour
            if guild_id in self.update_tasks:
                self.update_tasks[guild_id].cancel()
                del self.update_tasks[guild_id]
            
            # Déconnexion forcée pour éviter les problèmes
            await player.disconnect(force=True)
            
            text_channel = getattr(player, 'text_channel', ctx.channel)
            # Nettoyer le message
            if guild_id in self.now_playing_messages:
                try:
                    if text_channel:
                        old_message = await text_channel.fetch_message(self.now_playing_messages[guild_id])
                        await old_message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
                del self.now_playing_messages[guild_id]
            
            await ctx.send("⏹️ Déconnecté.")
        else:
            await ctx.send("Le bot n'est pas connecté à un canal vocal.")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Met en pause ou reprend la lecture."""
        player: wavelink.Player = ctx.voice_client
        if not player:
            return await ctx.send("Le bot n'est pas connecté à un canal vocal.")
        
        if player.paused:
            await player.pause(False)
            await ctx.send("▶️ Lecture reprise.")
        else:
            await player.pause(True)
            await ctx.send("⏸️ Lecture mise en pause.")

    @commands.command(name="volume", aliases=['vol'])
    async def volume(self, ctx: commands.Context, volume: int = None):
        """Règle le volume (0-100)."""
        player: wavelink.Player = ctx.voice_client
        if not player:
            return await ctx.send("Le bot n'est pas connecté à un canal vocal.")
        
        if volume is None:
            return await ctx.send(f"Volume actuel : {player.volume}%")
        
        if volume < 0 or volume > 100:
            return await ctx.send("Le volume doit être entre 0 et 100.")
        
        await player.set_volume(volume)
        await ctx.send(f"🔊 Volume réglé à {volume}%")

    @commands.command(name="queue", aliases=['q'])
    async def queue(self, ctx: commands.Context):
        """Affiche la file d'attente."""
        player: wavelink.Player = ctx.voice_client
        if not player:
            return await ctx.send("Le bot n'est pas connecté à un canal vocal.")
        
        embed = discord.Embed(title="File d'attente", color=0x00ff00)
        
        if player.current:
            embed.add_field(
                name="🎵 Lecture en cours", 
                value=f"**{player.current.title}** par {player.current.author}", 
                inline=False
            )
        
        if not player.queue.is_empty:
            queue_text = ""
            for i, track in enumerate(player.queue, start=1):
                queue_text += f"{i}. **{track.title}** par {track.author}\n"
                if i >= 10:
                    remaining = len(player.queue) - 10
                    queue_text += f"... et {remaining} autre{'s' if remaining > 1 else ''}."
                    break
            embed.add_field(name="⏭️ À venir", value=queue_text, inline=False)
        else:
            if not player.current:
                embed.description = "La file d'attente est vide."
            else:
                embed.add_field(name="⏭️ À venir", value="Aucune chanson en attente.", inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="clear")
    async def clear_queue(self, ctx: commands.Context):
        """Vide la file d'attente."""
        player: wavelink.Player = ctx.voice_client
        if not player:
            return await ctx.send("Le bot n'est pas connecté à un canal vocal.")
        
        if player.queue.is_empty:
            return await ctx.send("La file d'attente est déjà vide.")
        
        player.queue.clear()
        await ctx.send("🗑️ File d'attente vidée.")

    @commands.command(name="reconnect", aliases=['reconnexion'])
    async def reconnect(self, ctx: commands.Context):
        """Reconnecte le bot au salon vocal en cas de problème."""
        if not ctx.author.voice:
            return await ctx.send("Vous devez être dans un salon vocal pour utiliser cette commande.")
        
        # Forcer la déconnexion si connecté
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            await asyncio.sleep(2)
        
        try:
            player = await self.safe_voice_connect(ctx.author.voice.channel)
            setattr(player, 'text_channel', ctx.channel)
            await ctx.send("✅ Reconnexion réussie !")
        except Exception as e:
            await ctx.send(f"❌ Échec de la reconnexion : {str(e)}")

    @commands.command(name="servers", aliases=['serveurs'])
    async def servers_status(self, ctx: commands.Context):
        """Affiche l'état des serveurs Lavalink."""
        embed = discord.Embed(title="🖥️ État des serveurs Lavalink", color=0x00ff00)
        
        # Tester rapidement les serveurs
        await self.node_manager.find_best_nodes()
        
        primary_text = ""
        backup_text = ""
        offline_text = ""
        
        for node in self.node_manager.nodes:
            status_icon = "🟢" if node.is_available else "🔴"
            latency_text = f"{node.latency:.0f}ms" if node.is_available else "Offline"
            node_info = f"{status_icon} **{node.name}** - {latency_text} ({node.region})\n"
            
            if node == self.node_manager.primary_node:
                primary_text = f"🎯 **Principal:** {node_info}"
            elif node in self.node_manager.fallback_nodes:
                backup_text += node_info
            elif not node.is_available:
                offline_text += node_info
        
        if primary_text:
            embed.add_field(name="Serveur Actuel", value=primary_text, inline=False)
        if backup_text:
            embed.add_field(name="Serveurs de Backup", value=backup_text, inline=False)
        if offline_text:
            embed.add_field(name="Serveurs Hors Ligne", value=offline_text, inline=False)
        
        # Ajouter des statistiques de connexion
        connection_stats = ""
        for guild_id, retries in self.connection_retries.items():
            if retries > 0:
                guild = self.bot.get_guild(guild_id)
                guild_name = guild.name if guild else f"Serveur {guild_id}"
                connection_stats += f"• {guild_name}: {retries} échec(s)\n"
        
        if connection_stats:
            embed.add_field(name="Problèmes de Connexion", value=connection_stats, inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="paroles", aliases=['lyrics'])
    async def paroles(self, ctx: commands.Context, *, requete: str = None):
        """Affiche les paroles d'une chanson."""
        artist = None
        title = None

        if requete is None:
            player: wavelink.Player = ctx.voice_client
            if not (player and player.current):
                return await ctx.send("Veuillez spécifier une chanson ou lancer une lecture pour que je trouve les paroles.")
            title = player.current.title
            artist = player.current.author
        else:
            try:
                artist, title = requete.split(" - ", 1)
            except ValueError:
                return await ctx.send("Veuillez utiliser le format `Artiste - Titre` pour votre recherche.")
        
        artist = artist.strip()
        title = title.strip()

        await ctx.send(f"🔍 Recherche des paroles pour **{title}** par **{artist}**...")

        url = f"https://api.lyrics.ovh/v1/{artist}/{title}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    lyrics = data.get("lyrics")
                    if lyrics:
                        if len(lyrics) > 4000:
                            lyrics = lyrics[:4000] + "\n\n[Paroles tronquées...]"
                        
                        embed = discord.Embed(title=f"Paroles de {title}", description=lyrics, color=0x00ff00)
                        embed.set_author(name=artist)
                        await ctx.send(embed=embed)
                    else:
                        await ctx.send(f"Désolé, je n'ai pas trouvé les paroles pour **{title}** par **{artist}**.")
                else:
                    await ctx.send(f"Désolé, je n'ai pas trouvé les paroles pour **{title}** par **{artist}**.")

    @commands.group(name="playlist", invoke_without_command=True)
    async def playlist(self, ctx: commands.Context):
        """Gère les playlists. Affiche l'aide si aucune sous-commande n'est donnée."""
        await ctx.send_help(ctx.command)

    @playlist.command(name="create")
    async def playlist_create(self, ctx: commands.Context, *, name: str):
        """Crée une nouvelle playlist."""
        user_id = ctx.author.id
        if user_id not in self.playlists:
            self.playlists[user_id] = {}
        
        if name in self.playlists[user_id]:
            return await ctx.send(f"La playlist `{name}` existe déjà.")
            
        self.playlists[user_id][name] = []
        self._save_playlists()
        await ctx.send(f"✅ Playlist `{name}` créée avec succès.")

    @playlist.command(name="add")
    async def playlist_add(self, ctx: commands.Context, playlist_name: str, *, song_query: str):
        """Ajoute une chanson à une playlist."""
        user_id = ctx.author.id
        if user_id not in self.playlists or playlist_name not in self.playlists[user_id]:
            return await ctx.send(f"La playlist `{playlist_name}` n'existe pas. Créez-la avec `&playlist create {playlist_name}`.")

        tracks = await wavelink.Playable.search(song_query)
        if not tracks:
            return await ctx.send(f"Aucun résultat trouvé pour `{song_query}`.")
        
        track = tracks[0]
        song_data = {"title": track.title, "author": track.author, "uri": track.uri}
        
        self.playlists[user_id][playlist_name].append(song_data)
        self._save_playlists()
        await ctx.send(f"👍 Ajouté **{track.title}** à la playlist `{playlist_name}`.")

    @playlist.command(name="list")
    async def playlist_list(self, ctx: commands.Context):
        """Affiche vos playlists."""
        user_id = ctx.author.id
        if user_id not in self.playlists or not self.playlists[user_id]:
            return await ctx.send("Vous n'avez aucune playlist.")
            
        embed = discord.Embed(title=f"Playlists de {ctx.author.name}", color=0x00ff00)
        description = ""
        for name, songs in self.playlists[user_id].items():
            description += f"• **{name}** ({len(songs)} chanson(s))\n"
        embed.description = description
        await ctx.send(embed=embed)

    @playlist.command(name="show")
    async def playlist_show(self, ctx: commands.Context, *, name: str):
        """Affiche le contenu d'une playlist."""
        user_id = ctx.author.id
        if user_id not in self.playlists or name not in self.playlists[user_id]:
            return await ctx.send(f"La playlist `{name}` n'existe pas.")
        
        playlist_songs = self.playlists[user_id][name]
        if not playlist_songs:
            return await ctx.send(f"La playlist `{name}` est vide.")
            
        embed = discord.Embed(title=f"Contenu de la playlist : {name}", color=0x00ff00)
        description = ""
        for i, song in enumerate(playlist_songs, 1):
            description += f"`{i}.` **{song['title']}**\n"
            if i >= 20:
                description += f"\n... et {len(playlist_songs) - 20} autre(s)."
                break
        embed.description = description
        await ctx.send(embed=embed)

    @playlist.command(name="load")
    async def playlist_load(self, ctx: commands.Context, *, name: str):
        """Charge une playlist dans la file d'attente."""
        user_id = ctx.author.id
        if user_id not in self.playlists or name not in self.playlists[user_id]:
            return await ctx.send(f"La playlist `{name}` n'existe pas.")
        
        try:
            # Utiliser la fonction de connexion sécurisée
            player = await self.ensure_voice_connection(ctx)
            
            playlist_songs = self.playlists[user_id][name]
            if not playlist_songs:
                return await ctx.send(f"La playlist `{name}` est vide.")
                
            msg = await ctx.send(f"Chargement de la playlist `{name}`...")
            count = 0
            for song in playlist_songs:
                try:
                    track = await wavelink.Playable.search(song['uri'], source=wavelink.TrackSource.YouTube)
                    if track:
                        await player.queue.put_wait(track[0])
                        if not player.playing:
                            await player.play(player.queue.get())
                        count += 1
                except Exception:
                    pass 
            
            await msg.edit(content=f"✅ Ajouté {count}/{len(playlist_songs)} chanson(s) de la playlist `{name}` à la file d'attente.")
            
        except discord.DiscordException as e:
            await ctx.send("❌ Problème de connexion au salon vocal. Réessayez.")
        except Exception as e:
            await ctx.send("❌ Erreur lors du chargement de la playlist.")

    @playlist.command(name="delete")
    async def playlist_delete(self, ctx: commands.Context, *, name: str):
        """Supprime une playlist."""
        user_id = ctx.author.id
        if user_id not in self.playlists or name not in self.playlists[user_id]:
            return await ctx.send(f"La playlist `{name}` n'existe pas.")
            
        del self.playlists[user_id][name]
        self._save_playlists()
        await ctx.send(f"🗑️ Playlist `{name}` supprimée.")

    @playlist.command(name="remove")
    async def playlist_remove(self, ctx: commands.Context, playlist_name: str, index: int):
        """Supprime une chanson d'une playlist par son numéro."""
        user_id = ctx.author.id
        if user_id not in self.playlists or playlist_name not in self.playlists[user_id]:
            return await ctx.send(f"La playlist `{playlist_name}` n'existe pas.")
        
        playlist = self.playlists[user_id][playlist_name]
        if not 1 <= index <= len(playlist):
            return await ctx.send(f"Numéro de chanson invalide. La playlist `{playlist_name}` a {len(playlist)} chansons.")
            
        removed_song = playlist.pop(index - 1)
        self._save_playlists()
        await ctx.send(f"👍 Supprimé **{removed_song['title']}** de la playlist `{playlist_name}`.")


class CustomHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs={
            'help': 'Affiche ce message d\'aide.'
        })

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Aide du Bot", description="Voici la liste des commandes disponibles.", color=0x00ff00)
        
        for cog, commands_list in mapping.items():
            cog_name = getattr(cog, "qualified_name", "Sans Catégorie")
            filtered_commands = await self.filter_commands(commands_list, sort=True)
            if filtered_commands:
                command_signatures = [f"`{self.context.prefix}{c.name}`" for c in filtered_commands]
                if command_signatures:
                    embed.add_field(name=cog_name, value=" ".join(command_signatures), inline=False)

        embed.set_footer(text=f"Utilisez {self.context.prefix}help <commande> pour plus d'infos.")
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=f"`{self.context.prefix}{command.name}`", description=command.help or "Pas de description.", color=0x00ff00)
        
        if command.aliases:
            embed.add_field(name="Alias", value=", ".join(f"`{alias}`" for alias in command.aliases), inline=False)
            
        usage = f"`{self.context.prefix}{command.name} {command.signature}`"
        embed.add_field(name="Utilisation", value=usage, inline=False)
        
        await self.get_destination().send(embed=embed)
        
    async def send_cog_help(self, cog):
        embed = discord.Embed(title=f"Catégorie : `{cog.qualified_name}`", description=cog.description or "", color=0x00ff00)

        filtered_commands = await self.filter_commands(cog.get_commands(), sort=True)
        for command in filtered_commands:
            embed.add_field(name=f"`{self.context.prefix}{command.name}`", value=command.help or "Pas de description.", inline=True)
        
        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error):
        embed = discord.Embed(title="Erreur", description=error, color=discord.Color.red())
        await self.get_destination().send(embed=embed)


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        super().__init__(
            command_prefix='&', 
            intents=intents, 
            help_command=CustomHelpCommand(),
            # Ajout de paramètres pour améliorer la stabilité
            heartbeat_timeout=60.0,
            guild_ready_timeout=5.0
        )
        self.node_manager = IntelligentNodeManager()

    async def setup_hook(self) -> None:
        """Hook d'initialisation pour connecter Lavalink et charger les Cogs."""
        # Trouver et connecter aux meilleurs serveurs
        await self.node_manager.find_best_nodes()
        success = await self.node_manager.connect_nodes(self)
        
        if not success:
            print("❌ Impossible de se connecter aux serveurs Lavalink!")
            return
        
        # Ajouter le cog de musique
        await self.add_cog(MusicCog(self))
        print("✅ MusicCog chargé avec succès!")
        
        # Démarrer le monitoring
        self.node_manager.monitoring_task = asyncio.create_task(
            self.node_manager.start_monitoring(self)
        )

    async def on_ready(self):
        print(f'🎵 Bot connecté en tant que {self.user}')
        print(f'ID: {self.user.id}')
        print('🧠 Système d\'optimisation intelligente activé!')
        print('🔧 Système anti-timeout amélioré activé!')
        print('Prêt à jouer de la musique avec reconnexion automatique!')

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """Événement déclenché quand un nœud Lavalink est prêt."""
        print(f'🔗 Nœud Lavalink {payload.node.identifier} connecté et prêt!')

    async def on_voice_state_update(self, member, before, after):
        """Gère les déconnexions inattendues du bot."""
        if member == self.user:
            # Le bot a été déconnecté
            if before.channel and not after.channel:
                print(f"⚠️ Bot déconnecté du salon {before.channel.name} dans {before.channel.guild.name}")
                
                # Nettoyer les tâches et messages pour ce serveur
                music_cog = self.get_cog("Musique")
                if music_cog:
                    guild_id = before.channel.guild.id
                    
                    # Arrêter les tâches de mise à jour
                    if guild_id in music_cog.update_tasks:
                        music_cog.update_tasks[guild_id].cancel()
                        del music_cog.update_tasks[guild_id]
                    
                    # Supprimer les messages "now playing"
                    if guild_id in music_cog.now_playing_messages:
                        del music_cog.now_playing_messages[guild_id]
                    
                    # Annuler les timers de déconnexion
                    if guild_id in music_cog.disconnect_timers:
                        music_cog.disconnect_timers[guild_id].cancel()
                        del music_cog.disconnect_timers[guild_id]

    async def close(self):
        """Nettoyage lors de la fermeture du bot."""
        if self.node_manager.monitoring_task:
            self.node_manager.monitoring_task.cancel()
        await super().close()

if __name__ == "__main__":
    # Configuration du logging pour diagnostiquer les problèmes
    logging.basicConfig(
        level=logging.WARNING,  # Réduire le spam de logs
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Désactiver les logs Discord trop verbeux
    logging.getLogger('discord').setLevel(logging.ERROR)
    logging.getLogger('wavelink').setLevel(logging.ERROR)
    
    bot = MusicBot()
    bot.run(TOKEN)