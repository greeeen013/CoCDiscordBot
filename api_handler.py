import aiohttp
import asyncio
import requests
from bs4 import BeautifulSoup

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

async def fetch_current_war(clan_tag: str, config: dict):
    """Získává data o aktuální válce z API Clash of Clans"""
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag.replace('#', '%23')}/currentwar"
    headers = {
        "Authorization": f"Bearer {config['COC_API_KEY']}",
        "Accept": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    print(f"✅ [api_handler] Úspěšně získána data o válce pro klan {clan_tag}")
                    return await resp.json()
                elif resp.status == 404:
                    print(f"❌ [api_handler] Data o válce nenalezena (404) pro klan {clan_tag}")
                    return None
                else:
                    print(f"❌ [api_handler] Chyba při získávání dat o válce: {resp.status} - {await resp.text()}")
                    return None
        except asyncio.TimeoutError:
            print("❌ [api_handler] Timeout při získávání dat o válce")
            return None
        except Exception as e:
            print(f"❌ [api_handler] Neočekávaná chyba: {str(e)}")
            return None

async def fetch_current_capital(clan_tag: str, config: dict) -> dict | None:
    """
    Volá Clash of Clans API pro získání aktuální sezóny Capital Raidu.
    Vrací nejnovější raid ze seznamu.
    """
    url = f"{BASE_URL}/clans/{clan_tag.replace('#', '%23')}/capitalraidseasons"
    headers = get_headers(config)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    print(f"✅ [api_handler] Úspěšně získána Capital Raid data pro klan {clan_tag}")
                    data = await resp.json()
                    return data["items"][0] if data.get("items") else None
                elif resp.status == 403:
                    print(f"❌ [api_handler] Přístup odepřen při získávání Capital Raid dat (403)")
                    return None
                elif resp.status == 404:
                    print(f"❌ [api_handler] Capital Raid data nenalezena (404) pro klan {clan_tag}")
                    return None
                else:
                    print(f"❌ [api_handler] Chyba při získávání Capital Raid dat: {resp.status} - {await resp.text()}")
                    return None
        except asyncio.TimeoutError:
            print("❌ [api_handler] Timeout při získávání Capital Raid dat")
            return None
        except Exception as e:
            print(f"❌ [api_handler] Neočekávaná chyba při získávání Capital Raid dat: {str(e)}")
            return None

def fetch_events_from_clash_ninja():
    """
    Načte nadcházející události z clash.ninja a vrátí je jako seznam slovníků.
    """
    url = "https://www.clash.ninja/guides/when-are-the-next-ingame-events"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        events_divs = soup.find_all("div", class_="event-holder")

        events = []
        for div in events_divs:
            title_raw = div.find("h3")
            if not title_raw:
                continue

            title = title_raw.get_text(strip=True).replace("(Active Until)", "").strip()
            is_active = "(Active Until)" in title_raw.text

            ts = int(div.get("data-ed", 0)) // 1000  # safe fallback

            timer_div = div.find("div", class_="event-timer")
            remaining = timer_div.get_text(strip=True) if timer_div else ""

            if ts > 0:
                events.append({
                    "title": title,
                    "timestamp": ts,
                    "remaining": remaining,
                    "active": is_active
                })

        return events

    except Exception as e:
        print(f"❌ [clash_events_api] Chyba při načítání: {e}")
        return []
