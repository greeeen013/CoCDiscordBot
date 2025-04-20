from dotenv import load_dotenv #kvuli env file pip install load_dotenv
import os
import discord #kvuli discord botovi pip install discord.py
from discord.ext import commands
from discord import app_commands

load_dotenv()  # načte proměnné z .env souboru
COC_api_key = os.getenv("COC_API_KEY")
Discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")

class Client(commands.Bot):
    async def on_ready(self):
        await self.tree.sync()  # Synchronizace příkazů s Discord API
        print(f'Logged on as {self.user}!')
        try:
            guild=discord.Object(id=1363528906480681171) # pokud chceme aby fungoval jen na jednom serveru
            synced = await self.tree.sync(guild=guild) # Synchronizace příkazů s konkrétním serverem
            print(f"Synced {len(synced)} commands to guild {guild.id}.")

        except Exception as e:
            print(f"Error syncing commands: {e}")

intents = discord.Intents.default()
intents.message_content = True
client = Client(command_prefix="/", intents=intents)

guild=discord.Object(id=1363528906480681171) # pokud chceme aby fungoval jen na jednom serveru

#          name= obsah uvozovek musí být lowercase
@client.tree.command(name="helloo", description="just say hello!", guild=guild) #, guild=GUILD_ID
async def sayHello(interaction: discord.Interaction):
    await interaction.response.send_message("Hi there!")

client.run(Discord_bot_token)