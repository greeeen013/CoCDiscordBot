import discord
from discord.utils import escape_markdown
from datetime import datetime, timezone
from typing import Optional
import json
import os

from database import notify_single_warning, get_all_links
from constants import TOWN_HALL_EMOJIS

STATE_MAP = {
    "inWar": "Probíhá",
    "preparation": "Příprava",
    "warEnded": "Ukončeno",
    "notInWar": "Žádná válka"
}

# === Sdílené ID úložiště ===
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOM_IDS_PATH = os.path.join(THIS_DIR, "discord_rooms_ids.json")


class RoomIdStorage:
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        try:
            if os.path.exists(ROOM_IDS_PATH):
                with open(ROOM_IDS_PATH, "r") as f:
                    self.data = json.load(f)
        except Exception as e:
            print(f"[clan_war] [discord_rooms_ids] Chyba při čtení: {e}")
            self.data = {}

    def save(self):
        try:
            with open(ROOM_IDS_PATH, "w") as f:
                json.dump(self.data, f)
        except Exception as e:
            print(f"[clan_war] [discord_rooms_ids] Chyba při zápisu: {e}")

    def get(self, key: str):
        return self.data.get(key)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()

    def remove(self, key: str):
        if key in self.data:
            del self.data[key]
            self.save()

    def reset_war_reminder_flags(self):
        """Smaže všechny klíče začínající na 'war_reminder_'"""
        keys_to_remove = [key for key in self.data if key.startswith("war_reminder_")]
        for key in keys_to_remove:
            del self.data[key]
        if keys_to_remove:
            self.save()
            print(f"♻️ [clan_war] Resetováno {len(keys_to_remove)} war reminder flagů.")


room_storage = RoomIdStorage()


class ClanWarHandler:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.war_status_channel_id = 1366835944174391379
        self.war_events_channel_id = 1366835971395686554
        self.war_ping_channel_id = 1371089891621998652
        self.last_processed_order = room_storage.get("last_war_event_order") or 0
        self.current_war_message_id = room_storage.get("war_status_message")
        self._last_state = None

        # Cache
        self._mention_cache = {}
        self._time_cache = {}
        self._escaped_names = {}

    def _escape_name(self, name: str) -> str:
        """Vrací escapované jméno s cache"""
        if not name:
            return ""

        if name not in self._escaped_names:
            self._escaped_names[name] = escape_markdown(name.replace('_', r'\_'))
        return self._escaped_names[name]

    async def remind_missing_attacks(self, war_data: dict, send_warning: bool = True) -> Optional[str]:
        """
        Odešle upozornění do vybraného kanálu, pokud zbývá 6h, 2h nebo 1h do konce války
        a někteří hráči ještě neodehráli ani jeden útok. Každé upozornění se odešle jen jednou.
        """
        end_time = self._parse_coc_time(war_data.get('endTime', ''))
        if not end_time:
            return None

        now = datetime.now(timezone.utc)
        remaining_seconds = (end_time - now).total_seconds()
        remaining_hours = remaining_seconds / 3600
        hour_marks = [6, 2, 1]

        # Seznam členů klanu, kteří zatím neútočili
        missing_members = [m for m in war_data.get('clan', {}).get('members', []) if not m.get('attacks')]

        # Formátování zbývajícího času
        def format_remaining_time(seconds: float) -> str:
            if seconds < 0:
                seconds = 0
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)

            parts = []
            if hours > 0:
                parts.append(f"{hours} hodin" if hours > 4 else f"{hours} hodiny" if hours > 1 else "1 hodina")
            if minutes > 0 or not parts:
                parts.append(f"{minutes} minut" if minutes > 4 else f"{minutes} minuty" if minutes > 1 else "1 minuta")

            return " ".join(parts)

        # Pokud je povoleno zasílat varování
        if send_warning:
            for mark in hour_marks:
                key = f"war_reminder_{mark}h"
                already_sent = room_storage.get(key)
                if remaining_hours <= mark and not already_sent:
                    if not missing_members:
                        room_storage.set(key, True)
                        continue

                    ping_channel = self.bot.get_channel(self.war_ping_channel_id)
                    mention = "<@317724566426222592>"

                    # Připravit seznam zmínek hráčů
                    mentions_list = []
                    for m in missing_members:
                        tag = m.get("tag")
                        name = self._escape_name(m.get("name", "Unknown"))
                        discord_mention = await self._get_discord_mention(tag)
                        mentions_list.append(discord_mention or f"@{name}")

                    # Text upozornění
                    time_str = format_remaining_time(remaining_seconds)
                    if mark == 1:
                        await ping_channel.send(f"{mention} ⚠️ **POSLEDNÍ VAROVÁNÍ – zbývá {time_str} do konce!**")
                    else:
                        await ping_channel.send(f"{mention} Připomínka: zbývá {time_str} do konce války")

                    # Odeslat zmínky po skupinách
                    for i in range(0, len(mentions_list), 5):
                        await ping_channel.send(" ".join(mentions_list[i:i + 5]) + " ")

                    # Soukromé připomínky hráčům přes DM
                    all_links = get_all_links()
                    dm_targets = {
                        m.get("tag"): m.get("name", "Unknown")
                        for m in missing_members
                        if m.get("tag") in {tag.upper() for _, (tag, _) in all_links.items()}
                    }

                    for discord_id, (linked_tag, _) in all_links.items():
                        if linked_tag.upper() in dm_targets:
                            try:
                                user = await self.bot.fetch_user(discord_id)
                                if user:
                                    await user.send(
                                        f"⚔️ Připomínka: zbývá {time_str} do konce clan war!\n"
                                        f"Ještě jsi **neodehrál** žádný útok za svůj účet: `{linked_tag}`.\n"
                                        f"Nezapomeň prosím odehrát, ať neztrácíme hvězdy 🙏"
                                    )
                            except Exception as dm_error:
                                print(f"⚠️ [remind] Nepodařilo se odeslat DM hráči s tagem {linked_tag}: {dm_error}")

                    room_storage.set(key, True)

        # Sestavení výstupní zprávy
        time_remaining_str = format_remaining_time(remaining_seconds)
        if not missing_members:
            return f"Do konce války zbývá {time_remaining_str}. ✅ Všichni členové klanu již provedli své útoky."
        else:
            mentions_output = []
            for m in missing_members:
                tag = m.get("tag")
                name = self._escape_name(m.get("name", "Unknown"))
                discord_mention = await self._get_discord_mention(tag)
                mentions_output.append(discord_mention or f"@{name}")
            return f"Do konce války zbývá {time_remaining_str}. Útok dosud neprovedli: " + " ".join(
                mentions_output) + " "

    async def process_war_data(self, war_data: dict):
        """Zpracuje data o válce a aktualizuje Discord"""
        if not war_data:
            print("❌ [clan_war] Žádná data o válce ke zpracování")
            return

        state = war_data.get('state', 'unknown')

        # Reset při změně stavu
        if self._last_state is not None and state == "warEnded" and self._last_state != "warEnded":
            await self.update_war_status(war_data)
            self.current_war_message_id = None
            room_storage.set("war_status_message", None)

            # Oznámení o neodehraných útocích
            war_end_channel = self.bot.get_channel(self.war_ping_channel_id)
            missing = [m for m in war_data.get('clan', {}).get('members', []) if not m.get('attacks')]
            if war_end_channel and missing:
                await war_end_channel.send("🚨 Následující hráči **neodehráli** útoky ve válce: 🚨")
                mentions = []

                for m in missing:
                    tag = m.get("tag")
                    name = self._escape_name(m.get("name", "Unknown"))
                    discord_mention = await self._get_discord_mention(tag)
                    mentions.append(discord_mention or f"@{name}")

                    # Přidání varování
                    await notify_single_warning(
                        bot=self.bot,
                        coc_tag=tag,
                        date_time=datetime.now().strftime("%d/%m/%Y %H:%M"),
                        reason="neodehraná clan war válka"
                    )

                for i in range(0, len(mentions), 5):
                    await war_end_channel.send(" ".join(mentions[i:i + 5]))

        # Reset událostí při nové válce
        if self._last_state is not None and self._last_state != 'preparation' and state == 'preparation':
            print("🔁 [clan_war] Detekována nová válka – resetuji pořadí útoků.")
            self.last_processed_order = 0
            room_storage.set("last_war_event_order", 0)
            room_storage.reset_war_reminder_flags()

        self._last_state = state

        # Pokud není ve válce nebo přípravě, nedělej nic dalšího
        if state not in ('inWar', 'preparation'):
            return

        try:
            await self.remind_missing_attacks(war_data)
            await self.update_war_status(war_data)

            if war_data.get('state') in ('inWar', 'preparation'):
                await self.process_war_events(war_data)

        except Exception as e:
            print(f"❌ [clan_war] Chyba při zpracování dat: {str(e)}")

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
                room_storage.set("war_status_message", message.id)

        except Exception as e:
            print(f"❌ [clan_war] Chyba při aktualizaci stavu války: {str(e)}")

    def _create_war_status_embed(self, war_data: dict) -> discord.Embed:
        """Vytvoří embed se stavem války s dynamickým rozdělením hráčů"""
        clan = war_data.get('clan', {})
        opponent = war_data.get('opponent', {})
        state = war_data.get('state', 'unknown')

        embed = discord.Embed(
            title=f"Clan War: {self._escape_name(clan.get('name', 'Náš klan'))} vs {self._escape_name(opponent.get('name', 'Protivník'))}",
            color=discord.Color.blue() if state == "inWar" else discord.Color.gold()
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

        embed.add_field(name=f"**{self._escape_name(clan.get('name', 'Náš klan'))}**", value=our_stats, inline=True)
        embed.add_field(name="\u200b", value="⁣  **VS**", inline=True)
        embed.add_field(name=f"**{self._escape_name(opponent.get('name', 'Protivník'))}**", value=their_stats,
                        inline=True)

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

        # Hráči – dynamické dělení na více fieldů podle limitu 1024 znaků
        if war_data.get('state') in ('inWar', 'preparation', 'warEnded'):
            def format_members(members):
                formatted = []
                for idx, m in enumerate(sorted(members, key=lambda x: x.get('mapPosition', 0)), start=1):
                    formatted.append(
                        "{index}. {emoji} {name} ({attacks}/{max_attacks})".format(
                            index=idx,
                            emoji=TOWN_HALL_EMOJIS.get(m.get('townhallLevel', 10), ''),
                            name=self._escape_name(m.get('name', 'Unknown')),
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
                    l_len = len(l_line) + 1  # +1 za nový řádek
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

            # Zarovnej délky seznamů
            max_len = max(len(our_raw), len(their_raw))
            our_raw += ["—"] * (max_len - len(our_raw))
            their_raw += ["—"] * (max_len - len(their_raw))

            chunks = split_to_chunks_pairwise(our_raw, their_raw)

            for i, (our_value, their_value) in enumerate(chunks):
                if i == 0:
                    embed.add_field(name="**Naši hráči**", value=our_value, inline=True)
                    embed.add_field(name=" ", value=" ", inline=True)
                    embed.add_field(name="**Jejich hráči**", value=their_value, inline=True)
                else:
                    embed.add_field(name=" ", value=" ", inline=False)
                    embed.add_field(name="**Naši hráči**", value=our_value, inline=True)
                    embed.add_field(name=" ", value=" ", inline=True)
                    embed.add_field(name="**Jejich hráči**", value=their_value, inline=True)

        friendly_state = STATE_MAP.get(state, state)
        embed.set_footer(text=f"Stav války: {friendly_state}")
        return embed

    async def process_war_events(self, war_data: dict):
        """Zpracuje nové události ve válce (útoky)"""
        channel = self.bot.get_channel(self.war_events_channel_id)
        if not channel:
            print("❌ [clan_war] Kanál pro události války nebyl nalezen")
            return

        # Získání všech útoků
        attacks = []
        for side in ('clan', 'opponent'):
            for member in war_data.get(side, {}).get('members', []):
                attacks.extend(member.get('attacks', []))

        # Filtrace a řazení nových útoků
        new_attacks = sorted(
            (a for a in attacks if a.get('order', 0) > self.last_processed_order),
            key=lambda x: x.get('order', 0)
        )

        if not new_attacks:
            return

        # Zpracování útoků
        for attack in new_attacks:
            await self._send_attack_embed(channel, attack, war_data)

        # Uložení posledního orderu
        self.last_processed_order = max(a.get('order', 0) for a in new_attacks)
        room_storage.set("last_war_event_order", self.last_processed_order)

    async def _send_attack_embed(self, channel, attack: dict, war_data: dict):
        """Vytvoří embed pro jeden útok"""
        attacker = self._find_member_by_tag(attack.get('attackerTag'), war_data)
        defender = self._find_member_by_tag(attack.get('defenderTag'), war_data)

        if not attacker or not defender:
            return

        is_our_attack = any(m.get('tag') == attacker.get('tag') for m in war_data.get('clan', {}).get('members', []))
        discord_mention = await self._get_discord_mention(attack.get('attackerTag'))

        # Barva podle typu akce
        embed_color = discord.Color.red() if is_our_attack else discord.Color.blue()
        embed = discord.Embed(color=embed_color)

        # Escape jména
        attacker_name = self._escape_name(attacker.get('name', 'Unknown'))
        defender_name = self._escape_name(defender.get('name', 'Unknown'))
        clan_name = self._escape_name(war_data.get('clan', {}).get('name', 'Náš klan'))
        opponent_name = self._escape_name(war_data.get('opponent', {}).get('name', 'Protivník'))

        # Určení pozic
        left_pos = attacker.get("mapPosition") if is_our_attack else defender.get("mapPosition")
        right_pos = defender.get("mapPosition") if is_our_attack else attacker.get("mapPosition")

        left_name = attacker_name if is_our_attack else defender_name
        right_name = defender_name if is_our_attack else attacker_name

        left_th = attacker.get('townhallLevel', 10) if is_our_attack else defender.get('townhallLevel', 10)
        right_th = defender.get('townhallLevel', 10) if is_our_attack else attacker.get('townhallLevel', 10)

        # Kontrola oprav
        defender_position = defender.get("mapPosition")
        all_attacks = []
        for side in ('clan', 'opponent'):
            for member in war_data.get(side, {}).get('members', []):
                all_attacks.extend(member.get('attacks', []))

        duplicate_attacks = [a for a in all_attacks if
                             a.get('defenderTag') == defender.get('tag') and a.get('order', 0) < attack.get('order', 0)]
        is_oprava = len(duplicate_attacks) > 0

        # Sestavení embedu
        left_side = (
            f"**{clan_name}**\n"
            f"#{(left_pos or 1)} | {TOWN_HALL_EMOJIS.get(left_th, '')} {left_name}"
        )
        if discord_mention and is_our_attack:
            left_side += f"\n{discord_mention}"

        right_side = (
            f"**{opponent_name}**\n"
            f"#{(right_pos or 1)} | {TOWN_HALL_EMOJIS.get(right_th, '')} {right_name}"
        )
        if is_our_attack and is_oprava:
            right_side += f"\n`oprava`"

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

        # Čas do konce války
        end_time = self._parse_coc_time(war_data.get('endTime', ''))
        remaining_hours = None
        if end_time:
            now = datetime.now(timezone.utc)
            delta = end_time - now
            remaining_hours = max(delta.total_seconds() / 3600, 0)

            # Pochvala za mirror
            if (is_our_attack and
                    attacker.get("mapPosition") == defender.get("mapPosition") and
                    attack.get("destructionPercentage", 0) == 100 and
                    remaining_hours >= 5):
                praise_channel = self.bot.get_channel(1371170358056452176)
                discord_mention = await self._get_discord_mention(attacker.get("tag"))
                name_or_mention = discord_mention or f"@{attacker.get('name', 'neznámý')}"
                if praise_channel:
                    await praise_channel.send(f"{name_or_mention}\nPochvala za krásný útok na mirror včas!")

            # Varování za non-mirror
            if is_our_attack and not is_oprava and attacker.get("mapPosition") != defender.get("mapPosition"):
                if remaining_hours >= 5:
                    await notify_single_warning(
                        bot=self.bot,
                        coc_tag=attacker.get("tag"),
                        date_time=datetime.now().strftime("%d/%m/%Y %H:%M"),
                        reason="clan wars útok který nebyl mirror"
                    )

        # Footer
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
        for side in ('clan', 'opponent'):
            for member in war_data.get(side, {}).get('members', []):
                if member.get('tag') == tag:
                    return member
        return None

    async def _get_discord_mention(self, coc_tag: str) -> Optional[str]:
        """Získá Discord mention propojeného uživatele (s cache)"""
        if not coc_tag:
            return None

        if not hasattr(self, '_mention_cache'):
            self._mention_cache = {}
            links = get_all_links()
            guild = self.bot.get_guild(self.config['GUILD_ID'])
            for discord_id, (tag, _) in links.items():
                member = guild.get_member(discord_id)
                if member:
                    self._mention_cache[tag.upper()] = member.mention

        return self._mention_cache.get(coc_tag.upper())

    def _parse_coc_time(self, time_str: str) -> Optional[datetime]:
        """Parsuje čas z API CoC (s cache)"""
        if not time_str:
            return None

        if time_str not in self._time_cache:
            try:
                self._time_cache[time_str] = datetime.strptime(time_str, "%Y%m%dT%H%M%S.000Z").replace(
                    tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                self._time_cache[time_str] = None

        return self._time_cache[time_str]