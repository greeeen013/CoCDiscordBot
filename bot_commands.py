import discord
from discord.ext import commands
import asyncio

from scheduler import hourly_clan_update

class MyBot(commands.Bot):
    def __init__(self, command_prefix, intents, guild_id, clan_tag, config):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.guild_object = discord.Object(id=guild_id)
        self.clan_tag = clan_tag
        self.config = config

    async def setup_hook(self):
        @self.tree.command(name="helloo", description="Napíše pozdrav", guild=self.guild_object)
        async def say_hello(interaction: discord.Interaction):
            await interaction.response.send_message("Ahoj! 👋")

        try:
            synced = await self.tree.sync(guild=self.guild_object)
            print(f"✅ Synchronizováno {len(synced)} příkaz(ů) se serverem {self.guild_object.id}")
        except Exception as e:
            print(f"❌ Chyba při synchronizaci příkazů: {e}")

        # Spuštění hodinového updatu při startu bota
        asyncio.create_task(hourly_clan_update(self.clan_tag, self.config))

    async def on_ready(self):
        print(f"✅🤖 Přihlášen jako {self.user}")

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
