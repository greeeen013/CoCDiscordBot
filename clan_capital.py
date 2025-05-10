import discord
from datetime import datetime
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
        self.current_capital_message_id = load_room_id("capital_status_message")        # načtení ID zprávy z JSON souboru
        self._last_state = None                                                         # Sleduje předchozí stav (např. 'ongoing', 'ended')

    def _create_capital_embed(self, state: str, data: dict) -> discord.Embed:
        """
        Vytvoří a vrátí embed podle stavu capital raidu ('ongoing' nebo 'ended').
        """
        if state == "ended":
            # Embed pro ukončený raid
            embed = discord.Embed(
                title="🏁 Capital Raid: Ukončeno",
                description="Statistiky budou doplněny později...",
                color=discord.Color.red()
            )
            embed.set_footer(text="Stav: ended")
            return embed

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
        if state != self._last_state:
            print(f"ℹ️ [clan_capital] Stav se změnil na: {state}")

        self._last_state = state

        if state == "ongoing":
            embed = self._create_capital_embed(state, capital_data)
            await self.update_capital_message(embed)

        elif state == "ended" and self.current_capital_message_id:
            embed = self._create_capital_embed(state, capital_data)
            await self.update_capital_message(embed)
            self.current_capital_message_id = None
            save_room_id("capital_status_message", None)

        else:
            print("ℹ️ [clan_capital] Stav 'ended' ale žádná zpráva k úpravě neexistuje – neprovádím nic.")

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
        Převede čas ve formátu z Clash of Clans API (např. 20250509T070000.000Z)
        na datetime objekt v Pythonu.
        """
        try:
            return datetime.strptime(raw_time, "%Y%m%dT%H%M%S.%fZ")
        except Exception:
            return None
