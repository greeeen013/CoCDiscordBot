import discord # Import základní knihovny discord.py
from discord import app_commands
from discord.ext import commands # Import třídy commands z discord.ext.commands pro práci s příkazy a bota
import asyncio # Import knihovny asyncio pro asynchronní programování (např. čekání na události)
from scheduler import hourly_clan_update # Import funkce pro hodinovou aktualizaci členů klanu
from database import get_all_members # Import funkce, která načítá všechny hráče z databáze

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
    9: "",
    8: "",
    7: "",
    6: "",
    5: "",
    4: "",
    3: "",
    2: "",
    1: "",
    # atd...
}

class ConfirmView(discord.ui.View): # Definice view (rozhraní s tlačítkem) pro potvrzení identity hráče
    def __init__(self, player, user, bot): # Konstruktor view – přijímá hráče, uživatele a instanci bota
        super().__init__(timeout=30) # timeout=30 sekund, po kterém tlačítko zmizí
        self.player = player # Data ověřovaného hráče
        self.user = user # Uživatel, který vybírá
        self.bot = bot # Instance bota
        self.result = False # Výsledek potvrzení (zda bylo potvrzeno)

    @discord.ui.button(label="✅ Potvrdit", style=discord.ButtonStyle.success) # Definice tlačítka v rámci view
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: # Ověříme, že tlačítko stiskl správný uživatel
            await interaction.response.send_message("❌ Toto tlačítko není pro tebe!", ephemeral=True)
            return
        self.result = True # Nastavíme výsledek na True, hráč potvrzen
        await interaction.response.send_message(f"✅ Ověřil ses jako {self.player['name']} ({self.player['tag']})!", ephemeral=True)
        self.stop() # Ukončí view, zmizí tlačítka

class SelectPlayerView(discord.ui.View): # View pro výběr hráče, pokud existuje více stejných jmen
    def __init__(self, candidates, user, bot, interaction):
        super().__init__(timeout=30) # View timeout za 30 sekund
        self.candidates = candidates # Seznam kandidátů (hráčů)
        self.user = user # Uživatel, který volí
        self.bot = bot # Instance bota
        self.interaction = interaction # Původní interakce (slash příkaz)

        emojis = ["1️⃣", "2️⃣", "3️⃣"] # Přiřadíme tlačítka ke každému hráči (max 3)
        for i, player in enumerate(candidates):
            self.add_item(PlayerSelectButton(index=i, emoji=emojis[i], view_parent=self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool: # Ověří, že na tlačítka kliká správný uživatel
        return interaction.user == self.user

class PlayerSelectButton(discord.ui.Button): # Samostatné tlačítko pro výběr hráče podle indexu
    def __init__(self, index, emoji, view_parent):
        super().__init__(label=str(index + 1), emoji=emoji, style=discord.ButtonStyle.primary, custom_id=str(index))
        self.index = index # Index kandidáta v seznamu
        self.view_parent = view_parent # Reference na rodičovské view

    async def callback(self, interaction: discord.Interaction): # Callback, co se stane po kliknutí
        if interaction.user != self.view_parent.user: # Ověří, že kliká správný uživatel
            await interaction.response.send_message("❌ Toto tlačítko není pro tebe!", ephemeral=True)
            return
        player = self.view_parent.candidates[self.index] # Vybraný hráč
        await self.view_parent.bot.potvrdit_hrace(interaction, player) # Pokračujeme v potvrzení
        self.view_parent.stop() # Ukončíme view

class MyBot(commands.Bot): # Definice hlavního bota
    def __init__(self, command_prefix, intents, guild_id, clan_tag, config):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.guild_object = discord.Object(id=guild_id) # Discord server (guild)
        self.clan_tag = clan_tag # Tag klanu pro API dotazy
        self.config = config # Konfigurace bota (tokeny atd.)

    async def setup_hook(self):
        @self.tree.command(name="verifikovat", description="Ověř si svůj účet pomocí jména nebo tagu",guild=self.guild_object) # Slash příkaz /verifikovat
        @app_commands.describe(hledat="Zadej své Clash of Clans jméno nebo tag (#ABCD123)")
        async def verifikovat(interaction: discord.Interaction, hledat: str): # hledat je vstup – jméno nebo tag.
            await interaction.response.defer(ephemeral=True, thinking=True) # defer() znamená "čekejme odpověď", aby Discord nehlásil timeout.
            clenove = get_all_members()  # Načteme členy klanu z DB

            if hledat.startswith("#"): # Pokud začíná na #, hledáme podle tagu.
                nalezeny = next((m for m in clenove if m.get("tag", "").upper() == hledat.upper()), None)
                if nalezeny:
                    await self.potvrdit_hrace(interaction, nalezeny)
                else:
                    await interaction.followup.send("❌ Hráč s tímto tagem nebyl nalezen.")
            else:
                shody = [m for m in clenove if m.get("name", "").casefold() == hledat.casefold()] # casefold() = case-insensitive porovnání.
                if len(shody) == 0: # 0 → neexistuje hráč
                    await interaction.followup.send("❌ Nenašel jsem žádného hráče s tímto jménem.")
                elif len(shody) == 1: # 1 → rovnou nabídnout potvrzení
                    await self.potvrdit_hrace(interaction, shody[0])
                elif len(shody) <= 3: # 2–3 → nabídnout tlačítka na výběr
                    view = SelectPlayerView(shody, interaction.user, self, interaction)
                    description = ""
                    emojis = ["1️⃣", "2️⃣", "3️⃣"]
                    for i, player in enumerate(shody):
                        description += f"{emojis[i]} {player['name']} ({player['tag']}) | 🏆 {player['trophies']} | TH{player['townHallLevel']}\n"

                    await interaction.followup.send(description, view=view, ephemeral=True)
                else: # víc než 3 → napíše chybu
                    await interaction.followup.send("⚠️ Našlo se víc než 3 hráči se stejným jménem. Zadej prosím konkrétní tag (#...).", ephemeral=True) # Pokud je víc než 3 hráči se stejným jménem, vypíše chybu.

        @self.tree.command(name="helloo", description="Napíše pozdrav", guild=self.guild_object) # testovací příkaz
        async def say_hello(interaction: discord.Interaction): # Příkaz /helloo
            await interaction.response.send_message("Ahoj! 👋") # Odpoví na příkaz /helloo

        try:
            synced = await self.tree.sync(guild=self.guild_object) # Synchronizace slash příkazů se serverem.
            print(f"✅ Synchronizováno {len(synced)} příkaz(ů) se serverem {self.guild_object.id}") # Vypíše do konzole počet synchronizovaných příkazů.
        except Exception as e: # Pokud dojde k chybě při synchronizaci, vypíše chybu do konzole.
            print(f"❌ Chyba při synchronizaci příkazů: {e}")

        asyncio.create_task(hourly_clan_update(self.config, self)) # Spustí funkci na aktualizaci členů každou hodinu na pozadí.

    async def on_ready(self):
        print(f"✅🤖 Přihlášen jako {self.user}") # Když je bot přihlášený, vypíše info do konzole.

    async def potvrdit_hrace(self, interaction, player):
        embed = discord.Embed(
            title=f"{player['name']} ({player['tag']})",
            color=discord.Color.green()
        )

        # Základní informace
        trophies = player.get("trophies", "?")
        townhall_level = player.get("townHallLevel", "?")
        league = player.get("league", "Neznámá liga")
        role = player.get("role", "member")

        embed.add_field(name="🏆 Trofeje", value=f"{trophies}", inline=True)
        embed.add_field(name="🏅 Liga", value=f"{league}", inline=True)

        embed.add_field(name="👑 Role v klanu", value=f"{role}", inline=False)
        embed.add_field(name="🏰 Town Hall", value=f"TH{townhall_level}", inline=True)

        embed.set_footer(text="Klikni na ✅ pro potvrzení")

        view = ConfirmView(player, interaction.user, self)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.message = msg
        await asyncio.sleep(30)  # Počká 30 sekund.
        await msg.delete()  # Smaže zprávu.


def start_bot(config): # Funkce pro spuštění bota
    intents = discord.Intents.default() # Vytvoříme defaultní intents
    intents.message_content = True # Povolení obsahu zpráv

    bot = MyBot( # Vytvoříme instanci bota
        command_prefix="/", # Prefix pro příkazy
        intents=intents, # Intents pro bota
        guild_id=config["GUILD_ID"], # ID serveru (guild)
        clan_tag=config["CLAN_TAG"], # Tag klanu pro API dotazy
        config=config # Konfigurace bota (tokeny atd.
    )
    bot.run(config["DISCORD_BOT_TOKEN"]) # Spustí bota s tokenem