import asyncio
import json
import os

from api_handler import fetch_clan_members
from database import process_clan_data

VERIFICATION_PATH = "verification_data.json"

# === Načtení uloženého stavu zprávy ===
def load_verification_state():
    if not os.path.exists(VERIFICATION_PATH):
        return {}
    with open(VERIFICATION_PATH, "r") as f:
        return json.load(f)

# === Funkce pro hodinové tahání dat ===
async def hourly_clan_update(config: dict, bot):
    """
    Periodicky stahuje seznam členů klanu každou hodinu,
    aktualizuje databázi a zprávu s výběrem účtu.
    """
    while True:
        print("🔁 Spouštím aktualizaci seznamu členů klanu...")
        data = await fetch_clan_members(config["CLAN_TAG"], config)
        if data:
            print(f"✅ Načteno {len(data.get('items', []))} členů klanu.")
            process_clan_data(data.get("items", []))

        await asyncio.sleep(3600)
