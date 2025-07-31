import discord
from discord import app_commands
from typing import Optional
from database import get_all_members, get_all_links
from role_giver import update_roles
from verification import start_verification_permission
from constants import TOWN_HALL_EMOJIS



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
