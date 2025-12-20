
import discord
import asyncio
import os
import json

from dotenv import load_dotenv

# Konfigurace - načtení tokenu ze souboru nebo environment proměnné
# Předpokládá se spuštění ve stejné složce jako bot, nebo uprav cestu
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not TOKEN or not GUILD_ID:
    print("[ERROR] Chybí TOKEN nebo GUILD_ID v .env souboru.")
    exit()

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

client = discord.Client(intents=intents)

# Definice nových rolí
# Formát: (BaseName, StartLevel, EndLevel)
# Legend nemá čísla, je samostatně
ROLE_DEFINITIONS = [
    ("Skeleton", 1, 3),
    ("Barbarian", 4, 6),
    ("Archer", 7, 9),
    ("Wizard", 10, 12),
    ("Valkyrie", 13, 15),
    ("Witch", 16, 18),
    ("Golem", 19, 21),
    ("P.E.K.K.A", 22, 24),
    ("Titan", 25, 27),
    ("Dragon", 28, 30),
    ("Electro", 31, 33),
]

ROLE_LEGEND = "Legend League"

@client.event
async def on_ready():
    print(f'[OK] Prihlasen jako {client.user}')
    guild = client.get_guild(int(GUILD_ID))
    
    if not guild:
        print(f"[ERROR] Server s ID {GUILD_ID} nenalezen.")
        await client.close()
        return

    print(f"[INFO] Pracuji na serveru: {guild.name}")
    
    created_roles = {}
    
    # 1. Projdi definice a vytvoř/najdi role
    for name, start, end in ROLE_DEFINITIONS:
        for i in range(start, end + 1):
            role_name = f"{name} {i}"
            
            # Zkus najít existující
            existing_role = discord.utils.get(guild.roles, name=role_name)
            
            if existing_role:
                print(f"[INFO] Role '{role_name}' jiz existuje (ID: {existing_role.id})")
                created_roles[role_name] = existing_role.id
            else:
                try:
                    new_role = await guild.create_role(name=role_name, reason="New League System Update")
                    print(f"[OK] Vytvorena role '{role_name}' (ID: {new_role.id})")
                    created_roles[role_name] = new_role.id
                except Exception as e:
                    print(f"[ERROR] Chyba pri vytvareni role '{role_name}': {e}")


    # 2. Legend role (pokud je specifická)
    # Zadání: "Legend" (bez čísla)
    legend_name = "Legend"
    existing_legend = discord.utils.get(guild.roles, name=legend_name)
    if existing_legend:
        print(f"ℹ️ Role '{legend_name}' již existuje (ID: {existing_legend.id})")
        created_roles[legend_name] = existing_legend.id
    else:
        try:
            new_role = await guild.create_role(name=legend_name, reason="New League System Update")
            print(f"✅ Vytvořena role '{legend_name}' (ID: {new_role.id})")
            created_roles[legend_name] = new_role.id
        except Exception as e:
            print(f"❌ Chyba při vytváření role '{legend_name}': {e}")
            
    # 3. Výpis výsledku ve formátu pro python dict
    print("\n--- ZKOPÍRUJ NÁSLEDUJÍCÍ KÓD DO role_giver.py ---")
    print("LEAGUE_ROLES = {")
    for name, role_id in created_roles.items():
        print(f'    "{name}": {role_id},')
    print("}")
    print("-------------------------------------------------")
    
    await client.close()

client.run(TOKEN)
