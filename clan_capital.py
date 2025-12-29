import discord
from datetime import datetime, timezone, timedelta
from typing import Optional
import json
import json
import os

from database import notify_single_warning
from constants import CAPITAL_STATUS_CHANNEL_ID, PRAISE_CHANNEL_ID, EVENT_EMOJIS



# === Nastavení cesty k JSON souboru ===
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOM_IDS_PATH = os.path.join(THIS_DIR, "discord_rooms_ids.json")

def load_room_id(key: str):
    if os.path.exists(ROOM_IDS_PATH):
        try:
            with open(ROOM_IDS_PATH, "r") as f:
                data = json.load(f)
                return data.get(key)
        except Exception as e:
            print(f"❌ [discord_rooms_ids] Chyba při čtení: {e}")
    return None

def save_room_id(key: str, message_id: Optional[int]):
    try:
        data = {}
        if os.path.exists(ROOM_IDS_PATH):
            with open(ROOM_IDS_PATH, "r") as f:
                data = json.load(f)
        if message_id is None:
            data.pop(key, None)
        else:
            data[key] = message_id
        with open(ROOM_IDS_PATH, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ [discord_rooms_ids] Chyba při zápisu: {e}")


class ClanCapitalHandler:
    def __init__(self, bot, config):
        """
        Inicializace handleru pro správu Capital Raid embed zprávy.
        """
        self.bot = bot                                                                  # Discord bot instance
        self.config = config                                                            # Konfigurační slovník (obsahuje např. COC API klíč, GUILD_ID apod.)
        self.capital_status_channel_id = CAPITAL_STATUS_CHANNEL_ID                      # ID Discord kanálu, kam se bude embed posílat
        self.announcement_channel_id = PRAISE_CHANNEL_ID                                # ID kanálu pro oznámení nejlepšího výsledku
        self.current_capital_message_id = load_room_id("capital_status_message")        # načtení ID zprávy z JSON souboru
        self._last_state = None                                                         # Sleduje předchozí stav (např. 'ongoing', 'ended')
        self._has_announced_end = False                                                 # Flag pro sledování, zda byl oznámen konec raidu
        self._best_result_sent = False                                                  # Flag pro sledování, zda byl odeslán nejlepší výsledek
        self.warnings_file = os.path.join(THIS_DIR, "capital_warnings.json")
        self.pending_warnings = {}                                                      # {district_id: {attacker_tag: timestamp}}
        self.sent_warnings = set()                                                      # {unique_id}
        self.load_warnings()

    def load_warnings(self):
        """Načte stav varování z JSON souboru."""
        if os.path.exists(self.warnings_file):
            try:
                with open(self.warnings_file, "r") as f:
                    data = json.load(f)
                    self.pending_warnings = data.get("pending", {})
                    self.sent_warnings = set(data.get("sent_ids", []))
            except Exception as e:
                print(f"❌ [clan_capital] Chyba při načítání varování: {e}")

    def save_warnings(self):
        """Uloží stav varování do JSON souboru."""
        try:
            data = {
                "pending": self.pending_warnings,
                "sent_ids": list(self.sent_warnings)
            }
            with open(self.warnings_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"❌ [clan_capital] Chyba při ukládání varování: {e}")

    async def check_warnings(self, capital_data: dict):
        """
        Zkontroluje podmínky pro varování:
        1. Hráč nechal district na >75% a má ještě útok (trvá > 6 minut).
        2. Hráč nechal district na >75% a někdo jiný ho dodělal (a původní měl útoky).
        """
        if not capital_data:
            return

        # 1. Zjistíme zbývající útoky pro všechny členy
        members_map = {} # tag -> remaining_attacks
        for m in capital_data.get("members", []):
            limit = m.get("attackLimit", 0) + m.get("bonusAttackLimit", 0)
            used = m.get("attacks", 0)
            remaining = limit - used
            members_map[m.get("tag")] = remaining

        # 2. Projdeme aktivní/nedávný raid (hledáme ten ongoing nebo ended, který je relevantní)
        # Většinou nás zajímá ongoing, nebo ended pokud zrovna skončil.
        # Ale pozor, warningy chceme posílat hlavně live.
        # V example JSON je 'items' s jedním 'ongoing' prvkem.
        # capital_data je obvykle ten jeden prvek (z process_capital_data se volá s `capital_data` což je item).
        
        attack_log = capital_data.get("attackLog", [])
        
        # Projdeme všechny defendery v attackLogu (což jsou klany, na které útočíme)
        for raid_clan in attack_log:
            districts = raid_clan.get("districts", [])
            for district in districts:
                district_id = str(district.get("id"))
                district_name = district.get("name")
                attacks = district.get("attacks", []) # Seznam útoků, předpokládáme [nejnovější, ..., nejstarší]
                
                if not attacks:
                    continue

                # --- SCÉNÁŘ B: Někdo to "vyžral" (Stolen) ---
                # Procházíme útoky a hledáme situaci: Útok A (>75%), pak Útok B (jiný hráč).
                # attacks je [Last, Prev, PrevPrev...]
                for i in range(len(attacks) - 1):
                    current_attack = attacks[i]      # Novější
                    previous_attack = attacks[i+1]   # Starší (ten co to nechal)
                    
                    prev_percent = previous_attack.get("destructionPercent", 0)
                    
                    # Pokud ten předchozí to nechal na >= 75% a < 100%
                    if 75 < prev_percent < 100:
                        prev_tag = previous_attack.get("attacker", {}).get("tag")
                        curr_tag = current_attack.get("attacker", {}).get("tag")
                        
                        # A útočník se změnil
                        if prev_tag != curr_tag:
                            # A ten předchozí MÁ (stále) k dispozici útoky
                            if members_map.get(prev_tag, 0) > 0:
                                warning_id = f"stolen-{district_id}-{prev_tag}-{i}" # Unique ID pro tuto událost
                                
                                if warning_id not in self.sent_warnings:
                                    prev_name = previous_attack.get("attacker", {}).get("name")
                                    curr_name = current_attack.get("attacker", {}).get("name")
                                    
                                    msg = (f"⚠️ **Clan Capital Warning (Stolen Warning)**\n"
                                           f"Hráč **{prev_name}** nechal district `{district_name}` na **{prev_percent}%** "
                                           f"a měl ještě útoky!\n"
                                           f"District následně napadl/dodelal **{curr_name}**.")
                                           
                                    await self.send_log_message(msg)
                                    self.sent_warnings.add(warning_id)
                                    self.save_warnings()

                                    # Přidání varování
                                    await notify_single_warning(
                                        bot=self.bot,
                                        coc_tag=prev_tag,
                                        date_time=datetime.now().strftime("%d/%m/%Y %H:%M"),
                                        reason="nedokončený district v clan capital"
                                    )

                # --- SCÉNÁŘ A: Ongoing "zaseknutí" ---
                # Zajímá nás jen nejnovější stav districtu
                latest_attack = attacks[0]
                latest_percent = latest_attack.get("destructionPercent", 0)
                
                # Pokud je district "živý" (není 100%) a je > 75%
                if 75 < latest_percent < 100:
                    attacker_tag = latest_attack.get("attacker", {}).get("tag")
                    attacker_name = latest_attack.get("attacker", {}).get("name")
                    
                    # Má útočník ještě útoky?
                    if members_map.get(attacker_tag, 0) > 0:
                        pending_key = f"{district_id}-{attacker_tag}"
                        now_ts = datetime.now(timezone.utc).timestamp()
                        
                        warning_id = f"stuck-{district_id}-{attacker_tag}"
                        
                        # Pokud o něm ještě nevíme, začneme stopovat čas
                        if pending_key not in self.pending_warnings:
                            self.pending_warnings[pending_key] = now_ts
                            self.save_warnings()
                            print(f"[TIME] [clan_capital] Warning countdown started for {attacker_name} on {district_name} ({latest_percent}%).")
                        else:
                            # Už o něm víme, zkontrolujeme čas
                            start_ts = self.pending_warnings[pending_key]
                            # 6 minut = 360 sekund
                            if (now_ts - start_ts) > 360:
                                if warning_id not in self.sent_warnings:
                                    msg = (f"⚠️ **Clan Capital Warning (Incomplete District)**\n"
                                           f"Hráč **{attacker_name}** nechal district `{district_name}` na **{latest_percent}%** "
                                           f"již déle než 6 minut a stále má nevyužité útoky!")
                                    
                                    await self.send_log_message(msg)
                                    self.sent_warnings.add(warning_id)
                                    self.save_warnings()
                    else:
                        # Pokud už nemá útoky, vyhodíme z pending (už nemůže dokončit)
                        pending_key = f"{district_id}-{attacker_tag}"
                        if pending_key in self.pending_warnings:
                            del self.pending_warnings[pending_key]
                            self.save_warnings()
                else:
                    # District je 100% nebo < 75%, vyčistíme pending pokud existuje pro posledního útočníka
                    if attacks:
                        attacker_tag = attacks[0].get("attacker", {}).get("tag")
                        pending_key = f"{district_id}-{attacker_tag}"
                        if pending_key in self.pending_warnings:
                            del self.pending_warnings[pending_key]
                            self.save_warnings()

    async def send_log_message(self, content: str):
        """Odešle zprávu do logovacího kanálu."""
        log_channel_id = getattr(self.bot, "log_channel_id", None)
        if log_channel_id:
            channel = self.bot.get_channel(log_channel_id)
            if channel:
                try:
                    await channel.send(content)
                except Exception as e:
                    print(f"❌ [clan_capital] Nepodařilo se poslat varování: {e}")
            else:
                 print(f"❌ [clan_capital] Logovací kanál {log_channel_id} nebyl nalezen.")
        else:
            print("❌ [clan_capital] ID logovacího kanálu není nastaveno.")


    def _create_capital_embed(self, state: str, data: dict) -> discord.Embed:
        """
        Vytvoří a vrátí embed podle stavu capital raidu ('ongoing' nebo 'ended').
        """

        # Embed pro probíhající raid
        start = self._parse_time(data.get("startTime"))      # začátek jako datetime
        end = self._parse_time(data.get("endTime"))          # konec jako datetime
        start_ts = int(start.timestamp()) if start else 0    # timestamp pro Discord tag
        end_ts = int(end.timestamp()) if end else 0
        emoji = EVENT_EMOJIS.get("Capital District", "🏰")
        embed = discord.Embed(
            title=f"{emoji} Capital Raid",
            color=discord.Color.purple()
        )

        # Začátek a konec s formátem Discordu (zobrazí jak konkrétní datum, tak relativní čas)
        embed.add_field(
            name="🏁 Začátek",
            value=f"<t:{start_ts}>\n<t:{start_ts}:R>",
            inline=True
        )
        embed.add_field(
            name="📍 Konec",
            value=f"<t:{end_ts}>\n<t:{end_ts}:R>",
            inline=True
        )
        emoji = EVENT_EMOJIS.get("Capital Gold", "💰")
        # Statistiky s centrovaným formátem a monospaced fontem
        embed.add_field(
            name=f"{emoji} Loot",
            value=f"`{data.get('capitalTotalLoot', 0):^10,}`",
            inline=True
        )
        emoji = EVENT_EMOJIS.get("Capital Destroyed District", "⚔️️")
        embed.add_field(
            name=f"️{emoji} Raidů dokončeno",
            value=f"`{data.get('raidsCompleted', 0):^10}`",
            inline=True
        )
        emoji = EVENT_EMOJIS.get("Clan Capital", "⚔️️")
        embed.add_field(
            name=f"{emoji} Attacks",
            value=f"`{data.get('totalAttacks', 0):^10}`",
            inline=True
        )
        emoji = EVENT_EMOJIS.get("Capital District", "🏙️")
        embed.add_field(
            name=f"{emoji} Zničeno Disctrictů",
            value=f"`{data.get('enemyDistrictsDestroyed', 0):^10}`",
            inline=True
        )

        embed.set_footer(text="Stav: ongoing")
        return embed

    async def process_capital_data(self, capital_data: dict):
        """
        Zpracuje předaná data z Clash of Clans API a aktualizuje embed.
        Pokud došlo ke změně stavu raidu, zapíše do konzole.
        """
        self.current_capital_message_id = load_room_id("capital_status_message")
        if not capital_data:
            print("❌ [clan_capital] Žádná data o raidu ke zpracování")
            return

        # Získáme aktuální stav (např. 'ongoing' nebo 'ended')
        state = capital_data.get('state', 'unknown')

        # Pokud se stav změnil od minula, informujeme v konzoli
        if self._last_state is None:
            print("ℹ️ [clan_capital] První zpracování dat.")
        elif state != self._last_state:
            print(f"🔁 [clan_capital] Stav se změnil z {self._last_state} -> {state}")

        # --- oznámení o skončení -------------------------------------------
        # Proběhne jen pokud clan capital právě skončilo a poslední stav není none a není ended a ještě nebyl announcment
        if state == "ended" and self._last_state and self._last_state !="ended" and not self._has_announced_end:
            self._has_announced_end = True

            # ✅ Upravíme embed zprávu naposledy – jen změníme footer na 'Stav: ended'
            if self.current_capital_message_id:
                channel = self.bot.get_channel(self.capital_status_channel_id)
                try:
                    msg = await channel.fetch_message(self.current_capital_message_id)
                    embed = msg.embeds[0]
                    embed.set_footer(text="Stav: ended")
                    await msg.edit(embed=embed)
                    print("✅ [clan_capital] Footer embedu upraven na 'Stav: ended'.")
                    
                    # Zapomeneme ID zprávy, aby příští raid začal nový
                    self.current_capital_message_id = None
                    save_room_id("capital_status_message", None)
                    print("🗑️ [clan_capital] ID zprávy smazáno z paměti pro příští raid.")

                except Exception as e:
                    print(f"⚠️ [clan_capital] Nepodařilo se upravit embed: {e}")

            # ✅ Najdeme hráče s nejvyšším capitalResourcesLooted
            best_player = max(
                capital_data.get("members", []),
                key=lambda m: m.get("capitalResourcesLooted", 0),
                default=None
            )

            if best_player and best_player.get("capitalResourcesLooted", 0) > 0:
                name = best_player.get("name", "Neznámý hráč")
                gold = best_player.get("capitalResourcesLooted", 0)
                mention = f"@{name}"
                channel = self.bot.get_channel(self.announcement_channel_id)
                if channel:
                    try:
                        await channel.send(
                            f"{mention}\nza nejlepší výsledek v clan capital s {gold:,} {EVENT_EMOJIS.get('Capital Gold', '💰')}"
                        )
                        print(f"🏅 [clan_capital] Pochvala odeslána pro {name} s {gold} goldy.")
                    except Exception as e:
                        print(f"❌ [clan_capital] Chyba při posílání pochvaly: {e}")
                else:
                    print("❌ [clan_capital] Pochvalový kanál nenalezen.")
            else:
                print("⚠️ [clan_capital] Nebyl nalezen vhodný hráč k pochvale.")

        elif state == "ongoing":
            # Reset stavů
            self._has_announced_end = False
            embed = self._create_capital_embed(state, capital_data)
            await self.update_capital_message(embed)
            await self.check_warnings(capital_data)

        else:
            print("ℹ️ [clan_capital] Stav 'ended' – embed se již dál nemění.")

        self._last_state = state

    async def update_capital_message(self, embed: discord.Embed):
        """
        Vloží nebo aktualizuje embed zprávu v určeném Discord kanálu.
        """
        channel = self.bot.get_channel(self.capital_status_channel_id)
        if not channel:
            print("❌ [clan_capital] Kanál nenalezen")
            return

        try:
            # Pokud máme uložené ID zprávy, pokusíme se ji upravit
            if self.current_capital_message_id:
                try:
                    msg = await channel.fetch_message(self.current_capital_message_id)
                    await msg.edit(embed=embed)
                    print("✅ [clan_capital] Embed byl upraven.")
                    return
                except discord.NotFound:
                    # Pokud zpráva s daným ID neexistuje (např. byla smazána), pošleme novou
                    print("⚠️ [clan_capital] Zpráva nenalezena, posílám novou.")
                    self.current_capital_message_id = None

            # Nové odeslání zprávy
            msg = await channel.send(embed=embed)
            self.current_capital_message_id = msg.id
            save_room_id("capital_status_message", msg.id)
            print("✅ [clan_capital] Embed byl odeslán.")

        except Exception as e:
            print(f"❌ [clan_capital] Chyba při aktualizaci embed zprávy: {str(e)}")

    def _parse_time(self, raw_time: str) -> Optional[datetime]:
        """
        Převede čas z CoC API (např. 20250509T070000.000Z) na UTC datetime.
        Vrací offset-aware objekt v UTC (pro správné výpočty).
        """
        try:
            return datetime.strptime(raw_time, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)
        except Exception:
            return None
