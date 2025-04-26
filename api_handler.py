import aiohttp
import asyncio
import time
import os

# === Inicializace hlaviček a základní URL ===
def get_headers(config: dict) -> dict:
    """
    Vrací hlavičky pro autorizaci API požadavků.
    """
    return {
        "Authorization": f"Bearer {config['COC_API_KEY']}"
    }

BASE_URL = "https://api.clashofclans.com/v1"

# === Funkce pro stažení seznamu členů klanu ===
async def fetch_clan_members_list(clan_tag: str, config: dict) -> dict | None:
    """
    Volá Clash of Clans API pro získání seznamu členů klanu.
    Vstup: clan_tag (např. #ABCD123)
    Výstup: dict s daty nebo None při chybě
    """
    headers = get_headers(config)
    async with aiohttp.ClientSession(headers=headers) as session:
        url = "https://api.clashofclans.com/v1/clans/%232qqopy9v8/members"
        async with session.get(url) as response:
            if response.status == 200:
                print("✅ [api_handler] Úspěšně načten seznam členů klanu.")
                return await response.json()
            else:
                print(f"❌ [api_handler] Chyba při načítání členů klanu: {response.status}")
                return None

# === Funkce pro stažení dat konkrétního hráče ===
async def fetch_player_data(player_tag: str, config: dict) -> dict | None:
    """
    Volá Clash of Clans API pro získání informací o konkrétním hráči.
    Vstup: player_tag (např. #PLAYER123)
    Výstup: dict s daty nebo None při chybě nebo překročení limitu
    """
    headers = get_headers(config)
    async with aiohttp.ClientSession(headers=headers) as session:
        url = f"{BASE_URL}/players/{player_tag.replace('#', '%23')}"
        async with session.get(url) as response:
            if response.status == 200:
                print(f"✅ [api_handler] Načten hráč {player_tag}")
                return await response.json()
            elif response.status == 429:
                print(f"⚠️ [api_handler] Překročen limit API požadavků (rate limit) při hráči {player_tag}")
                return None
            else:
                print(f"❌ [api_handler] Chyba při načítání hráče {player_tag}: {response.status}")
                return None