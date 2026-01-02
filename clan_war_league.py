
import api_handler
from clan_war import room_storage  # Reuse storage from clan_war.py

class ClanWarLeagueHandler:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    async def handle_cwl_status(self, clan_war_handler):
        """
        Zpracovává logiku pro Clan War League (CWL).
        Kontroluje stav CWL, přepíná kola a volá zpracování válek.
        """
        cwl_active = room_storage.get("cwl_active") or False
        current_round = room_storage.get("current_cwl_round") or 0

        if cwl_active:
            # Přidán argument config
            group_data = await api_handler.fetch_league_group(self.config["CLAN_TAG"], self.config)
            if not group_data:
                print("[CWL] Data skupiny nedostupná, končím iteraci.")
                room_storage.set("cwl_active", False)
                return  # Added return to avoid referencing None

            rounds = group_data.get("rounds", [])
            if current_round >= len(rounds):
                # Bezpečnostní reset pokud jsme mimo rozsah
                print("[CWL] current_cwl_round >= počet kol, resetuji.")
                room_storage.set("cwl_active", False)
                room_storage.set("current_cwl_round", 0)
                return  # Added return after reset

            war_tags = rounds[current_round].get("warTags", [])
            active_found, ended_found = False, False

            for tag in war_tags:
                if tag == "#0":  # budoucí kolo
                    continue
                # Přidán argument config
                war = await api_handler.fetch_league_war(tag, self.config)
                if not war:
                    continue

                if war["clan"]["tag"] == self.config["CLAN_TAG"] or war["opponent"]["tag"] == self.config["CLAN_TAG"]:
                    # Zde používáme předaný clan_war_handler pro zpracování konkrétní války
                    await clan_war_handler.process_war_data(war, attacks_per_member=1)
                    state = war.get("state")
                    print(f"[CWL] round {current_round + 1} – state: {state}")
                    if state in ("preparation", "inWar"):
                        active_found = True
                        break
                    elif state == "warEnded":
                        ended_found = True

            if ended_found and not active_found:
                new_round = current_round + 1
                if new_round >= len(rounds):
                    print("[CWL] Dokončena všechna kola – vypínám CWL.")
                    room_storage.set("cwl_active", False)
                    room_storage.set("current_cwl_round", 0)
                else:
                    print(f"[CWL] Přechod na další kolo: {new_round + 1}")
                    room_storage.set("current_cwl_round", new_round)

        else:
            # Zkontroluj, zda začíná nová CWL sezóna
            # Přidán argument config
            group_data = await api_handler.fetch_league_group(self.config["CLAN_TAG"], self.config)
            if group_data and group_data.get("state") in ("preparation", "inWar"):
                print("[CWL] Detekován nový CWL, aktivuji.")
                room_storage.set("cwl_active", True)
                room_storage.set("current_cwl_round", 0)
