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
            print("❌ [clan_war] Kanál pro stav války nebyl nalezen")
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
            print(f"❌ [clan_war] Chyba při aktualizaci stavu války: {str(e)}")

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

    async def process_war_events(self, war_data: dict):
        """Zpracuje nové události ve válce (útoky)"""
        channel = self.bot.get_channel(self.war_events_channel_id)
        if not channel:
            print("❌ [clan_war] Kanál pro události války nebyl nalezen")
            return

        attacks = []
        for member in war_data.get('clan', {}).get('members', []):
            attacks.extend(member.get('attacks', []))
        for member in war_data.get('opponent', {}).get('members', []):
            attacks.extend(member.get('attacks', []))

        new_attacks = [a for a in attacks if a.get('order', 0) > self.last_processed_order]
        if not new_attacks:
            return

        new_attacks.sort(key=lambda x: x.get('order', 0))

        for attack in new_attacks:
            await self._send_attack_embed(channel, attack, war_data)
            self.last_processed_order = max(self.last_processed_order, attack.get('order', 0))

    async def _send_attack_embed(self, channel, attack: dict, war_data: dict):
        """Vytvoří embed pro jeden útok"""
        attacker = self._find_member_by_tag(attack.get('attackerTag'), war_data)
        defender = self._find_member_by_tag(attack.get('defenderTag'), war_data)

        if not attacker or not defender:
            return

        is_our_attack = any(m.get('tag') == attacker.get('tag') for m in war_data.get('clan', {}).get('members', []))
        discord_mention = await self._get_discord_mention(attack.get('attackerTag'))

        # Double-check pro Discord ping
        if discord_mention:
            print(f"✅ [clan_war] Nalezen Discord uživatel pro tag {attack.get('attackerTag')}: {discord_mention}")

        embed = discord.Embed(
            color=discord.Color.green() if attack.get('stars', 0) == 3 else
            discord.Color.orange() if attack.get('stars', 0) >= 1 else
            discord.Color.red()
        )

        if is_our_attack:
            left_side = attacker
            right_side = defender
            action = "**ÚTOK** ⚔️"
            arrow = "➡️"
        else:
            left_side = defender
            right_side = attacker
            action = "**OBRANA** 🛡️"
            arrow = "⬅️"

        # Levá strana (náš hráč)
        left_field = (
            f"{discord_mention or ''}\n"
            f"{TOWN_HALL_EMOJIS.get(left_side.get('townhallLevel', 10), '')} {left_side.get('name', 'Unknown')}"
        )

        # Prostřední akce
        middle_field = (
            f"{action}\n"
            f"{arrow}   {'⭐' * attack.get('stars', 0)}\n"
            f"   {attack.get('destructionPercentage', 0)}%"
        )

        # Pravá strana (protivník)
        right_field = f"{TOWN_HALL_EMOJIS.get(right_side.get('townhallLevel', 10), '')} {right_side.get('name', 'Unknown')}"

        embed.add_field(name="\u200b", value=left_field, inline=True)
        embed.add_field(name="\u200b", value=middle_field, inline=True)
        embed.add_field(name="\u200b", value=right_field, inline=True)

        embed.set_footer(text=f"Útok #{attack.get('order', 0)} | Trvání: {attack.get('duration', 0)}s")

        await channel.send(embed=embed)

    def _find_member_by_tag(self, tag: str, war_data: dict) -> Optional[dict]:
        """Najde člena podle tagu"""
        if not tag:
            return None
        for member in war_data.get('clan', {}).get('members', []):
            if member.get('tag') == tag:
                return member
        for member in war_data.get('opponent', {}).get('members', []):
            if member.get('tag') == tag:
                return member
        return None

    async def _get_discord_mention(self, coc_tag: str) -> Optional[str]:
        """Získá Discord mention propojeného uživatele"""
        from database import get_all_links
        links = get_all_links()
        for discord_id, (tag, _) in links.items():
            if tag == coc_tag:
                member = self.bot.get_guild(self.config['DISCORD_GUILD_ID']).get_member(discord_id)
                if member:
                    print(f"[clan_war] Nalezen propojený uživatel: {member.display_name} ({member.id})")
                    return member.mention
        return None

    def _parse_coc_time(self, time_str: str) -> Optional[datetime]:
        """Parsuje čas z API CoC"""
        try:
            return datetime.strptime(time_str, "%Y%m%dT%H%M%S.000Z")
        except (ValueError, AttributeError):
            return None