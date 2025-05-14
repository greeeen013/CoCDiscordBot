import time
from datetime import timedelta
from collections import defaultdict, deque

import discord # Import základní knihovny discord.py
from discord.ext import commands # Import třídy commands z discord.ext.commands pro práci s příkazy a bota
import asyncio # Import knihovny asyncio pro asynchronní programování (např. čekání na události)
from scheduler import hourly_clan_update # Import funkce pro hodinovou aktualizaci členů klanu
from bot_commands import setup_commands, VerifikacniView, ConfirmView # Import funkcí a tříd pro nastavení příkazů a ověřovacího pohledu
from mod_commands import setup_mod_commands # Import funkcí pro nastavení moderátorských příkazů

VERIFICATION_PATH = "verification_data.json" # Definování konstanty s cestou k souboru, kde se ukládá info o zprávě pro verifikaci
TOWN_HALL_EMOJIS = {
    17: "<:town_hall_17:1372327905882935467>",
    16: "<:town_hall_16:1372327703264497745>",
    15: "<:town_hall_15:1372327513975427183>",
    14: "<:town_hall_14:1372327272979103896>",
    13: "<:town_hall_13:1372259972053991434>",
    12: "<:town_hall_12:1372259837391405076>",
    11: "<:town_hall_11:1372259715840606449>",
    10: "<:town_hall_10:1372259547825307741>",
    9: "<:town_hall_9:1372259396842946671>",
    8: "<:town_hall_8:1372259356376170588>",
    7: "<:town_hall_7:1372259219302121522>"
} # Definování emoji pro jednotlivé úrovně Town Hall (TH) v Clash of Clans
LEAGUES = {
    "Bronze League": "<:league_bronze:1365740648820637807>",
    "Silver League": "<:league_silver:1365740647247646870>",
    "Gold League": "<:league_gold:1365740651898998824>",
    "Crystal League": "<:league_crystal:1365740653253754930>",
    "Master League": "<:league_master:1365740645355884764>",
    "Champion League": "<:league_champion:1365740643439214683>",
    "Titan League": "<:league_titan:1365740641765691412>",
    "Legend League": "<:league_legend:1365740639895158886>",
    "Unranked": "<:league_unranked:1365740650351558787>",
} # Definování emoji pro jednotlivé ligy v Clash of Clans


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
        self.log_channel_id = 1371089891621998652

    async def setup_hook(self):
        await setup_commands(self)
        await setup_mod_commands(self)

        try:
            synced = await self.tree.sync(guild=self.guild_object)
            print(f"✅ [bot_commands] Synchronizováno {len(synced)} příkaz(ů) se serverem {self.guild_object.id}")
        except Exception as e:
            print(f"❌ [bot_commands] Chyba při synchronizaci příkazů: {e}")

    async def on_ready(self):
        print(f"✅🤖 Přihlášen jako {self.user}")
        self.add_view(VerifikacniView())
        asyncio.create_task(hourly_clan_update(self.config, self))

    async def on_ready(self):
        print(f"✅🤖 Přihlášen jako {self.user}")
        self.add_view(VerifikacniView())
        asyncio.create_task(hourly_clan_update(self.config, self))

    async def on_message(self, message):
        if message.author.bot or not message.guild:
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
        embed.add_field(name="🏅 Liga", value=f"{league} {LEAGUES.get(' '.join(league.split()[:2]))}", inline=True)
        embed.add_field(name="👑 Role v klanu", value=f"{role}", inline=True)
        embed.add_field(name="🏰 Town Hall lvl", value=f"{townhall_level} {TOWN_HALL_EMOJIS.get(townhall_level)}",
                        inline=True)

        embed.set_footer(text="Klikni na ✅ pro potvrzení")

        view = ConfirmView(player, interaction.user, self)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.message = msg
        await asyncio.sleep(30)
        await msg.delete()


def start_bot(config):
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = MyBot(
        command_prefix="/",
        intents=intents,
        guild_id=config["GUILD_ID"],
        clan_tag=config["CLAN_TAG"],
        config=config
    )
    bot.run(config["DISCORD_BOT_TOKEN"])

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