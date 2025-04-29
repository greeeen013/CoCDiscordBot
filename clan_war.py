import discord
from datetime import datetime
from typing import Optional

TOWN_HALL_EMOJIS = {
    17: "<:town_hall_17:1365445408096129165>",
    16: "<:town_hall_16:1365445406854615143>",
    15: "<:town_hall_15:1365445404467925032>",
    14: "<:town_hall_14:1365445402463043664>",
    13: "<:town_hall_13:1365445400177147925>",
    12: "<:town_hall_12:1365445398411477082>",
    11: "<:town_hall_11:1365445395173347458>",
    10: "<:town_hall_10:1365445393680437369>",
}


class ClanWarHandler:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.war_status_channel_id = 1366835944174391379
        self.war_events_channel_id = 1366835971395686554
        self.last_processed_order = 0
        self.current_war_message_id = None

    async def process_war_data(self, war_data: dict):
        """Zpracuje data o válce a aktualizuje Discord"""
        if not war_data:
            print("[clan_war] ❌ Žádná data o válce ke zpracování")
            return

        state = war_data.get('state', 'unknown')

        # Pokud válka skončila, smaž obsah kanálů
        if state == 'warEnded':
            await self._clear_war_channels()
            return

        # Pokud není ve válce nebo přípravě, nedělej nic
        if state not in ('inWar', 'preparation'):
            return

        try:
            # Aktualizace stavu války
            await self.update_war_status(war_data)

            # Zpracování událostí (útoků) jen pokud válka probíhá
            if state == 'inWar':
                await self.process_war_events(war_data)

        except Exception as e:
            print(f"[clan_war] ❌ Chyba při zpracování dat: {str(e)}")

    