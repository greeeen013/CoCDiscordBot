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
            print("❌ [clan_war] Žádná data o válce ke zpracování")
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
            print(f"❌ [clan_war] Chyba při zpracování dat: {str(e)}")

    async def _clear_war_channels(self):
        """Smaže obsah war kanálů"""
        try:
            status_channel = self.bot.get_channel(self.war_status_channel_id)
            events_channel = self.bot.get_channel(self.war_events_channel_id)

            if status_channel:
                await status_channel.purge(limit=100)
                print("[clan_war] Obsah kanálu se stavem války byl smazán")

            if events_channel:
                await events_channel.purge(limit=100)
                print("[clan_war] Obsah kanálu s událostmi války byl smazán")

            self.current_war_message_id = None
            self.last_processed_order = 0

        except Exception as e:
            print(f"❌ [clan_war] Chyba při mazání kanálů: {str(e)}")

    async def update_war_status(self, war_data: dict):
        """Vytvoří nebo aktualizuje embed se stavem války"""
        channel = self.bot.get_channel(self.war_status_channel_id)
        if not channel:
            print("[clan_war] ❌ Kanál pro stav války nebyl nalezen")
            return

        embed = self._create_war_status_embed(war_data)

        try:
            if self.current_war_message_id:
                try:
                    message = await channel.fetch_message(self.current_war_message_id)
                    await message.edit(embed=embed)
                except discord.NotFound:
                    self.current_war_message_id = None
                    message = await channel.send(embed=embed)
                    self.current_war_message_id = message.id
            else:
                message = await channel.send(embed=embed)
                self.current_war_message_id = message.id

        except Exception as e:
            print(f"[clan_war] ❌ Chyba při aktualizaci stavu války: {str(e)}")

    def _create_war_status_embed(self, war_data: dict) -> discord.Embed:
        """Vytvoří embed se stavem války"""
        clan = war_data.get('clan', {})
        opponent = war_data.get('opponent', {})
        state = war_data.get('state', 'unknown').capitalize()

        embed = discord.Embed(
            title=f"Clan War: {clan.get('name', 'Náš klan')} vs {opponent.get('name', 'Protivník')}",
            color=discord.Color.blue() if state == "Inwar" else discord.Color.gold()
        )

        # Horní část - základní informace
        our_stats = (
            f"**{clan.get('stars', 0)}⭐**\n"
            f"Útoky: {clan.get('attacks', 0)}/{war_data.get('teamSize', 0) * war_data.get('attacksPerMember', 2)}\n"
            f"{clan.get('destructionPercentage', 0)}%"
        )

        their_stats = (
            f"**{opponent.get('stars', 0)}⭐**\n"
            f"Útoky: {opponent.get('attacks', 0)}/{war_data.get('teamSize', 0) * war_data.get('attacksPerMember', 2)}\n"
            f"{opponent.get('destructionPercentage', 0)}%"
        )

        embed.add_field(name=f"**{clan.get('name', 'Náš klan')}**", value=our_stats, inline=True)
        embed.add_field(name="\u200b", value="**VS**", inline=True)
        embed.add_field(name=f"**{opponent.get('name', 'Protivník')}**", value=their_stats, inline=True)

        # Časy války
        prep_time = self._parse_coc_time(war_data.get('preparationStartTime', ''))
        start_time = self._parse_coc_time(war_data.get('startTime', ''))
        end_time = self._parse_coc_time(war_data.get('endTime', ''))

        time_fields = [
            ("🛡️ Příprava začala", prep_time),
            ("⚔️ Válka začala", start_time),
            ("🏁 Konec války", end_time)
        ]

        for name, time in time_fields:
            if time:
                embed.add_field(
                    name=name,
                    value=f"<t:{int(time.timestamp())}:F>\n(`<t:{int(time.timestamp())}:R>`)",
                    inline=True
                )

        # Členové (pouze pokud válka probíhá)
        if war_data.get('state') == 'inWar':
            our_members = "\n".join(
                f"{TOWN_HALL_EMOJIS.get(m.get('townhallLevel', 10), '')} {m.get('name', 'Unknown')} "
                f"({len(m.get('attacks', []))}/{war_data.get('attacksPerMember', 2)})"
                for m in sorted(clan.get('members', []), key=lambda x: x.get('mapPosition', 0))
            )

            their_members = "\n".join(
                f"{TOWN_HALL_EMOJIS.get(m.get('townhallLevel', 10), '')} {m.get('name', 'Unknown')} "
                f"({len(m.get('attacks', []))}/{war_data.get('attacksPerMember', 2)})"
                for m in sorted(opponent.get('members', []), key=lambda x: x.get('mapPosition', 0))
            )

            embed.add_field(name="**Naši hráči**", value=our_members[:1024] or "Žádní", inline=True)
            embed.add_field(name="**Jejich hráči**", value=their_members[:1024] or "Žádní", inline=True)

        embed.set_footer(text=f"Stav války: {state}")
        return embed
