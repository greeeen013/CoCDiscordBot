import discord
from discord.utils import escape_markdown
from datetime import datetime, timezone
from typing import Optional
import json
import os

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

# === Sdílené ID úložiště ===
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


class ClanWarHandler:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.war_status_channel_id = 1366835944174391379
        self.war_events_channel_id = 1366835971395686554
        self.war_ping_channel_id = 1371089891621998652
        self.last_processed_order = load_room_id("last_war_event_order") or 0
        self.current_war_message_id = load_room_id("war_status_message")
        self._last_state = None

    async def remind_missing_attacks(self, war_data: dict):
        """
        Odešle upozornění do vybraného kanálu, pokud zbývá 7h, 3h nebo 1h do konce války
        a někteří hráči ještě neodehráli ani jeden útok. Každé upozornění se odešle jen jednou.
        """
        end_time = self._parse_coc_time(war_data.get('endTime', ''))
        if not end_time:
            return

        now = datetime.now(timezone.utc)
        remaining_hours = (end_time - now).total_seconds() / 3600
        hour_marks = [7, 3, 1]

        for mark in hour_marks:
            key = f"war_reminder_{mark}h"
            already_sent = load_room_id(key)

            if remaining_hours <= mark and not already_sent:
                missing = [m for m in war_data.get('clan', {}).get('members', []) if not m.get('attacks')]
                if not missing:
                    save_room_id(key, True)
                    continue

                ping_channel = self.bot.get_channel(self.war_ping_channel_id)
                mention = "<@317724566426222592>"

                mentions = []
                for m in missing:
                    tag = m.get("tag")
                    name = m.get("name", "Unknown").replace('_', r'\_').replace('*', r'\*')
                    discord_mention = await self._get_discord_mention(tag)
                    if discord_mention:
                        mentions.append(discord_mention)
                    else:
                        mentions.append(f"@{name}")

                # Zpráva podle urgency
                if mark == 1:
                    await ping_channel.send(f"{mention} ⚠️ **POSLEDNÍ VAROVÁNÍ – méně než 1 hodina do konce!**")
                else:
                    await ping_channel.send(f"{mention} Připomínka: zbývá méně než {mark}h do konce války")

                for i in range(0, len(mentions), 5):
                    await ping_channel.send(" ".join(mentions[i:i + 5]))

                save_room_id(key, True)

    async def process_war_data(self, war_data: dict):
        """Zpracuje data o válce a aktualizuje Discord"""
        if not war_data:
            print("❌ [clan_war] Žádná data o válce ke zpracování")
            return

        state = war_data.get('state', 'unknown')

        # Pokud se stav změnil na warEnded, smaž obsah kanálů
        if state == 'warEnded' and self._last_state != 'warEnded':
            # pokud chceme smazat mistnost tak odkomentujeme funkci
            #await self._clear_war_channels()
            self.current_war_message_id = None
            save_room_id("war_status_message", None)

        # Aktualizuj uložený stav až po kontrole
        self._last_state = state

        # Pokud není ve válce nebo přípravě, nedělej nic dalšího
        if state not in ('inWar', 'preparation'):
            return

        try:
            # Připomenutí hráčům bez útoku
            await self.remind_missing_attacks(war_data)

            # Aktualizace stavu války
            await self.update_war_status(war_data)

            # Zpracování událostí (útoků)
            if war_data.get('state') in ('inWar', 'preparation'):
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
                    print("⚠️ [clan_war] Původní zpráva nenalezena, posílám novou.")
                    self.current_war_message_id = None
            if not self.current_war_message_id:
                message = await channel.send(embed=embed)
                self.current_war_message_id = message.id
                save_room_id("war_status_message", message.id)

        except Exception as e:
            print(f"❌ [clan_war] Chyba při aktualizaci stavu války: {str(e)}")

    def _create_war_status_embed(self, war_data: dict) -> discord.Embed:
        """Vytvoří embed se stavem války s dynamickým rozdělením hráčů na víc fieldů podle limitu 1024 znaků."""
        clan = war_data.get('clan', {})
        opponent = war_data.get('opponent', {})
        state = war_data.get('state', 'unknown').capitalize()

        embed = discord.Embed(
            title=f"Clan War: {clan.get('name', 'Náš klan')} vs {opponent.get('name', 'Protivník')}",
            color=discord.Color.blue() if state == "Inwar" else discord.Color.gold()
        )

        # Základní statistiky
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
        embed.add_field(name="\u200b", value="⁣  **VS**", inline=True)
        embed.add_field(name=f"**{opponent.get('name', 'Protivník')}**", value=their_stats, inline=True)

        # Časy
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
                    value=f"<t:{int(time.timestamp())}:f>\n<t:{int(time.timestamp())}:R>",
                    inline=True
                )

        # Hráči – dynamické dělení na více fieldů
        if war_data.get('state') in ('inWar', 'preparation'):
            def format_members(members):
                formatted = []
                for idx, m in enumerate(sorted(members, key=lambda x: x.get('mapPosition', 0)), start=1):
                    formatted.append(
                        "{index}. {emoji} {name} ({attacks}/{max_attacks})".format(
                            index=idx,
                            emoji=TOWN_HALL_EMOJIS.get(m.get('townhallLevel', 10), ''),
                            name=m.get('name', 'Unknown').replace('_', r'\_').replace('*', r'\*'),
                            attacks=len(m.get('attacks', [])),
                            max_attacks=war_data.get('attacksPerMember', 2)
                        )
                    )
                return formatted

            def split_to_chunks_pairwise(left_lines, right_lines):
                chunks = []
                current_left, current_right = [], []
                length_left = length_right = 0
                for l_line, r_line in zip(left_lines, right_lines):
                    l_len = len(l_line) + 1
                    r_len = len(r_line) + 1
                    if (length_left + l_len > 1024) or (length_right + r_len > 1024):
                        chunks.append(("\n".join(current_left), "\n".join(current_right)))
                        current_left, current_right = [l_line], [r_line]
                        length_left, length_right = l_len, r_len
                    else:
                        current_left.append(l_line)
                        current_right.append(r_line)
                        length_left += l_len
                        length_right += r_len
                if current_left or current_right:
                    chunks.append(("\n".join(current_left), "\n".join(current_right)))
                return chunks

            our_raw = format_members(clan.get('members', []))
            their_raw = format_members(opponent.get('members', []))

            # Zarovnej délky seznamů (pokud jeden z nich je delší)
            max_len = max(len(our_raw), len(their_raw))
            while len(our_raw) < max_len:
                our_raw.append("—")
            while len(their_raw) < max_len:
                their_raw.append("—")

            chunks = split_to_chunks_pairwise(our_raw, their_raw)

            for i, (our_value, their_value) in enumerate(chunks):
                if i == 0:
                    embed.add_field(name="**Naši hráči**", value=our_value, inline=True)
                    embed.add_field(name=" ", value=" ", inline=True)
                    embed.add_field(name="**Jejich hráči**", value=their_value, inline=True)
                else:
                    embed.add_field(name=" ", value=" ", inline=False)
                    embed.add_field(name=f"**Naši hráči**", value=our_value, inline=True)
                    embed.add_field(name=" ", value=" ", inline=True)
                    embed.add_field(name=f"**Jejich hráči**", value=their_value, inline=True)

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
            save_room_id("last_war_event_order", self.last_processed_order)

    async def _send_attack_embed(self, channel, attack: dict, war_data: dict):
        """Vytvoří embed pro jeden útok"""
        attacker = self._find_member_by_tag(attack.get('attackerTag'), war_data)
        defender = self._find_member_by_tag(attack.get('defenderTag'), war_data)

        if not attacker or not defender:
            return

        is_our_attack = any(m.get('tag') == attacker.get('tag') for m in war_data.get('clan', {}).get('members', []))
        discord_mention = await self._get_discord_mention(attack.get('attackerTag'))

        # Debug ping
        if discord_mention:
            print(f"✅ [clan_war] Nalezen Discord uživatel pro tag {attack.get('attackerTag')}: {discord_mention}")

        # Barva podle typu akce
        embed_color = discord.Color.red() if is_our_attack else discord.Color.blue()
        embed = discord.Embed(color=embed_color)

        # Escape jména hráčů
        attacker_name = attacker.get('name', 'Unknown').replace('_', r'\_').replace('*', r'\*')
        defender_name = defender.get('name', 'Unknown').replace('_', r'\_').replace('*', r'\*')

        # Escape jména klanů
        clan_name = war_data.get('clan', {}).get('name', 'Náš klan').replace('_', r'\_').replace('*', r'\*')
        opponent_name = war_data.get('opponent', {}).get('name', 'Protivník').replace('_', r'\_').replace('*', r'\*')

        # Levá strana = náš klan, Pravá strana = protivník (vždy stejně)
        left_pos = attacker.get("mapPosition") if is_our_attack else defender.get("mapPosition")
        right_pos = defender.get("mapPosition") if is_our_attack else attacker.get("mapPosition")

        left_name = attacker_name if is_our_attack else defender_name
        right_name = defender_name if is_our_attack else attacker_name

        left_th = attacker.get('townhallLevel', 10) if is_our_attack else defender.get('townhallLevel', 10)
        right_th = defender.get('townhallLevel', 10) if is_our_attack else attacker.get('townhallLevel', 10)

        left_side = (
            f"**{clan_name}**\n"
            f"#{(left_pos or 0) + 1} | {TOWN_HALL_EMOJIS.get(left_th, '')} {left_name}"
        )
        if discord_mention and is_our_attack:
            left_side += f"\n{discord_mention}"

        right_side = (
            f"**{opponent_name}**\n"
            f"#{(right_pos or 0) + 1} | {TOWN_HALL_EMOJIS.get(right_th, '')} {right_name}"
        )

        action = "**ÚTOK** ⚔️" if is_our_attack else "**OBRANA** 🛡️"
        arrow = "➡️" if is_our_attack else "⬅️"

        middle_field = (
            f"{action}\n"
            f"{arrow}   {'⭐' * attack.get('stars', 0)}\n"
            f"   {attack.get('destructionPercentage', 0)}%"
        )

        embed.add_field(name="\u200b", value=left_side, inline=True)
        embed.add_field(name="\u200b", value=middle_field, inline=True)
        embed.add_field(name="\u200b", value=right_side, inline=True)

        # Výpočet času do konce války
        end_time = self._parse_coc_time(war_data.get('endTime', ''))
        remaining_hours = None
        if end_time:
            from datetime import datetime
            now = datetime.now(timezone.utc)
            delta = end_time - now
            remaining_hours = max(delta.total_seconds() / 3600, 0)

        footer_parts = [
            f"Útok #{attack.get('order', 0)}",
            f"Útok trval: {attack.get('duration', 0)}s"
        ]
        if remaining_hours is not None:
            footer_parts.append(f"Do konce war: {remaining_hours:.1f}h")

        embed.set_footer(text=" | ".join(footer_parts))
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
                member = self.bot.get_guild(self.config['GUILD_ID']).get_member(discord_id)
                if member:
                    print(f"[clan_war] Nalezen propojený uživatel: {member.display_name} ({member.id})")
                    return member.mention
        return None

    def _parse_coc_time(self, time_str: str) -> Optional[datetime]:
        """Parsuje čas z API CoC a vrací offset-aware UTC datetime"""
        try:
            return datetime.strptime(time_str, "%Y%m%dT%H%M%S.000Z").replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            return None
