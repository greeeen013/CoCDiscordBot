
import discord
import asyncio
import os
import json

from dotenv import load_dotenv
from constants import LEAGUE_ROLES  # Načítáme ID rolí pro Mode 3

# Konfigurace - načtení tokenu ze souboru nebo environment proměnné
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

# Definice pro generování (používá se pro Mode 1 a 2)
ROLE_DEFINITIONS = [
    ("Skeleton", 1, 3), ("Barbarian", 4, 6), ("Archer", 7, 9), ("Wizard", 10, 12),
    ("Valkyrie", 13, 15), ("Witch", 16, 18), ("Golem", 19, 21), ("P.E.K.K.A", 22, 24),
    ("Titan", 25, 27), ("Dragon", 28, 30), ("Electro", 31, 33),
]
ROLE_LEGEND = "Legend"
ROLE_UNRANKED = "Unranked" # Pokud chcete, aby se vytvářel i Unranked

PREFIX = "⁣               "
SUFFIX = "               ⁣"

# --- MODE 1: Check ---
async def mode_check(guild):
    print("\n--- [MODE 1] CONTROL & EXPORT ---")
    found_roles = {}
    
    # Pomocná funkce pro hledání
    async def find_role(base_name):
        padded_name = f"{PREFIX}{base_name}{SUFFIX}"
        
        # 1. Hledáme podle ID v constants.py (nejpřesnější)
        if base_name in LEAGUE_ROLES:
            role_by_id = guild.get_role(LEAGUE_ROLES[base_name])
            if role_by_id:
                print(f"✅ Nalezeno dle ID: '{role_by_id.name}' (Core: {base_name}) -> {role_by_id.id}")
                return role_by_id.id

        # 2. Hledáme podle jména (padded i plain)
        role = discord.utils.get(guild.roles, name=padded_name)
        if not role:
            role = discord.utils.get(guild.roles, name=base_name)
            
        if role:
             print(f"⚠️ Nalezeno dle jména: '{role.name}' (Core: {base_name}) -> {role.id}")
             return role.id
        else:
             print(f"❌ Nenalezeno: {base_name}")
             return None

    # Iterace definic
    for name, start, end in ROLE_DEFINITIONS:
        for i in range(start, end + 1):
             core_name = f"{name} {i}"
             rid = await find_role(core_name)
             if rid: found_roles[core_name] = rid

    # Legend & Unranked
    rid = await find_role(ROLE_LEGEND)
    if rid: found_roles[ROLE_LEGEND] = rid
    
    rid = await find_role(ROLE_UNRANKED)
    if rid: found_roles[ROLE_UNRANKED] = rid

    print("\n--- OUTPUT PRO CONSTANTS.PY ---")
    print("LEAGUE_ROLES = {")
    for name, role_id in found_roles.items():
        print(f'    "{name}": {role_id},')
    print("}")

# --- MODE 2: Create ---
async def mode_create(guild):
    print("\n--- [MODE 2] CREATE MISSING ROLES ---")
    
    async def ensure_role(core_name):
        target_name = f"{PREFIX}{core_name}{SUFFIX}"
        
        # Check if exists (plain or padded)
        existing = discord.utils.get(guild.roles, name=target_name)
        if not existing:
             # Try clean name too to avoid duplicates
             existing = discord.utils.get(guild.roles, name=core_name)
        
        if existing:
            print(f"ℹ️ Role '{core_name}' již existuje jako '{existing.name}' (ID: {existing.id})")
        else:
            try:
                new_role = await guild.create_role(name=target_name, reason="CoC Bot League Role")
                print(f"✅ Vytvořena role: '{target_name}' (ID: {new_role.id})")
            except Exception as e:
                print(f"❌ Chyba při vytváření {target_name}: {e}")

    for name, start, end in ROLE_DEFINITIONS:
        for i in range(start, end + 1):
            await ensure_role(f"{name} {i}")

    await ensure_role(ROLE_LEGEND)
    await ensure_role(ROLE_UNRANKED)

# --- MODE 3: Edit (Apply Padding) ---
async def mode_edit(guild):
    print("\n--- [MODE 3] EDIT / FIX PADDING ---")
    print(f"Using Prefix: '{PREFIX}'")
    print(f"Using Suffix: '{SUFFIX}'")
    
    # Iterujeme přes konstanty, protože tam máme ID, což je jistota
    for core_name, role_id in LEAGUE_ROLES.items():
        role = guild.get_role(role_id)
        
        if not role:
            print(f"⚠️ Role ID {role_id} ({core_name}) nenalezena na serveru.")
            continue
            
        # Požadovaný tvar
        target_name = f"{PREFIX}{core_name}{SUFFIX}"
        
        if role.name == target_name:
            print(f"🆗 '{core_name}' je správně: {role.name}")
        else:
            print(f"🔄 Přejmenovávám '{role.name}' -> '{target_name}'")
            try:
                await role.edit(name=target_name, reason="Fixing Role Padding")
                print("   ✅ Hotovo")
            except Exception as e:
                print(f"   ❌ Chyba: {e}")

@client.event
async def on_ready():
    print(f'[SYSTEM] Logged as {client.user}')
    guild = client.get_guild(int(GUILD_ID))
    
    if not guild:
        print(f"[ERROR] Server ID {GUILD_ID} not found.")
        await client.close()
        return

    print("Vyberte režim:")
    print("1: CHECK - Najde role a vypíše Python dictionary")
    print("2: CREATE - Vytvoří chybějící role (s paddingem)")
    print("3: EDIT   - Upraví existující role z constants.py (vynutí padding)")
    
    try:
        # Použijeme asyncio.to_thread pro input, aby neblokoval loop (i když tady je to jedno, neběží tu nic jiného)
        mode = await asyncio.to_thread(input, "Zadej číslo (1/2/3): ")
    except EOFError:
        print("Input error.")
        mode = ""

    if mode.strip() == "1":
        await mode_check(guild)
    elif mode.strip() == "2":
        await mode_create(guild)
    elif mode.strip() == "3":
        await mode_edit(guild)
    else:
        print("Neplatná volba.")

    await client.close()

if __name__ == "__main__":
    client.run(TOKEN)
