
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
        stored_season = room_storage.get("cwl_season")

        if cwl_active:
            # Přidán argument config
            group_data = await api_handler.fetch_league_group(self.config["CLAN_TAG"], self.config)
            if not group_data:
                print("⚠️ [CWL] Data skupiny nedostupná, končím iteraci.")
                # Pokud API selže, nevypínáme CWL hned, ale počkáme na příští pokus
                return
            
            current_season = group_data.get("season")
            if current_season and current_season != stored_season:
                # Pokud sezónu zatím nemáme zapsanou a jsme v CWL, prostě ji uložíme (abysme neresetovali zbytečně běžící CWL při updatu bota).
                # Pokud ji ale máme a NEODPOVIDÁ, znamená to, že se stará CWL nevypla a tohle je už úplně nová liga další měsíc!
                if stored_season:
                    print(f"🔄 [CWL] Nová sezóna CWL detekována ({current_season} vs. {stored_season}). Resetuji údaje.")
                    room_storage.set("current_cwl_round", 0)
                    room_storage.set("cwl_catchup_mode", True)
                    current_round = 0
                room_storage.set("cwl_season", current_season)

            rounds = group_data.get("rounds", [])
            if current_round >= len(rounds):
                # Bezpečnostní reset pokud jsme mimo rozsah
                print("🔄 [CWL] current_cwl_round >= počet kol, resetuji.")
                room_storage.set("cwl_active", False)
                room_storage.set("current_cwl_round", 0)
                room_storage.set("cwl_catchup_mode", False)
                return

            # --- Přepracovaná iterace přes kola ---
            # Pokusíme se načíst všechny war tags pro current_round.
            # Pokud narazíme na #0, kolo ještě nezačalo API stranou.
            war_tags = rounds[current_round].get("warTags", [])
            
            if not war_tags or all(t == "#0" for t in war_tags):
                # Jsme moc daleko nebo kolo ještě nemá los
                # Pojistka pro případ, že se kolo nějak proklouzlo:
                if current_round > 0:
                    prev_tags = rounds[0].get("warTags", [])
                    if prev_tags and prev_tags[0] != "#0":
                        # Znamená to, že CWL zjevně reálně už běží aspoň od kola 0
                        # Můžeme to vynutit resetováním
                        print(f"🔄 [CWL] Objevena nekonzistence kol (aktuální {current_round} je prázdné, ale kolo 0 platí). Vracím na první kolo.")
                        room_storage.set("current_cwl_round", 0)
                        room_storage.set("cwl_catchup_mode", True)
                return
            
            active_found, ended_found = False, False
            catchup_mode = room_storage.get("cwl_catchup_mode") or False
            success_fetches = 0
            our_war_found = False

            for tag in war_tags:
                if tag == "#0":
                    continue
                
                war = await api_handler.fetch_league_war(tag, self.config)
                if not war:
                    continue
                
                success_fetches += 1
                our_tag = self.config.get("CLAN_TAG", "").strip().upper()
                clan_tag = war.get("clan", {}).get("tag", "").strip().upper()
                opp_tag = war.get("opponent", {}).get("tag", "").strip().upper()
                
                if clan_tag == our_tag or opp_tag == our_tag:
                    our_war_found = True
                    state = war.get("state")
                    
                    if state == "warEnded" and catchup_mode:
                        print(f"⏩ [CWL] Catchup: Přeskakuji zpracování ukončeného kola {current_round + 1}")
                        ended_found = True
                    else:
                        if state in ("preparation", "inWar") and catchup_mode:
                            print(f"▶️ [CWL] Catchup: Nalezeno aktivní kolo {current_round + 1}, vypínám catchup mód.")
                            room_storage.set("cwl_catchup_mode", False)
                        
                        await clan_war_handler.process_war_data(war, attacks_per_member=1)
                        print(f"🛡️ [CWL] Zpracováno kolo {current_round + 1} – state: {state}")
                        
                        if state in ("preparation", "inWar"):
                            active_found = True
                        elif state == "warEnded":
                            ended_found = True
                    break  # Našli jsme náš zápas v tomto kole, zbytek tagů nepotřebujeme checkovat
            
            # Pokud jsme nenašli žádnou náši válku (např. 404 u všech),
            # posuneme se vpřed, aby se bot nezasekl.
            # Případně pokud API vrátilo None pro všechny a kolo už muselo proběhnout.
            # Nebo pokud jsme našli "warEnded" pro nás.
            if our_war_found:
                if ended_found and not active_found:
                    new_round = current_round + 1
                    if new_round >= len(rounds):
                        print("🏁 [CWL] Dokončena všechna kola – vypínám CWL.")
                        room_storage.set("cwl_active", False)
                        room_storage.set("current_cwl_round", 0)
                        room_storage.set("cwl_catchup_mode", False)
                    else:
                        print(f"➡️ [CWL] Kolo {current_round + 1} ukončeno. Přechod na další kolo: {new_round + 1}")
                        room_storage.set("current_cwl_round", new_round)
            else:
                # Nenašli jsme naši válku (možná nedostupná API 404 pro staré kolo).
                # Pokud ale víme, že alespoň jedno API request selhalo, můžeme usoudit, že je to staré kolo.
                # Abysme se nezasekli, skipneme staré kolo po x hodinách nebo prostě posuneme.
                if success_fetches == 0 and len([t for t in war_tags if t != "#0"]) > 0:
                    # Všechny tagy selhaly posuneme
                    print(f"⚠️ [CWL] Kolo {current_round + 1} vrací 404. Posouvám na kolo {current_round + 2}.")
                    room_storage.set("current_cwl_round", current_round + 1)

        else:
            # Zkontroluj, zda začíná nová CWL sezóna
            group_data = await api_handler.fetch_league_group(self.config["CLAN_TAG"], self.config)
            if group_data and group_data.get("state") in ("preparation", "inWar"):
                current_season = group_data.get("season")
                print(f"▶️ [CWL] Detekován nový CWL (sezóna: {current_season}), aktivuji.")
                room_storage.set("cwl_active", True)
                room_storage.set("current_cwl_round", 0)
                room_storage.set("cwl_season", current_season)
                # Aktivujeme catchup mód pro případ, že začínáme uprostřed sezóny
                room_storage.set("cwl_catchup_mode", True)
