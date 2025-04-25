import discord
from discord.ext import commands
import asyncio
import json
import os

from scheduler import hourly_clan_update
from database import process_clan_data
from database import get_all_members  # musíš mít funkci která načte členy z DB

VERIFICATION_PATH = "verification_data.json"

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
        await interaction.response.send_message(f"✅ Ověřil ses jako {self.player['name']} ({self.player['tag']})!", ephemeral=True)
        self.stop()

    async def on_timeout(self):
        if not self.result:
            try:
                await self.message.edit(content="⏱️ Čas na potvrzení vypršel.", view=None)
            except:
                pass

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

    async def on_timeout(self):
        try:
            await self.interaction.followup.send("⏱️ Čas na výběr hráče vypršel.", ephemeral=True)
        except:
            pass

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

class MyBot(commands.Bot):
    def __init__(self, command_prefix, intents, guild_id, clan_tag, config):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.guild_object = discord.Object(id=guild_id)
        self.clan_tag = clan_tag
        self.config = config

    async def setup_hook(self):
        @self.tree.command(name="verifikovat", description="Ověř si svůj účet pomocí jména nebo tagu", guild=self.guild_object)
        async def verifikovat(interaction: discord.Interaction, hledat: str):
            await interaction.response.defer(ephemeral=True, thinking=True)
            clenove = get_all_members()  # nově taháme z databáze

            if hledat.startswith("#"):
                nalezeny = next((m for m in clenove if m.get("tag", "").upper() == hledat.upper()), None)
                if nalezeny:
                    await self.potvrdit_hrace(interaction, nalezeny)
                else:
                    await interaction.followup.send("❌ Hráč s tímto tagem nebyl nalezen.")
            else:
                shody = [m for m in clenove if m.get("name", "").casefold() == hledat.casefold()]
                if len(shody) == 0:
                    await interaction.followup.send("❌ Nenašel jsem žádného hráče s tímto jménem.")
                elif len(shody) == 1:
                    await self.potvrdit_hrace(interaction, shody[0])
                elif len(shody) <= 3:
                    view = SelectPlayerView(shody, interaction.user, self, interaction)
                    description = ""
                    emojis = ["1️⃣", "2️⃣", "3️⃣"]
                    for i, player in enumerate(shody):
                        description += f"{emojis[i]} {player['name']} ({player['tag']}) | 🏆 {player['trophies']} | TH{player['townHallLevel']}\n"

                    await interaction.followup.send(description, view=view, ephemeral=True)
                else:
                    await interaction.followup.send("⚠️ Našlo se víc než 3 hráči se stejným jménem. Zadej prosím konkrétní tag (#...).", ephemeral=True)

        @self.tree.command(name="helloo", description="Napíše pozdrav", guild=self.guild_object)
        async def say_hello(interaction: discord.Interaction):
            await interaction.response.send_message("Ahoj! 👋")

        try:
            synced = await self.tree.sync(guild=self.guild_object)
            print(f"✅ Synchronizováno {len(synced)} příkaz(ů) se serverem {self.guild_object.id}")
        except Exception as e:
            print(f"❌ Chyba při synchronizaci příkazů: {e}")

        asyncio.create_task(hourly_clan_update(self.config, self))

    async def on_ready(self):
        print(f"✅🤖 Přihlášen jako {self.user}")

    async def potvrdit_hrace(self, interaction, player):
        embed = discord.Embed(title=f"{player['name']} ({player['tag']})", color=discord.Color.green())
        embed.add_field(name="🏆 Trofeje", value=str(player.get("trophies", "?")))
        embed.add_field(name="🏰 Town Hall", value=f"TH{player.get('townHallLevel', '?')}")
        embed.set_footer(text="Klikni na ✅ pro potvrzení")

        view = ConfirmView(player, interaction.user, self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

def start_bot(config):
    intents = discord.Intents.default()
    intents.message_content = True

    bot = MyBot(
        command_prefix="/",
        intents=intents,
        guild_id=config["GUILD_ID"],
        clan_tag=config["CLAN_TAG"],
        config=config
    )
    bot.run(config["DISCORD_BOT_TOKEN"])