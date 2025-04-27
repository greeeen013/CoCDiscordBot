import discord # Import základní knihovny discord.py
from discord import app_commands
from discord.ext import commands # Import třídy commands z discord.ext.commands pro práci s příkazy a bota
import asyncio # Import knihovny asyncio pro asynchronní programování (např. čekání na události)
from scheduler import hourly_clan_update # Import funkce pro hodinovou aktualizaci členů klanu
from database import get_all_members, get_all_links # Import funkce, která načítá všechny hráče z databáze
from verification import start_verification_permission  # Importuj funkci ze souboru verification.py
from role_giver import update_roles # Import funkce pro získání mapování mezi Discord ID a tagy hráčů

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

class ConfirmView(discord.ui.View): # Definice view (rozhraní s tlačítkem) pro potvrzení identity hráče
    def __init__(self, player, user, bot): # Konstruktor view – přijímá hráče, uživatele a instanci bota
        super().__init__(timeout=30) # timeout=30 sekund, po kterém tlačítko zmizí
        self.player = player # Data ověřovaného hráče
        self.user = user # Uživatel, který vybírá
        self.bot = bot # Instance bota
        self.result = False # Výsledek potvrzení (zda bylo potvrzeno)

    @discord.ui.button(label="✅ Potvrdit", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Callback pro potvrzovací tlačítko – spustí verifikační proces.
        """
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Toto tlačítko není pro tebe!", ephemeral=True)
            return

        self.result = True

        # spustíme proces verifikace
        await start_verification_permission(interaction, self.player, interaction.client.config)

        self.stop()  # Ukončí view, zmizí tlačítka

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


class VerifikacniView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Bez timeoutu, aby tlačítko zůstalo aktivní

    @discord.ui.button(label="✅ Chci ověřit účet", style=discord.ButtonStyle.success, custom_id="start_verification")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has the role 1365768439473373235
        role_id = 1365768439473373235
        if discord.utils.get(interaction.user.roles, id=role_id):
            # User has the role - send ephemeral message that they can't verify again
            await interaction.response.send_message(
                "❌ Již jsi ověřený a nemůžeš se ověřit znovu!",
                ephemeral=True
            )
            return

        # User doesn't have the role - proceed with verification
        await interaction.response.send_modal(VerifikaceModal())

class VerifikaceModal(discord.ui.Modal, title="Ověření Clash of Clans účtu"):
    hledat = discord.ui.TextInput(
        label="Zadej své Clash of Clans jméno nebo tag",
        placeholder="např. green013 nebo #2P0Y82Q",
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        zadany_text = self.hledat.value
        clenove = get_all_members()  # Načteme členy z databáze

        await interaction.response.defer(ephemeral=True, thinking=True)

        if zadany_text.startswith("#"):
            nalezeny = next((m for m in clenove if m.get("tag", "").upper() == zadany_text.upper()), None)
            if nalezeny:
                await interaction.client.potvrdit_hrace(interaction, nalezeny)
            else:
                await interaction.followup.send("❌ Hráč s tímto tagem nebyl nalezen.", ephemeral=True)
        else:
            shody = [m for m in clenove if m.get("name", "").casefold() == zadany_text.casefold()]
            if len(shody) == 0:
                await interaction.followup.send("❌ Nenašel jsem žádného hráče s tímto jménem.", ephemeral=True)
            elif len(shody) == 1:
                await interaction.client.potvrdit_hrace(interaction, shody[0])
            elif len(shody) <= 3:
                view = SelectPlayerView(shody, interaction.user, interaction.client, interaction)
                description = ""
                emojis = ["1️⃣", "2️⃣", "3️⃣"]
                for i, player in enumerate(shody):
                    description += f"{emojis[i]} {player['name']} ({player['tag']}) | 🏆 {player['trophies']} | TH{player['townHallLevel']}\n"

                await interaction.followup.send(description, view=view, ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Našlo se víc než 3 hráči se stejným jménem. Zadej prosím konkrétní tag (#...).", ephemeral=True)

class MyBot(commands.Bot): # Definice hlavního bota
    def __init__(self, command_prefix, intents, guild_id, clan_tag, config):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.guild_object = discord.Object(id=guild_id) # Discord server (guild)
        self.clan_tag = clan_tag # Tag klanu pro API dotazy
        self.config = config # Konfigurace bota (tokeny atd.)

    async def setup_hook(self):
        @self.tree.command(name="aktualizujrole", description="Aktualizuje role všech propojených členů",
                           guild=self.guild_object)
        async def aktualizujrole(interaction: discord.Interaction):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Tento příkaz může použít pouze administrátor.",
                                                        ephemeral=True)
                return

            await interaction.response.defer(thinking=True, ephemeral=True)


            clan_members = get_all_members()  # Vrátí všechny členy klanu z databáze
            user_mapping = get_all_links()  # Vrátí propojení Discord ID -> Tag (ten list co jsi popisoval)

            if not clan_members or not user_mapping:
                await interaction.followup.send("❌ Chyba: nebyla načtena databáze členů nebo propojení.",
                                                ephemeral=True)
                print(f"❌ [bot_commands] Chyba: nebyla načtena databáze členů nebo propojení.")
                print(f"❌ [bot_commands] Členové: {clan_members}")
                print(f"❌ [bot_commands] Propojení: {user_mapping}")
                return

            # Zavoláme aktualizaci
            await update_roles(interaction.guild, user_mapping, clan_members)

            await interaction.followup.send("✅ Role byly úspěšně aktualizovány!", ephemeral=True)
        @self.tree.command(name="vytvor_verifikacni_tabulku", description="Vytvoří verifikační tabulku s tlačítkem",
                           guild=self.guild_object)
        async def vytvor_verifikacni_tabulku(interaction: discord.Interaction):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Tento příkaz může použít pouze administrátor.",
                                                        ephemeral=True)
                return

            embed = discord.Embed(
                title="✅ Ověření účtu Clash of Clans",
                description=(
                    "**Klikni na tlačítko níže a ověř si svůj účet!**\n\n"
                    "- Po kliknutí zadáš své jméno nebo tag.\n"
                    "- Budeš proveden procesem ověření.\n"
                    "- Tento kanál slouží pouze k ověření – psaní zpráv není povoleno."
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text="Tým Clash of Clans ověřování 🔒")

            view = VerifikacniView()

            await interaction.channel.send(embed=embed, view=view)

            # Uzamkneme práva na psaní
            overwrite = discord.PermissionOverwrite()
            overwrite.send_messages = False
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

            await interaction.response.send_message("✅ Verifikační tabulka vytvořena a kanál uzamčen!", ephemeral=True)
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
            print(f"✅ [bot_commands] Synchronizováno {len(synced)} příkaz(ů) se serverem {self.guild_object.id}") # Vypíše do konzole počet synchronizovaných příkazů.
        except Exception as e: # Pokud dojde k chybě při synchronizaci, vypíše chybu do konzole.
            print(f"❌ [bot_commands] Chyba při synchronizaci příkazů: {e}")

    async def on_ready(self):
        print(f"✅🤖 Přihlášen jako {self.user}") # Když je bot přihlášený, vypíše info do konzole.
        self.add_view(VerifikacniView())
        asyncio.create_task(hourly_clan_update(self.config, self)) # Spustí funkci na aktualizaci členů každou hodinu na pozadí.

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
        embed.add_field(name="🏅 Liga", value=f"{league} {LEAGUES.get(' '.join(league.split()[:2]))}", inline=True)
        embed.add_field(name="👑 Role v klanu", value=f"{role}", inline=True)
        embed.add_field(name="🏰 Town Hall lvl", value=f"{townhall_level} {TOWN_HALL_EMOJIS.get(townhall_level)}", inline=True)


        embed.set_footer(text="Klikni na ✅ pro potvrzení")

        view = ConfirmView(player, interaction.user, self)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.message = msg
        await asyncio.sleep(30)  # Počká 30 sekund.
        await msg.delete()  # Smaže zprávu.


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