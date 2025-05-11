import discord
from discord import app_commands
from typing import Optional
from database import get_all_members, get_all_links
from role_giver import update_roles
from verification import start_verification_permission

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
}
HEROES_EMOJIS = {
    "Barbarian King": "<:barbarian_king:1371137125818568764>",
    "Archer Queen": "<:archer_queen:1371137339589394432>",
    "Grand Warden": "<:grand_warden:1371137633891254353>",
    "Royal Champion": "<:royal_champion:1371137975412592690>",
    "Minion Prince": "<:minion_prince:1371138182619463713>",
}

# Třídy pro ověřování
class ConfirmView(discord.ui.View):
    def __init__(self, player, user, bot):
        super().__init__(timeout=30)
        self.player = player
        self.user = user
        self.bot = bot
        self.result = False

    @discord.ui.button(label="✅ Potvrdit", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Toto tlačítko není pro tebe!", ephemeral=True)
            return

        self.result = True
        await start_verification_permission(interaction, self.player, interaction.client.config)
        self.stop()

class SelectPlayerView(discord.ui.View):
    def __init__(self, candidates, user, bot, interaction):
        super().__init__(timeout=30)
        self.candidates = candidates
        self.user = user
        self.bot = bot
        self.interaction = interaction

        emojis = ["1️⃣", "2️⃣", "3️⃣"]
        for i, player in enumerate(candidates):
            self.add_item(PlayerSelectButton(index=i, emoji=emojis[i], view_parent=self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

class PlayerSelectButton(discord.ui.Button):
    def __init__(self, index, emoji, view_parent):
        super().__init__(label=str(index + 1), emoji=emoji, style=discord.ButtonStyle.primary, custom_id=str(index))
        self.index = index
        self.view_parent = view_parent

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.view_parent.user:
            await interaction.response.send_message("❌ Toto tlačítko není pro tebe!", ephemeral=True)
            return
        player = self.view_parent.candidates[self.index]
        await self.view_parent.bot.potvrdit_hrace(interaction, player)
        self.view_parent.stop()

class VerifikacniView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Chci ověřit účet", style=discord.ButtonStyle.success, custom_id="start_verification")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_id = 1365768439473373235
        if discord.utils.get(interaction.user.roles, id=role_id):
            await interaction.response.send_message("❌ Již jsi ověřený a nemůžeš se ověřit znovu!", ephemeral=True)
            return

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
        clenove = get_all_members()

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

# Příkazy pro bota
async def setup_commands(bot):
    @bot.tree.command(name="aktualizujrole", description="Aktualizuje role všech propojených členů", guild=bot.guild_object)
    async def aktualizujrole(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze administrátor.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        clan_members = get_all_members()
        user_mapping = get_all_links()

        if not clan_members or not user_mapping:
            await interaction.followup.send("❌ Chyba: nebyla načtena databáze členů nebo propojení.", ephemeral=True)
            print(f"❌ [bot_commands] Chyba: nebyla načtena databáze členů nebo propojení.")
            print(f"❌ [bot_commands] Členové: {clan_members}")
            print(f"❌ [bot_commands] Propojení: {user_mapping}")
            return

        await update_roles(interaction.guild, user_mapping, clan_members)
        await interaction.followup.send("✅ Role byly úspěšně aktualizovány!", ephemeral=True)

    @bot.tree.command(name="vytvor_verifikacni_tabulku", description="Vytvoří verifikační tabulku s tlačítkem", guild=bot.guild_object)
    async def vytvor_verifikacni_tabulku(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze administrátor.", ephemeral=True)
            return

        embed = discord.Embed(
            title="✅ Ověření účtu pro klan Czech Heroes",
            description=(
                "**Klikni na tlačítko níže a ověř si svůj účet!**\n\n"
                "- ověřování je dělané jen pro členy klanu **Czech Heroes**"
                "- Po kliknutí zadáš své jméno nebo #tag.\n"
                "- Budeš proveden procesem ověření tvého účtu kde jen vybereš equipment na hrdinu.\n"
                "- Pokud jsi již ověřený, nebudeš moci ověřit znovu.\n"
                f"- Ověření je možné pouze, pokud je bot online: <@1363529470778146876>\n"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="- Czech Heroes klan 🔒")

        view = VerifikacniView()
        await interaction.channel.send(embed=embed, view=view)

        overwrite = discord.PermissionOverwrite()
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        await interaction.response.send_message("✅ Verifikační tabulka vytvořena a kanál uzamčen!", ephemeral=True)

    @bot.tree.command(name="verifikovat", description="Ověř si svůj účet pomocí jména nebo tagu", guild=bot.guild_object)
    @app_commands.describe(hledat="Zadej své Clash of Clans jméno nebo tag (#ABCD123)")
    async def verifikovat(interaction: discord.Interaction, hledat: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        clenove = get_all_members()

        if hledat.startswith("#"):
            nalezeny = next((m for m in clenove if m.get("tag", "").upper() == hledat.upper()), None)
            if nalezeny:
                await bot.potvrdit_hrace(interaction, nalezeny)
            else:
                await interaction.followup.send("❌ Hráč s tímto tagem nebyl nalezen.")
        else:
            shody = [m for m in clenove if m.get("name", "").casefold() == hledat.casefold()]
            if len(shody) == 0:
                await interaction.followup.send("❌ Nenašel jsem žádného hráče s tímto jménem.")
            elif len(shody) == 1:
                await bot.potvrdit_hrace(interaction, shody[0])
            elif len(shody) <= 3:
                view = SelectPlayerView(shody, interaction.user, bot, interaction)
                description = ""
                emojis = ["1️⃣", "2️⃣", "3️⃣"]
                for i, player in enumerate(shody):
                    description += f"{emojis[i]} {player['name']} ({player['tag']}) | 🏆 {player['trophies']} | TH{player['townHallLevel']}\n"

                await interaction.followup.send(description, view=view, ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Našlo se víc než 3 hráči se stejným jménem. Zadej prosím konkrétní tag (#...).", ephemeral=True)

    @bot.tree.command(name="max_hero_lvl", description="Zobrazí max levely hrdinů pro dané Town Hall",
                      guild=bot.guild_object)
    @app_commands.describe(townhall="Zadej Town Hall (10–17)")
    async def hero_levels_th(interaction: discord.Interaction, townhall: int):
        if townhall < 10 or townhall > 17:
            await interaction.response.send_message("❌ Zadej číslo Town Hall mezi 10 a 17.", ephemeral=True)
            return

        data = {
            10: {"Barbarian King": 40, "Archer Queen": 40, "Grand Warden": "N/A", "Royal Champion": "N/A",
                 "Minion Prince": 20},
            11: {"Barbarian King": 50, "Archer Queen": 50, "Grand Warden": 20, "Royal Champion": "N/A",
                 "Minion Prince": 30},
            12: {"Barbarian King": 65, "Archer Queen": 65, "Grand Warden": 40, "Royal Champion": "N/A",
                 "Minion Prince": 40},
            13: {"Barbarian King": 75, "Archer Queen": 75, "Grand Warden": 50, "Royal Champion": 25,
                 "Minion Prince": 50},
            14: {"Barbarian King": 80, "Archer Queen": 80, "Grand Warden": 55, "Royal Champion": 30,
                 "Minion Prince": 60},
            15: {"Barbarian King": 90, "Archer Queen": 90, "Grand Warden": 65, "Royal Champion": 45,
                 "Minion Prince": 70},
            16: {"Barbarian King": 95, "Archer Queen": 95, "Grand Warden": 70, "Royal Champion": 45,
                 "Minion Prince": "80 *(upraveno)*"},
            17: {"Barbarian King": 100, "Archer Queen": 100, "Grand Warden": 75, "Royal Champion": 50,
                 "Minion Prince": "90 *(upraveno)*"},
        }

        th_data = data[townhall]

        embed = discord.Embed(
            title=f"{TOWN_HALL_EMOJIS[townhall]} Town Hall {townhall} – Max. levely hrdinů",
            color=discord.Color.orange()
        )

        for hero, level in th_data.items():
            emoji = HEROES_EMOJIS.get(hero, "")
            embed.add_field(name=f"{emoji} {hero}", value=f"**{level}**", inline=True)

        embed.set_footer(text="Data z officialní clash of clans wiki")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="helloo", description="Napíše pozdrav", guild=bot.guild_object)
    async def say_hello(interaction: discord.Interaction):
        await interaction.response.send_message("Ahoj! 👋")