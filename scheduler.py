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

    def get(self, key: str):
        return self.data.get(key)

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
    clan_war_handler = getattr(bot, "clan_war_handler", None)
    current_cwl_round = room_storage.get("current_cwl_round") or 0
    cwl_active = room_storage.get("cwl_active") or False
    cwl_group_data = None
    if clan_war_handler is None:
        clan_war_handler = ClanWarHandler(bot, config)
        bot.clan_war_handler = clan_war_handler  # uložíme pro příště
        game_events_handler = GameEventsHandler(bot, config)

    clan_capital_handler = ClanCapitalHandler(bot, config)
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
                print("\n--- Začátek nové iterace scheduleru ---")

                # Normální clan war kontrola
                print(f"[Clan War] Kontrola normální války pro klan {config['CLAN_TAG']}...")
                war_data = await fetch_current_war(config['CLAN_TAG'], config)
                if war_data:
                    print(f"[Clan War] Data války získána, stav: {war_data.get('state')}")
                    await clan_war_handler.process_war_data(war_data)
                else:
                    print("[Clan War] Žádná aktivní válka nebyla nalezena")

                # CWL logika
                cwl_active = room_storage.get("cwl_active") or False
                current_cwl_round = room_storage.get("current_cwl_round") or 0

                if cwl_active:
                    print(f"\n🔁 [CWL] Pokračuji v kole {current_cwl_round + 1}")

                    try:
                        # Získání aktuálních CWL dat
                        cwl_group_data = await api_handler.fetch_league_group(config["CLAN_TAG"], config)
                        if not cwl_group_data:
                            print("[CWL] Nepodařilo se získat CWL data, deaktivuji CWL")
                            room_storage.set("cwl_active", False)
                            continue

                        if current_cwl_round >= len(cwl_group_data.get('rounds', [])):
                            print("[CWL] Aktuální kolo je větší než počet kol v CWL, resetuji")
                            room_storage.set("cwl_active", False)
                            room_storage.set("current_cwl_round", 0)
                            continue

                        round_wars = cwl_group_data['rounds'][current_cwl_round]['warTags']
                        print(f"[CWL] Dostupné war tagy v kole: {', '.join(round_wars)}")

                        war_found = False
                        active_war_found = False

                        for war_tag in round_wars:
                            if war_tag == "#0":
                                continue

                            print(f"[CWL] Zpracovávám válku s tagem: {war_tag}")
                            try:
                                war_tag_clean = war_tag.replace('#', '')
                                war_data = await api_handler.fetch_league_war(war_tag_clean, config)
                                war_state = war_data.get('state', 'unknown')
                                print(f"[CWL] Stav války: {war_state}")

                                await clan_war_handler.process_war_data(war_data, 1)

                                if war_state == 'warEnded':
                                    war_found = True
                                elif war_state in ['preparation', 'inWar']:
                                    active_war_found = True
                                    break

                            except Exception as e:
                                print(f"[CWL] Chyba při načítání války: {str(e)}")

                        # Pokud jsme našli warEnded válku a žádná aktivní nebyla
                        if war_found and not active_war_found:
                            new_round = current_cwl_round + 1
                            room_storage.set("current_cwl_round", new_round)
                            print(f"➡️ [CWL] Uloženo nové kolo: {new_round + 1}")

                            if new_round >= len(cwl_group_data['rounds']):
                                room_storage.set("cwl_active", False)
                                room_storage.set("current_cwl_round", 0)
                                print("🔄 [CWL] Resetován CWL stav po dokončení všech kol")

                    except Exception as e:
                        print(f"[CWL] Chyba při zpracování CWL: {str(e)}")

                # Detekce nového CWL
                else:
                    print("[CWL] Kontrola zda neběží CWL...")
                    try:
                        group_data = await api_handler.fetch_league_group(config["CLAN_TAG"], config)
                        if group_data and group_data.get('state') in ['warEnded', 'inWar', 'preparation']:
                            room_storage.set("cwl_active", True)
                            room_storage.set("current_cwl_round", 0)
                            print("[CWL] Detekován nový CWL, aktivován")
                    except Exception as e:
                        print(f"[CWL] Chyba při kontrole CWL: {str(e)}")

            except Exception as e:
                print(f"[ERROR] Neočekávaná chyba v scheduleru: {str(e)}")


        else:
            print("⏸️ [Scheduler] Aktualizace seznamu klanu je momentálně pozastavena kvůli ověřování.")

        await asyncio.sleep(60 * 1,5)  # každých 15 minut

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

