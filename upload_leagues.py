import discord
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')

if not TOKEN or not GUILD_ID:
    print("Error: DISCORD_BOT_TOKEN or GUILD_ID not found in .env")
    exit(1)

GUILD_ID = int(GUILD_ID)

# League definitions
LEAGUES = {
    "league_unranked": "https://static.wikia.nocookie.net/clashofclans/images/b/b4/Unranked.png/revision/latest/scale-to-width-down/90?cb=20251006172834",
    "league_skeleton": "https://static.wikia.nocookie.net/clashofclans/images/e/e6/Skeleton_League.png/revision/latest/scale-to-width-down/100?cb=20251006065317",
    "league_barbarian": "https://static.wikia.nocookie.net/clashofclans/images/c/c0/Barbarian_League.png/revision/latest/scale-to-width-down/100?cb=20251119195647",
    "league_archer": "https://static.wikia.nocookie.net/clashofclans/images/8/85/Archer_League.png/revision/latest/scale-to-width-down/100?cb=20251006065408",
    "league_wizard": "https://static.wikia.nocookie.net/clashofclans/images/1/1b/Wizard_League.png/revision/latest/scale-to-width-down/100?cb=20251006065428",
    "league_valkyrie": "https://static.wikia.nocookie.net/clashofclans/images/c/c8/Valkyrie_League.png/revision/latest/scale-to-width-down/100?cb=20251006065509",
    "league_witch": "https://static.wikia.nocookie.net/clashofclans/images/a/a1/Witch_League.png/revision/latest/scale-to-width-down/100?cb=20251006065535",
    "league_golem": "https://static.wikia.nocookie.net/clashofclans/images/0/01/Golem_League.png/revision/latest/scale-to-width-down/100?cb=20251006065601",
    "league_pekka": "https://static.wikia.nocookie.net/clashofclans/images/3/33/PEKKA_League.png/revision/latest/scale-to-width-down/100?cb=20251006065625",
    "league_titan": "https://static.wikia.nocookie.net/clashofclans/images/3/36/Electro_Titan_League.png/revision/latest/scale-to-width-down/100?cb=20251006065713",
    "league_dragon": "https://static.wikia.nocookie.net/clashofclans/images/3/33/Dragon_League.png/revision/latest/scale-to-width-down/110?cb=20251006065732",
    "league_electro": "https://static.wikia.nocookie.net/clashofclans/images/3/3e/Electro_Dragon_League.png/revision/latest/scale-to-width-down/110?cb=20251006065806",
    "league_legend": "https://static.wikia.nocookie.net/clashofclans/images/8/86/Legend_League2.png/revision/latest/scale-to-width-down/110?cb=20251006065838"
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    guild = client.get_guild(GUILD_ID)
    if not guild:
        print(f"Server with ID {GUILD_ID} not found.")
        await client.close()
        return

    print(f"Processing server: {guild.name}")
    
    # Fetch existing emojis to avoid duplicates
    existing_emojis = {emoji.name: emoji for emoji in guild.emojis}
    uploaded_emojis = {}

    async with aiohttp.ClientSession() as session:
        for name, url in LEAGUES.items():
            if name in existing_emojis:
                emoji = existing_emojis[name]
                print(f"Skipping {name}, already exists (ID: {emoji.id}).")
                uploaded_emojis[name] = emoji.id
                continue

            print(f"Downloading {name} from {url}...")
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        print(f"Uploading {name}...")
                        try:
                            emoji = await guild.create_custom_emoji(name=name, image=data)
                            print(f"Successfully created emoji: {emoji.name} (ID: {emoji.id})")
                            uploaded_emojis[name] = emoji.id
                        except discord.HTTPException as e:
                             print(f"Failed to upload {name}: {e}")
                    else:
                        print(f"Failed to download image for {name}. Status: {response.status}")
            except Exception as e:
                print(f"Error processing {name}: {e}")
                
    print("\n--- EMOJI DATA ---")
    print("Dict format:")
    print(uploaded_emojis)
    
    print("\nPython Dict format for constants:")
    print("LEAGUES = {")
    for name, emoji_id in uploaded_emojis.items():
        print(f'    "{name}": "<:{name}:{emoji_id}>",')
    print("}")
    
    print("Done!")
    await client.close()

if __name__ == "__main__":
    client.run(TOKEN)
