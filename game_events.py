import discord
from typing import Optional
import json
import os
from api_handler import fetch_events_from_clash_ninja
from datetime import datetime

EVENT_EMOJIS = {
    "Raid Weekend": "<:clan_capital:1370710098158026792>",
    "Trader Refresh": "<:trader:1370708896964022324>",
    "Clan Games": "<:clan_games:1370709757761028187>",
    "League Reset": "<:league_unranked:1365740650351558787>",
    "Season End": "<:free_battlepass:1370713363188813865>",
    "CWL": "<:clan_war_league:1370712275614302309>",
}


# === Cesta k JSONu ===
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


class GameEventsHandler:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        # může být v configu
        self.channel_id = 1367054076688339053
        # 1) zkus načíst z JSON
        self.message_id = load_room_id("game_events_message")

    async def _ensure_message_id(self, channel: discord.TextChannel):
        """
        Zajistí self.message_id tak, že:
        - buď funguje fetch_message(self.message_id),
        - nebo najde poslední zprávu od bota v kanálu a uloží ji,
        - nebo pošle novou a uloží její ID.
        """
        # pokud v JSON bylo ID, ověř, že zpráva existuje
        if self.message_id:
            try:
                await channel.fetch_message(self.message_id)
                return  # vše OK
            except discord.NotFound:
                print("⚠️ [game_events] Zpráva z JSONu neexistuje, zkusím najít poslední botí zprávu.")
                # spadneme níž na hledání
            except discord.Forbidden:
                print("❌ [game_events] Nemám oprávnění číst zprávy v kanálu.")
                return
            except discord.HTTPException as e:
                print(f"❌ [game_events] HTTP chyba při fetch_message: {e}")

        # 2) najdi poslední zprávu od bota v historii kanálu
        try:
            async for m in channel.history(limit=50, oldest_first=False):
                if m.author.id == self.bot.user.id:
                    self.message_id = m.id
                    save_room_id("game_events_message", m.id)
                    print("✅ [game_events] Nalezl jsem poslední botí zprávu, budu ji editovat.")
                    return
        except discord.Forbidden:
            print("❌ [game_events] Nemám oprávnění číst historii kanálu.")
        except Exception as e:
            print(f"❌ [game_events] Chyba při procházení historie: {e}")

        # 3) pokud nic, pošli novou placeholder zprávu (bez embedu), ID si uložíme a hned ji budeme editovat
        try:
            placeholder = await channel.send("⏳ Připravuji přehled událostí…")
            self.message_id = placeholder.id
            save_room_id("game_events_message", placeholder.id)
            print("✅ [game_events] Vytvořil jsem novou referenční zprávu.")
        except Exception as e:
            print(f"❌ [game_events] Nepodařilo se vytvořit referenční zprávu: {e}")

    async def process_game_events(self):
        """
        Načte herní události z webu a aktualizuje nebo vytvoří Discord embed zprávu.
        Nikdy neposílá duplicitní zprávy – vždy edituje poslední botí zprávu v kanálu.
        """
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print("❌ [game_events] Kanál nenalezen.")
            return

        # Zajisti, že máme platné message_id (JSON → historie → nová)
        await self._ensure_message_id(channel)
        if not self.message_id:
            print("❌ [game_events] Nemám message_id, končím.")
            return

        events = fetch_events_from_clash_ninja()
        if not events:
            print("❌ [game_events] Žádná data o událostech.")
            return

        embed = discord.Embed(
            title="📆 Nadcházející Clash of Clans události",
            color=discord.Color.teal()
        )

        for event in events:
            title = event['title']
            if title == "CWL":
                title = "Clan War League"
            if title == "CWL(Sign-up Until)":
                title = "CWL (Přihlášky do..)"

            emoji = EVENT_EMOJIS.get(event['title'], "🗓️")
            field_name = f"{emoji} {title}" if not event["active"] else f"🟢 {title} (Probíhá)"
            ts = event["timestamp"]
            if event["active"]:
                field_value = f"<t:{ts}>\nkončí: <t:{ts}:R>"
            else:
                field_value = f"<t:{ts}>\n<t:{ts}:R>"

            embed.add_field(name=field_name, value=field_value, inline=True)

        embed.set_footer(text="Zdroj: clash.ninja")

        # teď už jen edituj potvrzenou zprávu
        try:
            msg = await channel.fetch_message(self.message_id)
            await msg.edit(content=None, embed=embed)
            print("✅ [game_events] Embed upraven.")
        except discord.NotFound:
            # výjimečně pokud byla smazána mezi _ensure_message_id a editací
            print("⚠️ [game_events] Zpráva zmizela, vytvořím novou.")
            msg = await channel.send(embed=embed)
            self.message_id = msg.id
            save_room_id("game_events_message", msg.id)
            print("✅ [game_events] Nový embed odeslán.")
        except Exception as e:
            print(f"❌ [game_events] Chyba při editaci embed zprávy: {e}")
