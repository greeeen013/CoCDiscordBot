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

