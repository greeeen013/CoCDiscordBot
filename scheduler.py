import asyncio
import json
import os
from datetime import datetime

import aiohttp

import api_handler
from api_handler import fetch_clan_members_list, fetch_player_data
from database import process_clan_data, get_all_links, get_all_members, cleanup_old_warnings
from member_tracker import discord_sync_members_once
from role_giver import update_roles
from api_handler import fetch_current_war, fetch_current_capital
from clan_war import ClanWarHandler
from clan_capital import ClanCapitalHandler
from game_events import GameEventsHandler
from clan_war_league import ClanWarLeagueHandler




# === Stav pozastavení hodinového updatu ===
is_hourly_paused = False

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOM_IDS_PATH = os.path.join(THIS_DIR, "discord_rooms_ids.json")
class RoomIdStorage:
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        try:
            if os.path.exists(ROOM_IDS_PATH):
                with open(ROOM_IDS_PATH, "r") as f:
                    self.data = json.load(f)
        except Exception as e:
            print(f"[clan_war] [discord_rooms_ids] Chyba při čtení: {e}")
            self.data = {}

    def save(self):
        try:
            with open(ROOM_IDS_PATH, "w") as f:
                json.dump(self.data, f)
        except Exception as e:
            print(f"[clan_war] [discord_rooms_ids] Chyba při zápisu: {e}")

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()

    def remove(self, key: str):
        if key in self.data:
            del self.data[key]
            self.save()

room_storage = RoomIdStorage()
# === Funkce pro hodinové tahání dat ===
async def hourly_clan_update(config: dict, bot):
    # Získání nebo vytvoření ClanWarHandleru
    clan_war_handler = getattr(bot, "clan_war_handler", None)  # Pokus o získání existujícího handleru z bot objektu
    current_cwl_round = room_storage.get("current_cwl_round") or 0  # Načtení aktuálního kola CWL z úložiště
    cwl_active = room_storage.get("cwl_active") or False  # Načtení stavu CWL z úložiště
    cwl_group_data = None  # Inicializace proměnné pro data CWL skupiny

    # Pokud ClanWarHandler neexistuje, vytvoříme nový
    if clan_war_handler is None:
        clan_war_handler = ClanWarHandler(bot, config)  # Vytvoření nového handleru
        bot.clan_war_handler = clan_war_handler  # Uložení handleru do bot objektu pro budoucí použití
        game_events_handler = GameEventsHandler(bot, config)  # Vytvoření GameEventsHandleru (původní verze)

    # Získání nebo vytvoření GameEventsHandleru (nová, robustnější verze)
    game_events_handler = getattr(bot, "game_events_handler", None)  # Pokus o získání existujícího handleru
    if game_events_handler is None:
        game_events_handler = GameEventsHandler(bot, config)  # Vytvoření nového handleru
        bot.game_events_handler = game_events_handler  # Uložení handleru do bot objektu

    # Vytvoření handleru pro Clan Capital (vždy nová instance)
    clan_capital_handler = ClanCapitalHandler(bot, config)

    # Vytvoření handleru pro CWL
    clan_war_league_handler = ClanWarLeagueHandler(bot, config)

    # Hlavní smyčka
    while True:
        if not is_hourly_paused:
            print(
                f"🕒 [Scheduler] spouštím hourly_clan_update Aktuální datum a čas: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

            # === Kontrola Discord uživatelů ===
            try:
                await discord_sync_members_once(bot)
            except Exception as e:
                print(f"[scheduler] ⚠️ member sync chyba: {e}")

            # === Načtení guildy ===
            guild = bot.get_guild(config["GUILD_ID"])
            if guild is None:
                print(f"❌ [Scheduler] Guild s ID {config['GUILD_ID']} nebyl nalezen.")
                await asyncio.sleep(60)
                continue

            # === Načtení seznamu členů klanu ===
            print("🔁 [Scheduler] Spouštím aktualizaci seznamu členů klanu...")
            try:
                data = await fetch_clan_members_list(config["CLAN_TAG"], config)
                if data:
                    print(f"✅ [Scheduler] Načteno {len(data.get('items', []))} členů klanu.")
                    process_clan_data(data.get("items", []), bot=bot)
                else:
                    print("⚠️ [Scheduler] Nepodařilo se získat seznam členů klanu.")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"❌ [Scheduler] Chyba při načítání členů klanu: {e}")
            except Exception as e:
                print(f"❌ [Scheduler] Neočekávaná chyba při fetch_clan_members_list: {e}")

            # === Aktualizace rolí ===
            try:
                print("🔄 [Scheduler] Spouštím automatickou aktualizaci rolí...")
                links = get_all_links()
                members = get_all_members()
                await update_roles(guild, links, members)
                print("✅ [Scheduler] Aktualizace rolí dokončena.")
            except Exception as e:
                print(f"❌ [Scheduler] Chyba při aktualizaci rolí: {e}")

            # === CAPITAL STATUS ===
            try:
                capital_data = await fetch_current_capital(config["CLAN_TAG"], config)
                if capital_data:
                    await clan_capital_handler.process_capital_data(capital_data)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"❌ [Scheduler] Chyba při načítání capital dat: {e}")
            except Exception as e:
                print(f"❌ [Scheduler] Neočekávaná chyba v CAPITAL části: {e}")

            # === GAME EVENTS ===
            try:
                if 'game_events_handler' in locals():
                    await game_events_handler.process_game_events()
            except Exception as e:
                print(f"❌ [Scheduler] Chyba při zpracování game eventů: {e}")

            # === VAROVÁNÍ ===
            try:
                await cleanup_old_warnings()
            except Exception as e:
                print(f"❌ [Scheduler] Chyba při mazání varování: {e}")

            # === CLAN WAR and CLAN WAR LEAGUE ===
            try:
                # --- Normální války ---
                war_data = await api_handler.fetch_current_war(config["CLAN_TAG"], config)
                war_active = False
                
                if war_data and war_data.get("state") in ("preparation", "inWar"):
                    war_active = True
                    await clan_war_handler.process_war_data(war_data)
                elif war_data and war_data.get("state") == "warEnded":
                    await clan_war_handler.process_war_data(war_data)
                else:
                    pass  # žádná aktivní war

                # Kontrola reminderu (19:00)
                await clan_war_handler.check_schedule_reminder(war_active)

                # --- CWL ---
                await clan_war_league_handler.handle_cwl_status(clan_war_handler)

            except Exception as e:
                print(f"[SCHEDULER] Chyba v CWL/war sekci: {e}")


        else:
            print("⏸️ [Scheduler] Aktualizace seznamu klanu je momentálně pozastavena kvůli ověřování.")

        await asyncio.sleep(60 * 3)  # každých 3 minut

# === Funkce pro pozastavení hodinového updatu ===
def pause_hourly_update():
    """
    Nastaví příznak pro pozastavení hodinového updatu dat.
    """
    global is_hourly_paused
    is_hourly_paused = True
    print("⏸️ [scheduler] Hourly update byl pozastaven.")

# === Funkce pro obnovení hodinového updatu ===
def resume_hourly_update():
    """
    Vrátí zpět příznak, aby hourly update znovu běžel.
    """
    global is_hourly_paused
    is_hourly_paused = False
    print("▶️ [scheduler] Hourly update byl obnoven.")

# === Nová funkce pro verifikační smyčku ===
async def verification_check_loop(bot, player_tag, user, verification_channel, config):
    from verification import process_verification, end_verification

    print(f"🚀 Zahajuji ověřování hráče {user} s tagem {player_tag}")
    pause_hourly_update()

    try:
        player_data = await fetch_player_data(player_tag, config)
        if not player_data:
            raise ValueError("Nepodařilo se načíst data hráče")

        selected_item = await process_verification(bot, player_data, user, verification_channel)
        if not selected_item:
            raise ValueError("Nelze vybrat vybavení pro ověření")

        # Hlavní smyčka ověřování
        for try_num in range(1, 7):  # 6 pokusů
            await asyncio.sleep(300)

            player_data = await fetch_player_data(player_tag, config)
            if not player_data:
                continue

            result = await process_verification(bot, player_data, user, verification_channel, selected_item)
            if result == "verified":
                print(f"✅ Hráč {user} úspěšně ověřen")
                return  # Ukončí funkci, end_verification se zavolá v succesful_verification

        # Timeout po 6 pokusech
        await verification_channel.send("❌ Časový limit pro ověření vypršel")
        raise TimeoutError("Vypršel časový limit pro ověření")

    except Exception as e:
        print(f"❌ Chyba při ověřování {user}: {e}")
    finally:
        # Vždy uklidíme, i když dojde k chybě
        await end_verification(user, verification_channel)
        resume_hourly_update()
