import discord
from discord.ext import commands
import wavelink
import os
import asyncio
import time
import aiohttp
import logging
import json
import sys

# --- Configuration ---
# Le token est injecté par le Bot Manager via la variable d'environnement DISCORD_TOKEN
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("❌ ERREUR: Aucun token Discord trouvé dans les variables d'environnement.")
    print("   Assurez-vous que le Bot Manager lance ce script correctement.")
    sys.exit(1)

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
        print("🔍 Test des serveurs Lavalink...")
        tasks = [self.test_node_latency(node) for node in self.nodes]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        available_nodes = [node for node in self.nodes if node.is_available]
        available_nodes.sort(key=lambda x: x.latency)
        
        if available_nodes:
            self.primary_node = available_nodes[0]
            self.fallback_nodes = available_nodes[1:4]
            print(f"✅ Serveur principal: {self.primary_node.name} ({self.primary_node.latency:.0f}ms)")
        else:
            print("❌ Aucun serveur Lavalink disponible!")

    async def connect_nodes(self, client):
        if not self.primary_node:
            return False

        try:
            nodes_to_connect = [self.primary_node] + self.fallback_nodes
            wavelink_nodes = []
            
            for node in nodes_to_connect:
                wavelink_nodes.append(wavelink.Node(
                    identifier=node.name,
                    uri=node.uri,
                    password=node.password
                ))
            
            await wavelink.Pool.connect(client=client, nodes=wavelink_nodes)
            return True
        except Exception as e:
            print(f"❌ Erreur connexion: {e}")
            return False

    async def start_monitoring(self, bot):
        while True:
            try:
                await asyncio.sleep(60)
                if self.primary_node:
                    is_healthy = await self.test_node_latency(self.primary_node)
                    if not is_healthy:
                        print(f"⚠️ Nœud principal {self.primary_node.name} indisponible!")
                        await self.handle_node_failure(bot)
            except Exception as e:
                print(f"Erreur monitoring: {e}")

    async def handle_node_failure(self, bot):
        try:
            await self.find_best_nodes()
            if self.primary_node:
                print(f"🔄 Basculement vers {self.primary_node.name}")
        except Exception as e:
            print(f"Erreur lors du basculement: {e}")

class VoiceChannelCheckFailure(commands.CheckFailure): pass
class NotInVoiceChannel(VoiceChannelCheckFailure): pass
class NotInSameVoiceChannel(VoiceChannelCheckFailure): pass

class MusicCog(commands.Cog, name="Musique"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.now_playing_messages = {}
        self.update_tasks = {}
        self.node_manager = bot.node_manager
        self.disconnect_timers = {}
        self.connection_retries = {}

    async def safe_voice_connect(self, channel, timeout=30.0, retries=3):
        guild_id = channel.guild.id
        for attempt in range(retries):
            try:
                print(f"🔌 Tentative de connexion {attempt + 1}/{retries} au salon {channel.name}")
                current_timeout = timeout + (attempt * 10)
                
                if channel.guild.voice_client:
                    await channel.guild.voice_client.disconnect(force=True)
                    await asyncio.sleep(2)
                
                player = await channel.connect(cls=wavelink.Player, timeout=current_timeout, reconnect=True)
                print(f"✅ Connecté avec succès au salon {channel.name}")
                
                if guild_id in self.connection_retries:
                    del self.connection_retries[guild_id]
                return player
                
            except Exception as e:
                print(f"❌ Erreur connexion (tentative {attempt + 1}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(3)
        
        self.connection_retries[guild_id] = self.connection_retries.get(guild_id, 0) + 1
        if self.connection_retries[guild_id] >= 3:
            await self.node_manager.handle_node_failure(self.bot)
            self.connection_retries[guild_id] = 0
        
        raise discord.DiscordException("Impossible de se connecter au salon vocal.")

    async def ensure_voice_connection(self, ctx):
        player = ctx.voice_client
        if player and player.is_connected():
            if player.channel == ctx.author.voice.channel:
                return player
            else:
                await player.disconnect()
                player = None
        
        if not player:
            player = await self.safe_voice_connect(ctx.author.voice.channel)
            setattr(player, 'text_channel', ctx.channel)
        
        return player

    @commands.command(name="jouer", aliases=['p', 'play'])
    async def jouer(self, ctx: commands.Context, *, recherche: str):
        try:
            if not ctx.author.voice:
                return await ctx.send("❌ Vous devez être dans un salon vocal.")

            player = await self.ensure_voice_connection(ctx)
            
            try:
                tracks = await wavelink.Playable.search(recherche)
            except Exception as e:
                print(f"Erreur recherche: {e}")
                await self.node_manager.handle_node_failure(self.bot)
                try:
                    tracks = await wavelink.Playable.search(recherche)
                except:
                    return await ctx.send(f"❌ Erreur lors de la recherche. Les serveurs de musique sont peut-être surchargés.")
            
            if not tracks:
                return await ctx.send(f"Aucun résultat trouvé pour `{recherche}`.")

            track = tracks[0]
            
            if not player.playing and player.queue.is_empty:
                await player.play(track)
                await ctx.send(f"▶️ Lecture de **{track.title}**")
            else:
                await player.queue.put_wait(track)
                await ctx.send(f"👍 Ajouté à la file d'attente : **{track.title}**")
                
        except Exception as e:
            print(f"Erreur dans jouer: {e}")
            await ctx.send(f"❌ Erreur : {str(e)}")

    @commands.command(name="arreter", aliases=['stop', 'leave'])
    async def arreter(self, ctx: commands.Context):
        player: wavelink.Player = ctx.voice_client
        if player:
            try:
                await player.disconnect(force=True)
                await ctx.send("⏹️ Déconnecté.")
            except Exception as e:
                print(f"Erreur déconnexion: {e}")
                # Force cleanup if wavelink fails
                if ctx.guild.voice_client:
                    await ctx.guild.voice_client.disconnect(force=True)
                await ctx.send("⏹️ Déconnecté (forcé).")
        else:
            await ctx.send("Le bot n'est pas connecté.")

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        super().__init__(command_prefix='&', intents=intents)
        self.node_manager = IntelligentNodeManager()

    async def setup_hook(self) -> None:
        await self.node_manager.find_best_nodes()
        success = await self.node_manager.connect_nodes(self)
        if not success:
            print("❌ Impossible de se connecter aux serveurs Lavalink!")
        await self.add_cog(MusicCog(self))

    async def on_ready(self):
        print(f'🎵 Bot connecté en tant que {self.user}')

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = MusicBot()
    bot.run(TOKEN)
