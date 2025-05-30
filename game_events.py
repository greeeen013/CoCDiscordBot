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
        self.channel_id = 1367054076688339053
        self.message_id = load_room_id("game_events_message")

    async def process_game_events(self):
        """
        Načte herní události z webu a aktualizuje nebo vytvoří Discord embed zprávu.
        """
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print("❌ [game_events] Kanál nenalezen.")
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
            # Přejmenování z "CWL" na "Clan War League"
            if title == "CWL":
                title = "Clan War League"

            emoji = EVENT_EMOJIS.get(event['title'], "🗓️")
            field_name = f"{emoji} {title}" if not event["active"] else f"🟢 {title} (Probíhá)"
            ts = event["timestamp"]
            if event["active"]:
                field_value = f"<t:{ts}>\nkončí: <t:{ts}:R>"
            else:
                field_value = f"<t:{ts}>\n<t:{ts}:R>"

            embed.add_field(name=field_name, value=field_value, inline=True)

        embed.set_footer(text="Zdroj: clash.ninja")

        try:
            if self.message_id:
                try:
                    msg = await channel.fetch_message(self.message_id)
                    await msg.edit(embed=embed)
                    print("✅ [game_events] Embed upraven.")
                    return
                except discord.NotFound:
                    print("⚠️ [game_events] Zpráva nenalezena, posílám novou.")
                    self.message_id = None

            msg = await channel.send(embed=embed)
            self.message_id = msg.id
            save_room_id("game_events_message", msg.id)
            print("✅ [game_events] Embed odeslán.")

        except Exception as e:
            print(f"❌ [game_events] Chyba při odesílání embed zprávy: {e}")