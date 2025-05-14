import discord
from datetime import datetime, timezone
from typing import Optional
import json
import os

EVENT_EMOJIS = {
    "Capital Gold": "<:capital_gold:1370839359896551677>",
    "Clan Capital": "<:clan_capital:1370710098158026792>",
    "Capital District": "<:capital_district:1370841273128456392>",
    "Capital Destroyed District": "<:capital_destroyed_district:1370843785688518706>",
    "Season End": "<:free_battlepass:1370713363188813865>",
    "CWL": "<:clan_war_league:1370712275614302309>",
}

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
        self.capital_status_channel_id = 1370467834932756600                            # ID Discord kanálu, kam se bude embed posílat
        self.announcement_channel_id = 1371170358056452176                              # ID kanálu pro oznámení nejlepšího výsledku
        self.current_capital_message_id = load_room_id("capital_status_message")        # načtení ID zprávy z JSON souboru
        self._last_state = None                                                         # Sleduje předchozí stav (např. 'ongoing', 'ended')
        self._has_announced_end = False                                                 # Flag pro sledování, zda byl oznámen konec raidu
        self._best_result_sent = False                                                  # Flag pro sledování, zda byl odeslán nejlepší výsledek

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
            title=f"{emoji} Capital Raid: Probíhá",
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
