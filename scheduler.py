import asyncio
from api_handler import fetch_clan_members
from database import process_clan_data

# === Funkce pro hodinové tahání dat ===
async def hourly_clan_update(clan_tag: str, config: dict):
    """
    Periodicky stahuje seznam členů klanu každou hodinu.
    """
    while True:
        print("🔁 Spouštím aktualizaci seznamu členů klanu...")
        data = await fetch_clan_members(clan_tag, config)
        if data:
            print(f"✅ Načteno {len(data.get('items', []))} členů klanu.")
            process_clan_data(data.get("items", []))
        await asyncio.sleep(120) # Čeká 1 hodinu
