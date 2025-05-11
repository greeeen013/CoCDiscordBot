import discord # Import základní knihovny discord.py
from discord import app_commands
from discord.ext import commands # Import třídy commands z discord.ext.commands pro práci s příkazy a bota
import asyncio # Import knihovny asyncio pro asynchronní programování (např. čekání na události)
from scheduler import hourly_clan_update # Import funkce pro hodinovou aktualizaci členů klanu
from database import get_all_members, get_all_links # Import funkce, která načítá všechny hráče z databáze
from verification import start_verification_permission  # Importuj funkci ze souboru verification.py
from role_giver import update_roles # Import funkce pro získání mapování mezi Discord ID a tagy hráčů
from bot_commands import setup_commands, VerifikacniView, ConfirmView # Import funkcí a tříd pro nastavení příkazů a ověřovacího pohledu
from mod_commands import setup_mod_commands # Import funkcí pro nastavení moderátorských příkazů
from database import WarningReviewView  # nebo odkud tu třídu máš

VERIFICATION_PATH = "verification_data.json" # Definování konstanty s cestou k souboru, kde se ukládá info o zprávě pro verifikaci
TOWN_HALL_EMOJIS = {
    17: "<:town_hall_17:1365445408096129165>",
    16: "<:town_hall_16:1365445406854615143>",
    15: "<:town_hall_15:1365445404467925032>",
    14: "<:town_hall_14:1365445402463043664>",
    13: "<:town_hall_13:1365445400177147925>",
    12: "<:town_hall_12:1365445398411477082>",
    11: "<:town_hall_11:1365445395173347458>",
    10: "<:town_hall_10:1365445393680437369>",
    # atd...
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