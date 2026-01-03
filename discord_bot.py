import time
from datetime import timedelta
from collections import defaultdict, deque

import discord # Import základní knihovny discord.py
from discord.ext import commands # Import třídy commands z discord.ext.commands pro práci s příkazy a bota
import asyncio # Import knihovny asyncio pro asynchronní programování (např. čekání na události)
from scheduler import hourly_clan_update # Import funkce pro hodinovou aktualizaci členů klanu
from bot_commands import VerifikacniView, ConfirmView # Import funkcí a tříd pro nastavení příkazů a ověřovacího pohledu
from mod_commands import setup_mod_commands # Import funkcí pro nastavení moderátorských příkazů
from database import fetch_pending_warnings, WarningReviewView
from constants import TOWN_HALL_EMOJIS, LEAGUE_EMOJIS, LOG_CHANNEL_ID
import media_downloader
import web_server

VERIFICATION_PATH = "verification_data.json" # Definování konstanty s cestou k souboru, kde se ukládá info o zprávě pro verifikaci





class MyBot(commands.Bot):
    def __init__(self, command_prefix, intents, guild_id, clan_tag, config):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.guild_object = discord.Object(id=guild_id)
        self.clan_tag = clan_tag
        self.config = config
        # Proti-spam monitor: user_id -> deque časových razítek
        self.message_history = defaultdict(lambda: deque(maxlen=10))
        self.timeout_levels = defaultdict(int)  # user_id -> počet porušení
        self.failed_timeout_cache = set()  # user_id -> kdo již selhal s timeoutem
        self.log_channel_id = LOG_CHANNEL_ID

    async def setup_hook(self):
        # Načti globální příkazy
        await self.load_extension("global_commands")

        # Načti moderátorské příkazy (ty zůstanou pouze pro tvůj server)
        await setup_mod_commands(self)

        # Synchronizuj globální příkazy
        try:
            global_commands = await self.tree.sync()
            print(f"🌐 [sync] Globálně synchronizováno {len(global_commands)} příkaz(ů)")
        except Exception as e:
            print(f"❌ [sync] Chyba globálního sync: {e}")

        # Synchronizuj guild-specific příkazy
        try:
            guild = discord.Object(id=self.config["GUILD_ID"])
            guild_commands = await self.tree.sync(guild=guild)
            print(f"🏠 [sync] Serverově synchronizováno {len(guild_commands)} příkaz(ů)")
        except Exception as e:
            print(f"❌ [sync] Chyba guild sync: {e}")

        # Obnovení persistentních views pro varování
        try:
            pending_warnings = fetch_pending_warnings()
            for pw in pending_warnings:
                view = WarningReviewView(
                    coc_tag=pw['coc_tag'],
                    coc_name=pw['coc_name'],
                    date_time=pw['date_time'],
                    reason=pw['reason']
                )
                self.add_view(view, message_id=pw['message_id'])
            
            if pending_warnings:
                print(f"🔄 [setup_hook] Obnoveno {len(pending_warnings)} čekajících návrhů varování.")
        except Exception as e:
            print(f"❌ [setup_hook] Chyba při obnově varování: {e}")

    async def on_ready(self):
        print(f"✅🤖 Přihlášen jako {self.user}")

        # ⬇️ Připojíme reálný Guild objekt
        self.guild_object = self.get_guild(self.config["GUILD_ID"])
        if self.guild_object is None:
            print(f"❌ [bot] Guild s ID {self.config['GUILD_ID']} nebyla nalezena.")
        else:
            print(f"✅ [bot] Připojen k serveru: {self.guild_object.name}")

        # Kontrola, jestli už byl bot inicializován
        if getattr(self, "_initialized", False):
            print("⚠️ [bot] Opětovné připojení zjištěno — inicializační rutiny přeskočeny.")
            return

        self._initialized = True
        self.add_view(VerifikacniView())

        asyncio.create_task(hourly_clan_update(self.config, self))
        # Web server se nyní spouští automaticky (on-demand) při přidání souboru
        print("✅ [bot] Inicializační rutiny spuštěny (View + scheduler).")

    async def on_message(self, message):
        if message.author.bot:
            return

        # Detekce DM (Private Channel)
        if not message.guild:
            url = media_downloader.extract_url(message.content)
            if url:
                await self.handle_media_download(message, url)
            return

        if not message.guild:
            return

        now = time.time()
        user_id = message.author.id

        self.message_history[user_id].append(now)
        timestamps = self.message_history[user_id]

        # Kontrola 10 zpráv v 5 sekundách
        if len(timestamps) == 10 and timestamps[-1] - timestamps[0] <= 5:
            self.timeout_levels[user_id] += 1
            timeout_minutes = min(60, 1 * (2 ** (self.timeout_levels[user_id] - 1)))

            try:
                await message.author.timeout(timedelta(minutes=timeout_minutes), reason="Anti-spam ochrana")
                await message.channel.send(f"{message.author.mention} byl automaticky umlčen na {timeout_minutes} min. za spam.")
                print(f"⚠️ [antispam] {message.author} timeout na {timeout_minutes} min (level {self.timeout_levels[user_id]})")
                if user_id in self.failed_timeout_cache:
                    self.failed_timeout_cache.remove(user_id)
            except Exception as e:
                if user_id not in self.failed_timeout_cache:
                    print(f"❌ [antispam] Nepodařilo se umlčet {message.author}: {e}")
                    self.failed_timeout_cache.add(user_id)

                    # Log do logovacího kanálu
                    log_channel = self.get_channel(self.log_channel_id)
                    if log_channel:
                        await log_channel.send(f"❌ Nepodařilo se umlčet {message.author.mention} (`{message.author.id}`): `{str(e)}`")

        await self.process_commands(message)

    async def potvrdit_hrace(self, interaction, player):
        embed = discord.Embed(
            title=f"{player['name']} ({player['tag']})",
            color=discord.Color.green()
        )

        trophies = player.get("trophies", "?")
        townhall_level = player.get("townHallLevel", "?")
        league = player.get("league", "Neznámá liga")
        role = player.get("role", "member")

        embed.add_field(name="🏆 Trofeje", value=f"{trophies}", inline=True)
        league_key = f"league_{league.split()[0].lower().replace('.', '')}"
        embed.add_field(name="🏅 Liga", value=f"{league} {LEAGUE_EMOJIS.get(league_key, '')}", inline=True)
        embed.add_field(name="👑 Role v klanu", value=f"{role}", inline=True)
        embed.add_field(name="🏰 Town Hall lvl", value=f"{townhall_level} {TOWN_HALL_EMOJIS.get(townhall_level)}",
                        inline=True)

        embed.set_footer(text="Klikni na ✅ pro potvrzení")

        view = ConfirmView(player, interaction.user, self)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.message = msg
        await asyncio.sleep(30)
        await msg.delete()

    async def handle_media_download(self, message, url):
        status_msg = await message.channel.send("Zahajuji stahování... ⏳")
        
        loop = asyncio.get_running_loop()
        # Spustíme blokující stahování v exekutoru
        result = await loop.run_in_executor(None, media_downloader.download_media, url)
        
        if "error" in result:
            await status_msg.edit(content=f"❌ Chyba při stahování: {result['error']}")
            return
            
        # Zkontrolujeme velikost (Discord limit cca 10MB pro free, více pro Nitro/Boost)
        SAFE_LIMIT_MB = 10
        
        embed = discord.Embed(title="Stažení dokončeno", color=discord.Color.blue())
        embed.add_field(name="Název", value=result['title'], inline=False)
        embed.add_field(name="Autor", value=result['uploader'], inline=True)
        if result['duration']:
            minutes, seconds = divmod(result['duration'], 60)
            embed.add_field(name="Délka", value=f"{int(minutes)}:{int(seconds):02d}", inline=True)
        embed.add_field(name="Rozlišení", value=result['resolution'], inline=True)
        embed.add_field(name="Velikost", value=f"{result['filesize_mb']} MB", inline=True)

        if result['filesize_mb'] > SAFE_LIMIT_MB:
            # Soubor je příliš velký -> web server
            key = await web_server.add_file(result['filename'])
            download_url = f"https://discordvids.420013.xyz/videa-z-discordu/{key}"
            
            embed.add_field(name="Odkaz ke stažení", value=f"[Klikni pro stažení]({download_url})", inline=False)
            embed.set_footer(text="⚠️ Soubor je příliš velký pro Discord. Odkaz je platný 24h.")
            
            try:
                await status_msg.delete()
                await message.channel.send(embed=embed)
            except Exception as e:
                await message.channel.send(f"❌ Chyba při odesílání odkazu: {e}")
            # NEMAZAT soubor, web server ho potřebuje
            
        else:
            # Soubor je malý -> poslat přímo
            file = discord.File(result['filename'])
            try:
                await status_msg.delete()
                # 1. zpráva: Samotné video
                await message.channel.send(file=file)
                # 2. zpráva: Statistiky (embed) pod tím
                await message.channel.send(embed=embed)
            except Exception as e:
                await message.channel.send(f"❌ Chyba při odesílání souboru: {e}")
            finally:
                media_downloader.delete_file(result['filename'])


def start_bot(config): # Funkce pro spuštění bota
    intents = discord.Intents.default() # Vytvoříme defaultní intents
    intents.message_content = True # Povolení obsahu zpráv
    intents.members = True  # Povolení členů (pro role a ověřování)

    bot = MyBot( # Vytvoříme instanci bota
        command_prefix="/", # Prefix pro příkazy
        intents=intents, # Intents pro bota
        guild_id=config["GUILD_ID"], # ID serveru (guild)
        clan_tag=config["CLAN_TAG"], # Tag klanu pro API dotazy
        config=config # Konfigurace bota (tokeny atd.
    )
    bot.run(config["DISCORD_BOT_TOKEN"]) # Spustí bota s tokenem