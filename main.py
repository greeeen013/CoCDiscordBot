import os
from dotenv import load_dotenv  # Načítání proměnných z .env souboru
import discord  # Hlavní knihovna pro Discord bota
from discord.ext import commands  # Rozšíření pro příkazový systém
from discord import app_commands  # Pro práci se slash příkazy

# === Načtení konfigurace z .env ===
def load_config():
    load_dotenv()  # Načte všechny proměnné z .env souboru do prostředí
    return {
        "COC_API_KEY": os.getenv("COC_API_KEY"),  # API klíč pro Clash of Clans
        "DISCORD_BOT_TOKEN": os.getenv("DISCORD_BOT_TOKEN"),  # Token pro Discord bota
        "GUILD_ID": int(os.getenv("GUILD_ID"))  # ID Discord serveru (fallback hodnota)
    }

# === Vlastní třída pro Discord bota ===
class MyBot(commands.Bot):
    def __init__(self, command_prefix, intents, guild_id):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.guild_object = discord.Object(id=guild_id)  # Server, na kterém bude bot registrován

    async def setup_hook(self):
        # Registrace slash příkazu při spouštění bota
        @self.tree.command(name="helloo", description="Napíše pozdrav", guild=self.guild_object)
        async def say_hello(interaction: discord.Interaction):
            await interaction.response.send_message("Ahoj! 👋")

        try:
            # Synchronizace slash příkazů se serverem (guild)
            synced = await self.tree.sync(guild=self.guild_object)
            print(f"✅ Synchronizováno {len(synced)} příkaz(ů) se serverem {self.guild_object.id}")
        except Exception as e:
            print(f"❌ Chyba při synchronizaci příkazů: {e}")

    async def on_ready(self):
        # Vypíše se, když se bot úspěšně připojí
        print(f"✅🤖 Přihlášen jako {self.user}")

# === Spuštění aplikace ===
def main():
    config = load_config()  # Načteme konfiguraci z .env
    print(f"✅ Načtený COC API klíč: {config['COC_API_KEY']}")
    print(f"✅ Načtený Discord bot token: {config['DISCORD_BOT_TOKEN']}")
    print(f"✅ Načtený Discord guild id: {config['GUILD_ID']}")
    #sleep(1)  # Krátká pauza pro lepší čitelnost výstupu

    intents = discord.Intents.default()
    intents.message_content = True  # Povolení čtení zpráv (nutné pro některé funkce)

    # Vytvoření instance bota a spuštění
    bot = MyBot(command_prefix="/", intents=intents, guild_id=config["GUILD_ID"])
    bot.run(config["DISCORD_BOT_TOKEN"])  # Spuštění bota s tokenem

# === Hlavní vstupní bod ===
if __name__ == "__main__":
    main()
