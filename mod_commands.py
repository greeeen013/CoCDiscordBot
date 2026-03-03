import asyncio
import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.utils import get
from datetime import datetime, timedelta, timezone
from typing import Optional

import api_handler
from api_handler import fetch_current_war
from bot_commands import VerifikacniView
from clan_war import ClanWarHandler
from constants import HEROES_EMOJIS, TOWN_HALL_EMOJIS, max_heroes_lvls
from database import remove_warning, fetch_warnings, notify_single_warning, get_all_links, remove_coc_link, \
    add_coc_link, get_all_members
from role_giver import update_roles

from constants import (
    HEROES_EMOJIS, 
    TOWN_HALL_EMOJIS, 
    max_heroes_lvls, 
    ROLE_VERIFIED, 
    ROLE_ELDER, 
    ROLE_CO_LEADER, 
    ROLE_LEADER,
    TH_TO_PET_HOUSE, 
    PET_MAX_LEVELS, 
    EQUIPMENT_DATA, 
    TH_TO_BLACKSMITH, 
    TH_TO_LAB, 
    TROOP_UPGRADES, 
    SIEGE_MACHINE_UPGRADES, 
    SPELL_UPGRADES,
    RULES_CHANNEL_ID,
    VERIFICATION_CHANNEL_ID,
    WAR_INFO_CHANNEL_ID,
    WAR_EVENTS_CHANNEL_ID,
    CAPITAL_STATUS_CHANNEL_ID,
    CLASH_OF_CLANS_EVENT_CHANNEL_ID,
    GENERAL_CHANNEL_ID,
    BOT_USER_ID
)


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

room_storage = RoomIdStorage()
async def setup_mod_commands(bot):

    # === Role/permission helpers ===
    def _is_admin(member: discord.Member) -> bool:
        return bool(getattr(member.guild_permissions, "administrator", False))

    def _has_role(member: discord.Member, role_id: int) -> bool:
        try:
            return any(r.id == role_id for r in getattr(member, "roles", []))
        except Exception:
            return False

    def _is_leader(member: discord.Member) -> bool:
        return _has_role(member, ROLE_LEADER)

    def _is_co_leader(member: discord.Member) -> bool:
        return _has_role(member, ROLE_CO_LEADER) or _is_leader(member)

    def _is_elder(member: discord.Member) -> bool:
        return _has_role(member, ROLE_ELDER)

    def _is_verified(member: discord.Member) -> bool:
        # Elder/Co-Leader jsou implicitně “ověření”
        return _has_role(member, ROLE_VERIFIED) or _is_elder(member) or _is_co_leader(member)

    # Pomocná funkce pro automatické mazání ephemerálních zpráv
    async def auto_delete_ephemeral(message: discord.Message | discord.Interaction, delay: int = 180):
        """Automatically delete ephemeral message after specified delay"""
        try:
            await asyncio.sleep(delay)
            if isinstance(message, discord.Interaction):
                if message.response.is_done():
                    await message.delete_original_response()
            else:
                await message.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

    async def send_ephemeral(interaction: discord.Interaction, content: str, delete_after: int = 180, **kwargs):
        """Helper function to send ephemeral messages with auto-delete"""
        if interaction.response.is_done():
            msg = await interaction.followup.send(content, ephemeral=True, **kwargs)
        else:
            msg = await interaction.response.send_message(content, ephemeral=True, **kwargs)

        if delete_after and delete_after > 0:
            asyncio.create_task(auto_delete_ephemeral(msg, delete_after))
        return msg

    @bot.tree.command(name="clear", description="Vyčistí kanál nebo zadaný počet zpráv", guild=bot.guild_object)
    @app_commands.describe(pocet="Kolik zpráv smazat (nebo prázdné = kompletní vymazání)")
    async def clear(interaction: discord.Interaction, pocet: int = 0):
        if not interaction.user.guild_permissions.manage_messages:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            total_deleted = 0
            if pocet > 0:
                deleted = await interaction.channel.purge(limit=pocet)
                total_deleted = len(deleted)
            else:
                while True:
                    deleted = await interaction.channel.purge(limit=100)
                    total_deleted += len(deleted)
                    if len(deleted) < 100:
                        break

            await send_ephemeral(interaction, f"✅ Vymazáno {total_deleted} zpráv v kanálu.")
        except discord.Forbidden:
            await send_ephemeral(interaction, "❌ Nemám právo mazat zprávy v tomto kanálu.")
        except Exception as e:
            await send_ephemeral(interaction, f"❌ Došlo k chybě při mazání zpráv: {e}")

    @bot.tree.command(name="lock", description="Uzamkne kanál pro psaní", guild=bot.guild_object)
    @app_commands.describe(duvod="Důvod pro uzamčení kanálu")
    async def lock(interaction: discord.Interaction, duvod: str = None):
        if not interaction.user.guild_permissions.manage_channels:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔒 Kanál uzamčen",
            description=f"Moderátor {interaction.user.mention} uzamkl tento kanál." + (
                f"\n**Důvod:** {duvod}" if duvod else ""),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="unlock", description="Odemkne kanál pro psaní", guild=bot.guild_object)
    async def unlock(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔓 Kanál odemknut",
            description=f"Moderátor {interaction.user.mention} odemkl tento kanál.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="timeout", description="Umlčí uživatele na určitou dobu", guild=bot.guild_object)
    @app_commands.describe(
        uzivatel="Uživatel, kterého chceš umlčet",
        minuty="Doba umlčení v minutách",
        duvod="Důvod pro umlčení"
    )
    async def timeout(interaction: discord.Interaction, uzivatel: discord.Member, minuty: int, duvod: str = None):
        if not interaction.user.guild_permissions.moderate_members:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        duration = timedelta(minutes=minuty)
        await uzivatel.timeout(duration, reason=duvod)

        embed = discord.Embed(
            title="⏳ Uživatel umlčen",
            description=f"{uzivatel.mention} byl umlčen na {minuty} minut." + (
                f"\n**Důvod:** {duvod}" if duvod else ""),
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="untimeout", description="Zruší umlčení uživatele", guild=bot.guild_object)
    @app_commands.describe(uzivatel="Uživatel, kterému chceš zrušit umlčení")
    async def untimeout(interaction: discord.Interaction, uzivatel: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        await uzivatel.timeout(None)

        embed = discord.Embed(
            title="🔊 Umlčení zrušeno",
            description=f"{uzivatel.mention} může znovu psát.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="kick", description="Vyhodí uživatele ze serveru", guild=bot.guild_object)
    @app_commands.describe(
        uzivatel="Uživatel, kterého chceš vyhodit",
        duvod="Důvod pro vyhození"
    )
    async def kick(interaction: discord.Interaction, uzivatel: discord.Member, duvod: str = None):
        if not interaction.user.guild_permissions.kick_members:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        await uzivatel.kick(reason=duvod)

        embed = discord.Embed(
            title="👢 Uživatel vyhozen",
            description=f"{uzivatel.display_name} byl vyhozen ze serveru." + (f"\n**Důvod:** {duvod}" if duvod else ""),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="slowmode", description="Nastaví slowmode v kanálu", guild=bot.guild_object)
    @app_commands.describe(
        sekundy="Počet sekund mezi zprávami (0 pro vypnutí)"
    )
    async def slowmode(interaction: discord.Interaction, sekundy: int):
        if not interaction.user.guild_permissions.manage_channels:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        if sekundy < 0 or sekundy > 21600:
            await send_ephemeral(interaction, "❌ Slowmode musí být mezi 0 a 21600 sekundami (6 hodin).")
            return

        await interaction.channel.edit(slowmode_delay=sekundy)

        if sekundy == 0:
            await interaction.response.send_message("✅ Slowmode vypnut.")
        else:
            await interaction.response.send_message(f"✅ Slowmode nastaven na {sekundy} sekund.")

    @bot.tree.command(
        name="pridej_varovani",
        description="Navrhne varování pro hráče podle CoC tagu nebo označeného uživatele",
        guild=bot.guild_object
    )
    @app_commands.describe(
        uzivatel="Discord uživatel (alternativa k zadání tagu)",
        coc_tag="Clash of Clans tag hráče (alternativa k označení uživatele)",
        date_time="Datum a čas (DD/MM/YYYY HH:MM)",
        reason="Důvod varování"
    )
    async def pridej_varovani(
            interaction: discord.Interaction,
            uzivatel: discord.Member | None = None,
            coc_tag: str | None = None,
            reason: str = "Bez udaného důvodu",
            date_time: str | None = None
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)

        # ✅ Povolení: pouze Co-Leader nebo Administrátor
        if not (_is_admin(interaction.user) or _is_co_leader(interaction.user)):
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze **Co-Leader** nebo **Administrátor**.")
            return

        # 1) Validace: nesmí být současně uzivatel i coc_tag
        if uzivatel and coc_tag:
            await send_ephemeral(interaction, "❌ Použij **jen jeden** identifikátor: buď `uzivatel`, nebo `coc_tag`.")
            return

        # 2) Zjisti CoC tag
        resolved_tag = None
        if uzivatel:
            # dohledání tagu podle označeného uživatele
            links = get_all_links()  # {discord_id: (coc_tag, coc_name)} :contentReference[oaicite:2]{index=2}
            entry = links.get(int(uzivatel.id))
            if not entry or not entry[0]:
                await send_ephemeral(interaction, f"❌ Uživatel {uzivatel.mention} nemá propojený CoC účet.")
                return
            resolved_tag = entry[0]
        elif coc_tag:
            # normalizace zadaného tagu
            resolved_tag = coc_tag.strip().upper()
        else:
            # nebyl zadán ani uzivatel ani tag → zkusíme volajícího
            links = get_all_links()  # :contentReference[oaicite:3]{index=3}
            entry = links.get(int(interaction.user.id))
            if not entry or not entry[0]:
                await send_ephemeral(
                    interaction,
                    "❌ Nezadán `uzivatel` ani `coc_tag` a zároveň u tebe není nalezen propojený CoC účet."
                )
                return
            resolved_tag = entry[0]

        # 3) Ujisti se, že tag má správný formát
        resolved_tag = resolved_tag.upper()
        if not resolved_tag.startswith("#"):
            resolved_tag = f"#{resolved_tag}"

        # 4) Validace času
        if date_time:
            try:
                datetime.strptime(date_time, "%d/%m/%Y %H:%M")
            except ValueError:
                await send_ephemeral(
                    interaction,
                    "❌ Neplatný formát času. Použij `DD/MM/YYYY HH:MM`, např. `14/05/2025 18:30`."
                )
                return
        else:
            date_time = datetime.now().strftime("%d/%m/%Y %H:%M")

        # 5) Odeslání návrhu (zůstává stejné) – pošle se do review kanálu s tlačítky ✅/❌:contentReference[oaicite:4]{index=4}
        try:
            await notify_single_warning(interaction.client, resolved_tag, date_time,
                                        reason)  # :contentReference[oaicite:5]{index=5}
            await send_ephemeral(interaction, f"✅ Návrh varování pro {resolved_tag} byl odeslán ke schválení.")
        except Exception as e:
            await send_ephemeral(interaction, f"❌ Chyba při vytváření varování: {e}")
            print(f"❌ [slash/pridej_varovani] {e}")

    @bot.tree.command(
        name="vypis_varovani",
        description="Vypíše varování pro konkrétního uživatele nebo všechna varování",
        guild=bot.guild_object,
    )
    @app_commands.describe(
        uzivatel="Discord uživatel (pouze administrátor)",
        coc_tag="Clash of Clans tag (pouze administrátor)"
    )
    async def list_warnings_cmd(
            interaction: discord.Interaction,
            uzivatel: Optional[discord.Member] = None,
            coc_tag: Optional[str] = None
    ):
        # ✅ Pravidla:
        # - Bez parametrů: může každý ověřený člen klanu (ROLE_VERIFIED/Elder/Co-Leader/Admin)
        # - S parametry (uzivatel nebo coc_tag): pouze Co-Leader nebo Administrátor
        # Kontrola oprávnění
        if (uzivatel is not None or coc_tag is not None):
            if not (_is_admin(interaction.user) or _is_co_leader(interaction.user)):
                await send_ephemeral(interaction,
                                     "❌ Parametry `uzivatel`/`coc_tag` může použít pouze **Co-Leader** nebo **Administrátor**.")
                return
        else:
            if not (_is_admin(interaction.user) or _is_co_leader(interaction.user) or _is_verified(interaction.user)):
                await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze **ověřený člen klanu**.")
                return

        # Validace vstupů
        if uzivatel and coc_tag:
            await send_ephemeral(interaction, "❌ Použijte pouze jeden parametr (uživatel NEBO tag)")
            return

        await interaction.response.defer(ephemeral=True)

        # Zpracování podle vstupu
        if uzivatel:
            # Hledání podle Discord uživatele
            links = get_all_links()
            coc_tag = None
            for discord_id, (tag, _) in links.items():
                if int(discord_id) == uzivatel.id:
                    coc_tag = tag
                    break

            if not coc_tag:
                await send_ephemeral(interaction, f"❌ Uživatel {uzivatel.mention} nemá propojený CoC účet")
                return

        rows = fetch_warnings()
        filtered_rows = []

        if coc_tag:
            # Filtrace podle tagu
            coc_tag = coc_tag.upper().strip()
            if not coc_tag.startswith("#"):
                coc_tag = "#" + coc_tag

            filtered_rows = [row for row in rows if row[0] == coc_tag]
        elif uzivatel:
            # Filtrace podle nalezeného tagu
            filtered_rows = [row for row in rows if row[0] == coc_tag]
        else:
            # místo všech varování použít tag volajícího
            links = get_all_links()
            user_tag = None
            for discord_id, (tag, _) in links.items():
                if int(discord_id) == interaction.user.id:
                    user_tag = tag
                    break

            if not user_tag:
                await send_ephemeral(interaction, "❌ Nemáš propojený CoC účet.")
                return

            filtered_rows = [row for row in rows if row[0] == user_tag.upper()]

        # Zobrazení výsledků
        if not filtered_rows:
            await send_ephemeral(interaction, "😊 Nenalezeno žádné varování.")
            return

        header = "🔶 **Seznam varování**\n"
        lines = []
        all_links = get_all_links()

        for i, (tag, dt, reason) in enumerate(filtered_rows, 1):
            coc_name = next((name for _, (t, name) in all_links.items() if t == tag), "Neznámý hráč")
            lines.append(f"{i}. {tag} ({coc_name}) | {dt} | {reason}")

        msg = header + "\n".join(lines)
        await send_ephemeral(interaction, msg)

    @bot.tree.command(name="odeber_varovani", description="Odstraní konkrétní varování (musí to být 1:1 napsané",
                      guild=bot.guild_object)
    @app_commands.describe(
        coc_tag="Tag hráče",
        date_time="Datum a čas varování (DD/MM/YYYY HH:MM)",
        reason="Přesný důvod varování"
    )
    async def remove_warning_cmd(interaction: discord.Interaction, coc_tag: str, date_time: str, reason: str):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return
        remove_warning(coc_tag, date_time, reason)
        await send_ephemeral(interaction, "🗑️ Varování odstraněno (pokud existovalo).")

    @bot.tree.command(
        name="kdo_neodehral",
        description="Vypíše stav války a hráče podle zbývajících útoků (s rozdělením na propojené a nepropojené).",
        guild=bot.guild_object
    )
    @app_commands.describe(
        oba_utoky="Pokud True: ukaž i hráče, kterým zbývá 1+ útok (v CW tedy i ti s 1/2)."
    )
    async def kdo_neodehral(interaction: discord.Interaction, oba_utoky: bool = False):
        # --- Povolení ---
        if not (_is_admin(interaction.user) or _is_co_leader(interaction.user) or _is_elder(interaction.user)):
            await send_ephemeral(interaction,
                                 "❌ Tento příkaz může použít pouze **Elder**, **Co-Leader** nebo **Administrátor**.")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # --- Handlery / konfig ---
        clan_war_handler = getattr(bot, "clan_war_handler", None)
        if clan_war_handler is None:
            clan_war_handler = ClanWarHandler(bot, bot.config)
            bot.clan_war_handler = clan_war_handler

        our_tag = bot.config["CLAN_TAG"].upper()

        # --- 1) Stáhni CWL i běžnou CW a vyber to, co opravdu probíhá ---
        # --- 1) Stáhni CWL i běžnou CW a vyber to, co opravdu probíhá ---
        selected_war = None
        selected_is_cwl = False

        # a) Zkusíme najít CWL válku (aktivní vyhledání)
        cwl_candidate = None
        group = await api_handler.fetch_league_group(our_tag, bot.config)
        
        if group and group.get('state') != 'notInWar':
            # Změna: Projdeme všechna kola aktivně, nespoléháme na 'current_cwl_round'
            rounds = group.get("rounds", [])
            
            # Projdeme všechna kola od posledního k prvnímu (nebo jen všechna),
            # abychom našli to 'nejlepší' (Active > Preparation > Ended).
            # Ale pozor: rounds[0] je 1. kolo, rounds[-1] je poslední.
            
            best_cwl_war = None
            best_cwl_score = -1

            # Funkce pro skóre stavu války
            def get_state_score(state):
                if state == "inWar": return 3
                if state == "preparation": return 2
                if state == "warEnded": return 1
                return 0

            # Proiterujeme všechna dostupná kola
            for r in rounds:
                war_tags = r.get("warTags", [])
                for tag in war_tags:
                    if tag == "#0": 
                        continue
                    
                    # Optimalizace: Nestahovat data, pokud už jedno inWar máme?
                    # Raději budeme přesní. Ale API calls mohou být drahé. 
                    # Nicméně /kdo_neodehral se nevolá často.
                    
                    w = await api_handler.fetch_league_war(tag, bot.config)
                    if not w:
                        continue
                    
                    c_tag = w.get('clan', {}).get('tag', '').upper()
                    o_tag = w.get('opponent', {}).get('tag', '').upper()
                    
                    if our_tag == c_tag or our_tag == o_tag:
                        s = w.get("state")
                        sc = get_state_score(s)
                        
                        # Pokud najdeme inWar, bereme ho hned a končíme hledání
                        if s == "inWar":
                            cwl_candidate = w
                            best_cwl_score = 3
                            break
                        
                        # Jinak bereme pokud je lepší než co máme (např. preparation je lepší než ended)
                        # Pokud jsou dvě shodné (např. dvě ended), bereme tu pozdější (v poli rounds)
                        # Protože iterujeme od začátku do konce, pozdější přepíše dřívější, 
                        # pokud dáme >=. Ale 'warEnded' předchozího kola vs 'preparation' dalšího?
                        # Preparation (2) > Ended (1). Takže OK.
                        if sc >= best_cwl_score:
                            cwl_candidate = w
                            best_cwl_score = sc
                            
                if best_cwl_score == 3:
                     # Máme aktivní válku, není třeba hledat v dalších kolech
                     break

        # b) Zkusíme najít klasickou CW
        cw_candidate = await fetch_current_war(bot.clan_tag, bot.config)

        # c) Vyhodnocení priority: Active CWL > Active CW > Ended CWL > Ended CW
        def get_war_score(w):
            if not w: return 0
            s = w.get("state")
            if s in ("inWar", "preparation"): return 2
            if s == "warEnded": return 1
            return 0

        score_cwl = get_war_score(cwl_candidate)
        score_cw = get_war_score(cw_candidate)

        if score_cwl >= 2:
            selected_war = cwl_candidate
            selected_is_cwl = True
        elif score_cw >= 2:
            selected_war = cw_candidate
            selected_is_cwl = False
        elif score_cwl >= 1:
            selected_war = cwl_candidate
            selected_is_cwl = True
        elif score_cw >= 1:
            selected_war = cw_candidate
            selected_is_cwl = False

        if not selected_war or selected_war.get("state") is None:
            await send_ephemeral(interaction, "❌ Nepodařilo se získat data o žádné běžící ani nedávné válce (CWL/Klasická).")
            return

        war_data = dict(selected_war)  # kopie

        # --- 2) Zajisti, že náš klan je v klíči 'clan' (jinak prohoď strany) ---
        if war_data.get('opponent', {}).get('tag', '').upper() == our_tag:
            war_data['clan'], war_data['opponent'] = war_data['opponent'], war_data['clan']

        # --- 3) Počet útoků na člena ---
        attacks_per_member = war_data.get('attacksPerMember', 1 if selected_is_cwl else 2)

        # --- 4) Časy a formátování ---
        now = datetime.now(timezone.utc)
        start_time = clan_war_handler._parse_coc_time(war_data.get('startTime', ''))
        end_time = clan_war_handler._parse_coc_time(war_data.get('endTime', ''))

        def fmt_delta(seconds: float) -> str:
            return clan_war_handler._format_remaining_time(seconds)

        # --- 5) Helper: rozdělení na propojené vs. nepropojené a formát po 5 ---
        async def build_mentions_groups(members: list[dict]) -> tuple[list[str], list[str]]:
            """
            Vrací (bez_discord, s_discord) – každý je list řádků,
            kde každý řádek má max 5 položek a končí ' .'
            Bez Discord propojení: @herniNick
            S Discord propojením:  <@discordId> (nepřidáváme @ navíc)
            """
            no_discord_raw, with_discord_raw = [], []
            for m in members:
                tag = m.get("tag")
                # herní nick pro kopírování – chceme @nick
                name = m.get("name", "Unknown")
                # Discord mention (pokud existuje, očekáváme <@...>)
                mention = await clan_war_handler._get_discord_mention(tag)

                if mention:
                    with_discord_raw.append(mention)  # už je to správný mention, nepřidávat '@'
                else:
                    # požadovaný formát pro kopírování: @jmeno
                    no_discord_raw.append(f"@{name}")

            def chunk_five(lst: list[str]) -> list[str]:
                lines = []
                for i in range(0, len(lst), 5):
                    part = " ".join(lst[i:i + 5]) + " ."
                    lines.append(part)
                return lines

            return chunk_five(no_discord_raw), chunk_five(with_discord_raw)

        # --- 6) Stavové větve ---
        state = war_data["state"]
        if state == "notInWar":
            await send_ephemeral(interaction, "⚔️ Momentálně neprobíhá žádná klanová válka.")
            return

        clan_members = war_data.get('clan', {}).get('members', [])

        # PŘÍPRAVA
        if state == "preparation":
            if start_time:
                secs = max((start_time - now).total_seconds(), 0.0)
                await send_ephemeral(
                    interaction,
                    f"🛡️ Válka je ve fázi **přípravy**. Bitva začne za **{fmt_delta(secs)}**.\n"
                    f"(Zdroj: {'CWL' if selected_is_cwl else 'Clan War'})"
                )
            else:
                await send_ephemeral(interaction,
                                     f"🛡️ Válka je ve fázi **přípravy**. (Zdroj: {'CWL' if selected_is_cwl else 'Clan War'})")
            return

        # BATTLE DAY
        if state == "inWar":
            if oba_utoky:
                missing = [m for m in clan_members if len(m.get("attacks", [])) < attacks_per_member]
                label = "Hráči, kterým **zbývá alespoň 1 útok**:"
            else:
                missing = [m for m in clan_members if len(m.get("attacks", [])) == 0]
                label = "Hráči, kteří **neprovedli žádný útok**:"

            time_info = ""
            if end_time:
                secs_left = max((end_time - now).total_seconds(), 0.0)
                time_info = f" (zbývá **{fmt_delta(secs_left)}**)"

            header = f"⚔️ **Battle Day**{time_info} – {'CWL' if selected_is_cwl else 'Clan War'}."
            await send_ephemeral(interaction, header)

            if not missing:
                await send_ephemeral(interaction, "✅ Všichni relevantní hráči mají odehráno.")
                return

            await send_ephemeral(interaction, label)

            no_discord, with_discord = await build_mentions_groups(missing)

            if no_discord:
                await send_ephemeral(interaction, "**Bez Discord propojení:**")
                for line in no_discord:
                    await send_ephemeral(interaction, line)

            if with_discord:
                await send_ephemeral(interaction, "**S Discord propojením:**")
                for line in with_discord:
                    await send_ephemeral(interaction, line)
            return

        # WAR ENDED
        if state == "warEnded":
            if oba_utoky:
                missing = [m for m in clan_members if len(m.get("attacks", [])) < attacks_per_member]
                label = "**Neodehráli všemi dostupnými útoky:**"
            else:
                missing = [m for m in clan_members if len(m.get("attacks", [])) == 0]
                label = "**Neodehráli (0 útoků):**"

            when = ""
            if end_time:
                secs_ago = max((now - end_time).total_seconds(), 0.0)
                when = f" před **{fmt_delta(secs_ago)}**"

            header = f"🏁 Válka skončila{when}. {'(CWL)' if selected_is_cwl else '(Clan War)'}"
            await send_ephemeral(interaction, header)

            if not missing:
                await send_ephemeral(interaction, "✅ Nikdo nespadá do zadaného filtru.")
                return

            await send_ephemeral(interaction, label)

            no_discord, with_discord = await build_mentions_groups(missing)

            if no_discord:
                await send_ephemeral(interaction, "**Bez Discord propojení (kopírovat):**")
                for line in no_discord:
                    await send_ephemeral(interaction, line)

            if with_discord:
                await send_ephemeral(interaction, "**S Discord propojením:**")
                for line in with_discord:
                    await send_ephemeral(interaction, line)
            return

    @bot.tree.command(
        name="propoj_ucet",
        description="Propojí zadaný Discord účet s Clash of Clans účtem a přiřadí roli.",
        guild=bot.guild_object
    )
    @app_commands.describe(
        uzivatel="Discord uživatel k propojení",
        coc_tag="Clash of Clans tag (např. #ABC123)",
        coc_name="Jméno v Clash of Clans"
    )
    async def propojit_ucet(
            interaction: discord.Interaction,
            uzivatel: discord.Member,
            coc_tag: str,
            coc_name: str
    ):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        coc_tag = coc_tag.upper()
        if not coc_tag.startswith("#"):
            coc_tag = f"#{coc_tag}"

        try:
            add_coc_link(str(uzivatel.id), coc_tag, coc_name)

            role = interaction.guild.get_role(ROLE_VERIFIED)
            if role:
                try:
                    await uzivatel.add_roles(role, reason="Propojení Clash of Clans účtu")
                except discord.Forbidden:
                    await send_ephemeral(interaction, "⚠️ Nepodařilo se přiřadit roli – chybí oprávnění.")

            await interaction.response.send_message(
                f"✅ Účet **{coc_name}** ({coc_tag}) byl propojen s {uzivatel.mention} a byla mu přiřazena role.",
                ephemeral=False
            )

            try:
                await uzivatel.send(
                    f"🔗 Tvůj Discord účet byl propojen s Clash of Clans účtem **{coc_name}** (`{coc_tag}`).")
            except Exception:
                pass

        except Exception as e:
            await send_ephemeral(interaction, f"❌ Nepodařilo se uložit propojení: {e}")

    @bot.tree.command(
        name="odpoj_ucet",
        description="Odpojí Clash of Clans účet od Discord uživatele a odebere roli.",
        guild=bot.guild_object
    )
    @app_commands.describe(
        uzivatel="Discord uživatel k odpojení (pokud vynecháš, odpojí tebe)"
    )
    async def odpoj_ucet(
            interaction: discord.Interaction,
            uzivatel: discord.Member | None = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        uzivatel = uzivatel or interaction.user

        try:
            remove_coc_link(str(uzivatel.id))

            role = interaction.guild.get_role(ROLE_VERIFIED)
            if role and role in uzivatel.roles:
                try:
                    await uzivatel.remove_roles(role, reason="Odpojení Clash of Clans účtu")
                except discord.Forbidden:
                    await send_ephemeral(interaction, "⚠️ Nepodařilo se odebrat roli – chybí oprávnění.")

            await interaction.response.send_message(
                f"🗑️ Propojení bylo odstraněno a roli jsem odebral uživateli {uzivatel.mention}.",
                ephemeral=False
            )

            try:
                await uzivatel.send("🔌 Tvé propojení s Clash of Clans účtem bylo zrušeno a role odebrána.")
            except Exception:
                pass

        except Exception as e:
            await send_ephemeral(interaction, f"❌ Nepodařilo se odpojit účet: {e}")

    @bot.tree.command(
        name="seznam_propojeni",
        description="Vypíše seznam všech Discord ↔ CoC propojení.",
        guild=bot.guild_object
    )
    async def seznam_propojeni(interaction: discord.Interaction):
        # ✅ Povolení: pouze Co-Leader nebo Administrátor
        if not (_is_admin(interaction.user) or _is_co_leader(interaction.user)):
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze **Co-Leader** nebo **Administrátor**.")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            links = get_all_links()
        except Exception as e:
            await send_ephemeral(interaction, f"❌ Chyba při čtení databáze: {e}")
            return

        if not links:
            await send_ephemeral(interaction, "ℹ️ Zatím nejsou žádná propojení.")
            return

        lines = ["**Seznam propojených účtů:**"]
        for discord_id, (tag, name) in links.items():
            lines.append(f"- <@{discord_id}> → **{name}** (`{tag}`)")

        await send_ephemeral(interaction, "\n".join(lines), delete_after=300)  # 5 minut pro delší výpisy

    @bot.tree.command(name="pravidla_discord", description="Zobrazí pravidla Discord serveru", guild=bot.guild_object)
    async def pravidla_discord(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        await send_ephemeral(interaction, "Pravidla zobrazena", delete_after=1)

        embed = discord.Embed(
            title="📜 Pravidla Discord serveru",
            description="Pravidla pro všechny členy našeho Discord serveru:",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="1. Chování a komunikace",
            value="• Respektujte všechny členy serveru\n"
                  "• Žádné urážky, rasismus, sexismu nebo jiná forma diskriminace\n"
                  "• Mluvte výhradně česky\n"
                  "• Žádné spammování nebo floodování zprávami\n"
                  "• Dodržujte témata kanálů",
            inline=False
        )

        embed.add_field(
            name="2. Sdílení obsahu",
            value="• Odkazy smíte posílat pouze pokud se týkají kontextu konverzace\n"
                  "• Zakázány jsou náhodné Discord invite nebo reklamy\n"
                  "• NSFW obsah je striktně zakázán",
            inline=False
        )

        embed.add_field(
            name="3. Role a oprávnění",
            value="• Nežádejte o vyšší role - ty se přidělují podle postavení v klanu\n"
                  "• Zneužívání rolí nebo botů bude potrestáno\n"
                  "• Moderátoři mají vždy pravdu",
            inline=False
        )

        embed.add_field(
            name="4. Hlasové kanály",
            value="• Respektujte toho, kdo mluví\n"
                  "• Žádné rušení hlukem v pozadí\n"
                  "• Hudba pouze v určených kanálech",
            inline=False
        )

        embed.set_footer(text="Porušení pravidel může vést k mute, kick nebo banu, podle závažnosti přestupku")

        await interaction.response.send_message("Pravidla zobrazena", ephemeral=True, delete_after=1)
        await interaction.channel.send(embed=embed)

    @bot.tree.command(name="pravidla_clan", description="Zobrazí pravidla herního klanu", guild=bot.guild_object)
    async def pravidla_clan(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        await send_ephemeral(interaction, "Pravidla zobrazena", delete_after=1)

        embed = discord.Embed(
            title="⚔️ Pravidla Klanu Czech Heroes",
            description="Pravidla pro všechny členy našeho herního klanu:",
            color=discord.Color.gold()
        )

        # Sekce obecná pravidla
        embed.add_field(
            name="🔹 Obecná pravidla",
            value="• Minimální aktivita 3 dny - po delší neaktivitě hrozí kick\n"
                  "• Clan Games: od každého očekáváme minimálně 1000 bodů\n"
                  "• Clan Capital: povinné využít všech 6 útoků\n"
                  "• Donate: darujte co to jde, ideálně nemít donate na 0",
            inline=False
        )

        # Výrazně zvýrazněná sekce Clan War
        embed.add_field(
            name="⚔️ CLAN WAR - NEJDŮLEŽITĚJŠÍ PRAVIDLA",
            value="```diff\n"
                  "+ 1. útok: VŽDY MIRROR (stejné číslo)\n"
                  "+ Ideálně odehrát před 5. hodinou do konce války\n\n"
                  "+ 2. útok: oprava nějakého cizího útoku\n"
                  "+ Nebo na koho chcete, pokud zbývá méně než 5h do konce CW\n\n"
                  "! Neodehrání útoku = VAROVÁNÍ\n"
                  "```",
            inline=False
        )

        # Sekce přihlašování do waru
        embed.add_field(
            name="📝 Přihlašování do Clan War",
            value="• Pár hodin před začátkem války pošlu \"Clan War Sign-Up\"\n"
                  "• Palec nahoru = 100% účast (musíš dodržet pravidla)\n"
                  "• Palec dolů = 100% nebudeš ve válce\n"
                  "• Nereaguješ + zelený štít = možná účast (doplňujeme počet)\n"
                  "• Nereaguješ + červený štít = nebudeš ve válce",
            inline=False
        )

        embed.add_field(
            name="ℹ️ Poznámky",
            value="• Války vždy začínají ve večerních hodinách (17-24)\n"
                  "• Pravidla se mohou v budoucnu změnit\n"
                  "• Kicknutí členové mohou dostat pozvánku zpátky pokud vím že byly aktivní",
            inline=False
        )

        embed.set_footer(text="Po 3 varováních hrozí kick z klanu")

        await interaction.response.send_message("Pravidla zobrazena", ephemeral=True, delete_after=1)
        await interaction.channel.send(embed=embed)

    @bot.tree.command(name="vitej", description="Vítej na našem Discord serveru", guild=bot.guild_object)
    async def vitej(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        await send_ephemeral(interaction, "Vítej zpráva odeslána", delete_after=1)

        embed = discord.Embed(
            title="🎉 Vítej na Discord serveru Czech Heroes!",
            description="Oficiální Discord pro herní klan **Czech Heroes** ze hry Clash of Clans!",
            color=discord.Color.green()
        )

        # Sekce pro členy klanu
        embed.add_field(
            name="🔹 Jsi členem našeho klanu?",
            value=(
                f"1. Projdi si pravidla v {interaction.guild.get_channel(RULES_CHANNEL_ID).mention}\n"
                f"2. Proveď ověření v {interaction.guild.get_channel(VERIFICATION_CHANNEL_ID).mention}\n"
                "3. Po ověření získáš automaticky:\n"
                "   - Speciální roli podle postavení v klanu (Leader, Co-leader, Elder...)\n"
                "   - Role na míru podle počtu pohárků, TH level, Liga\n"
                "   - Přezdívka na Discord serveru nastavena na herní jméno"
                "   - Přístup ke všem sekcím serveru"
            ),
            inline=False
        )

        # Sekce pro návštěvníky
        embed.add_field(
            name="🔹 Jsi návštěvník?",
            value=(
                "I pro tebe máme omezený přístup(někdy):\n"
                "- Můžeš pokecat v obecných chatech\n"
                "- Podívat se na pravidla\n"
                "- Případně se připojit do klanu a projít plnou verifikací"
            ),
            inline=False
        )

        # Sekce s výhodami serveru
        embed.add_field(
            name="📊 Co všechno zde najdeš?",
            value=(
                f"- Přehledné statistiky o Clan War v {interaction.guild.get_channel(WAR_INFO_CHANNEL_ID).mention}\n"
                f"   - Aktuální Clan War útoky a obrany v {interaction.guild.get_channel(WAR_EVENTS_CHANNEL_ID).mention}\n"
                f"- Detaily o Clan Capital v {interaction.guild.get_channel(CAPITAL_STATUS_CHANNEL_ID).mention}\n"
                f"- Herní eventy v {interaction.guild.get_channel(CLASH_OF_CLANS_EVENT_CHANNEL_ID).mention}\n"
                f"- Místo pro obecný pokec v {interaction.guild.get_channel(GENERAL_CHANNEL_ID).mention}\n"
                "- Tipy a triky jak hrát lépe\n"
                "- A mnohem více!"
            ),
            inline=False
        )

        embed.set_footer(text="Těšíme se na tebe v našem klanu i na Discordu!")

        await interaction.response.send_message("Vítej zpráva odeslána", ephemeral=True, delete_after=1)
        await interaction.channel.send(embed=embed)

    @bot.tree.command(
        name="vypis_log",
        description="Vypíše poslední řádky z log souboru (pouze pro administrátory)",
        guild=bot.guild_object
    )
    @app_commands.describe(
        pocet_radku="Kolik posledních řádků zobrazit (default: 50, max: 500)"
    )
    async def vypis_log(interaction: discord.Interaction, pocet_radku: int = 50):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        pocet_radku = min(max(pocet_radku, 1), 500)
        await interaction.response.defer(ephemeral=True, thinking=True)

        log_file = Path(__file__).parent / "CoCDiscordBot.log"

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if not lines:
                await send_ephemeral(interaction, "ℹ️ Log soubor je prázdný.")
                return

            last_lines = lines[-pocet_radku:]
            current_chunk = []
            current_length = 0

            for line in last_lines:
                line_length = len(line)

                if current_length + line_length > 1900:
                    if current_chunk:
                        await send_ephemeral(interaction, f"```\n{''.join(current_chunk)}\n```", delete_after=300)
                        current_chunk = []
                        current_length = 0

                    if line_length > 1900:
                        parts = [line[i:i + 1900] for i in range(0, len(line), 1900)]
                        for part in parts[:-1]:
                            await send_ephemeral(interaction, f"```\n{part}\n```", delete_after=300)
                        line = parts[-1]
                        line_length = len(line)

                current_chunk.append(line)
                current_length += line_length

            if current_chunk:
                await send_ephemeral(interaction, f"```\n{''.join(current_chunk)}\n```", delete_after=300)

        except FileNotFoundError:
            await send_ephemeral(interaction, f"❌ Log soubor '{log_file}' nebyl nalezen.")
        except Exception as e:
            await send_ephemeral(interaction, f"❌ Chyba při čtení log souboru: {e}")

    @bot.tree.command(name="aktualizujrole", description="Aktualizuje role všech propojených členů",
                      guild=bot.guild_object)
    async def aktualizujrole(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze administrátor.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        clan_members = get_all_members()
        user_mapping = get_all_links()

        if not clan_members or not user_mapping:
            await interaction.followup.send("❌ Chyba: nebyla načtena databáze členů nebo propojení.", ephemeral=True)
            print(f"❌ [bot_commands] Chyba: nebyla načtena databáze členů nebo propojení.")
            print(f"❌ [bot_commands] Členové: {clan_members}")
            print(f"❌ [bot_commands] Propojení: {user_mapping}")
            return

        await update_roles(interaction.guild, user_mapping, clan_members)
        await interaction.followup.send("✅ Role byly úspěšně aktualizovány!", ephemeral=True)

    @bot.tree.command(name="vytvor_verifikacni_tabulku", description="Vytvoří verifikační tabulku s tlačítkem",
                      guild=bot.guild_object)
    async def vytvor_verifikacni_tabulku(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze administrátor.", ephemeral=True)
            return

        embed = discord.Embed(
            title="✅ Ověření účtu pro klan Czech Heroes",
            description=(
                "- Klikni na tlačítko níže a ověř svůj účet!\n"
                "- Ověřování je jen pro členy klanu Czech Heroes\n"
                f"- Nezapomeň si nejprve přečíst pravidla: {interaction.guild.get_channel(RULES_CHANNEL_ID).mention}\n"
                "- Discord účet bude propojen s Clash of Clans účtem\n"
                "- Po kliknutí zadáš své jméno nebo #tag\n"
                "- Provedeš ověření výběrem equipmentu na hrdinu\n"
                "   - Pokud jsi již ověřený, nelze ověřit znovu\n"
                f"   - Bot musí být online: <@{BOT_USER_ID}>\n"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="- Czech Heroes klan 🔒")

        view = VerifikacniView()
        await interaction.channel.send(embed=embed, view=view)

        overwrite = discord.PermissionOverwrite()
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        await interaction.response.send_message("✅ Verifikační tabulka vytvořena a kanál uzamčen!", ephemeral=True)

    async def _send_commands_help(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        def _commands_permissions_table_embed(role_index: int) -> discord.Embed:
            # role_index: 0=Verified, 1=Elder, 2=Co-Leader
            roles = ["Verified", "Elder", "Co-Leader"]
            role_name = roles[role_index]

            # Define command matrix and descriptions
            commands = [
                ("kdo_neodehral", "Vypíše hráče, kteří neodehráli (nebo kterým zbývá útok)."),
                ("seznam_propojeni", "Seznam propojení Discord ↔ CoC."),
                ("pridej_varovani", "Přidá/naplánuje varování pro hráče."),
                ("vypis_varovani", "Vypíše varování. Bez parametrů kdokoli ověřený; s parametry jen Co-Leader."),
            ]

            # Permission matrix by role
            def can_for(role, cmd):
                if cmd == "kdo_neodehral":
                    return role in ("Elder", "Co-Leader")
                if cmd == "seznam_propojeni":
                    return role in ("Co-Leader",)
                if cmd == "pridej_varovani":
                    return role in ("Co-Leader",)
                if cmd == "vypis_varovani":
                    # Verified: own/no params; Elder: jako Verified; Co-Leader: full
                    return True
                return False

            lines = []
            for name, desc in commands:
                allowed = can_for(
                    "Co-Leader" if role_index == 2 else ("Elder" if role_index == 1 else "Verified"),
                    name
                )
                mark = "✅" if allowed else "❌"
                lines.append(f"**/{name}** — {mark}\n{desc}")

            embed = discord.Embed(
                title=f"📋 Commands – {role_name}",
                description="\n\n".join(lines),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Tip: ⬅️ ➡️ pro přepínání rolí • Administrátor má přístup ke všem příkazům.")
            return embed

        # pick start index based on caller's role
        def _start_index_for_user(member: discord.Member) -> int:
            if _is_co_leader(member):
                return 2
            if _is_elder(member):
                return 1
            return 0

        index = _start_index_for_user(interaction.user)  # 0=Verified,1=Elder,2=Co-Leader
        author_id = interaction.user.id

        view = discord.ui.View(timeout=60.0)

        left_btn = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary)
        right_btn = discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary)

        async def _guard(inter: discord.Interaction) -> bool:
            if inter.user.id != author_id:
                await inter.response.send_message("🔒 Tohle může ovládat jen autor zobrazení.", ephemeral=True)
                return False
            return True

        async def on_left(inter: discord.Interaction):
            nonlocal index
            if not await _guard(inter):
                return
            index = (index - 1) % 3
            await inter.response.edit_message(embed=_commands_permissions_table_embed(index), view=view)

        async def on_right(inter: discord.Interaction):
            nonlocal index
            if not await _guard(inter):
                return
            index = (index + 1) % 3
            await inter.response.edit_message(embed=_commands_permissions_table_embed(index), view=view)

        left_btn.callback = on_left
        right_btn.callback = on_right
        view.add_item(left_btn)
        view.add_item(right_btn)

        await interaction.followup.send(embed=_commands_permissions_table_embed(index), view=view, ephemeral=True)

    @bot.tree.command(name="commands", description="Zobrazí přehled příkazů a oprávnění.", guild=bot.guild_object)
    async def commands_cmd(interaction: discord.Interaction):
        await _send_commands_help(interaction)

    @bot.tree.command(name="help", description="Zobrazí přehled příkazů a oprávnění.", guild=bot.guild_object)
    async def help_cmd(interaction: discord.Interaction):
        await _send_commands_help(interaction)

    # Constants moved to constants.py

    # ===== VIEWS A HELPER FUNKCE =====
    class SectionSelectView(discord.ui.View):
        """View pro výběr sekce max levelů"""

        def __init__(self, th_level: int):
            super().__init__(timeout=180)
            self.th_level = th_level
            self.message = None

        async def on_timeout(self):
            """Automaticky smaže zprávu po timeoutu"""
            try:
                if self.message:
                    await self.message.delete()
            except:
                pass
        @discord.ui.select(
            placeholder="Vyber co chceš zobrazit...",
            options=[
                discord.SelectOption(label="Heroes", value="heroes", emoji="🦸", description="Max levely hrdinů"),
                discord.SelectOption(label="Pets", value="pets", emoji="🐾", description="Max levely zvířat"),
                discord.SelectOption(label="Equipment", value="equipment", emoji="⚔️",
                                     description="Max levely vybavení"),
                discord.SelectOption(label="Laboratory Upgrades", value="lab", emoji="🧪",
                                     description="Výzkumy v laboratoři"),
                discord.SelectOption(label="Buildings", value="buildings", emoji="🏗️", description="Max levely budov")
            ]
        )
        async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
            section = select.values[0]

            if section == "heroes":
                embed = create_th_embed(self.th_level)
                view = THLevelView(self.th_level, section)
            elif section == "pets":
                embed = create_pets_embed(self.th_level)
                view = THLevelView(self.th_level, section)
            elif section == "equipment":
                embed = create_equipment_embed(self.th_level)
                view = THLevelView(self.th_level, section)
            elif section == "lab":
                embed = create_lab_embed(self.th_level)
                view = THLevelView(self.th_level, section)
            else:
                embed = discord.Embed(
                    title="Připravujeme...",
                    description=f"Sekce **{section}** je aktuálně ve vývoji a brzy bude dostupná!",
                    color=discord.Color.orange()
                )
                view = None

            await interaction.response.edit_message(embed=embed, view=view)
            if view:
                view.message = interaction.message



    class THLevelView(discord.ui.View):
        """View pro procházení TH levelů s podporou sekcí"""

        def __init__(self, initial_th: int, section: str):
            super().__init__(timeout=180)
            self.th_level = initial_th
            self.section = section
            self.message = None
            self.update_buttons()

        async def on_timeout(self):
            """Automaticky smaže zprávu po timeoutu"""
            try:
                if self.message:
                    await self.message.delete()
            except:
                pass

        def update_buttons(self):
            self.clear_items()

            # Tlačítka pro změnu TH - zobrazíme jen pokud existuje vyšší/nižší úroveň
            if self.th_level > 10:  # Minimální podporovaný TH
                prev_btn = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary, row=0, label="  ")
                prev_btn.callback = self.on_prev_button
                self.add_item(prev_btn)

            if self.th_level < 17:  # Maximální podporovaný TH
                next_btn = discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary, row=0, label="  ")
                next_btn.callback = self.on_next_button
                self.add_item(next_btn)

            # Tlačítko pro návrat k výběru sekce
            back_btn = discord.ui.Button(label="Zpět na výběr", style=discord.ButtonStyle.primary, row=1)
            back_btn.callback = self.on_back_button
            self.add_item(back_btn)

        async def on_prev_button(self, interaction: discord.Interaction):
            if self.th_level > 10:
                self.th_level -= 1
                self.update_buttons()
                await self.update_embed(interaction)

        async def on_next_button(self, interaction: discord.Interaction):
            if self.th_level < 17:
                self.th_level += 1
                self.update_buttons()
                await self.update_embed(interaction)

        async def on_back_button(self, interaction: discord.Interaction):
            view = SectionSelectView(self.th_level)
            embed = discord.Embed(
                title=f"🔹 {interaction.user.display_name} - TH{self.th_level}",
                description="Vyber sekci, kterou chceš zobrazit:",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=view)
            view.message = interaction.message

        async def update_embed(self, interaction: discord.Interaction):
            if self.section == "heroes":
                embed = create_th_embed(self.th_level)
            elif self.section == "pets":
                embed = create_pets_embed(self.th_level)
            elif self.section == "equipment":
                embed = create_equipment_embed(self.th_level)
            elif self.section == "lab":
                embed = create_lab_embed(self.th_level)
            else:
                embed = discord.Embed(title="Chyba", description="Nepodporovaná sekce", color=discord.Color.red())

            await interaction.response.edit_message(embed=embed, view=self)

    def create_th_embed(th_level: int) -> discord.Embed:
        th_data = max_heroes_lvls.get(th_level, {})
        embed = discord.Embed(
            title=f"{TOWN_HALL_EMOJIS.get(th_level, '')} Town Hall {th_level} – Max. levely hrdinů",
            color=discord.Color.orange()
        )

        for hero, level in th_data.items():
            emoji = HEROES_EMOJIS.get(hero, "")
            embed.add_field(name=f"{emoji} {hero}", value=f"**{level}**", inline=True)

        embed.set_footer(text="Použij tlačítka pro změnu úrovně")
        return embed

    def create_pets_embed(th_level: int) -> discord.Embed:
        # Získání max Pet House pro daný TH
        max_ph = TH_TO_PET_HOUSE.get(th_level, 0)

        if max_ph == 0:
            return discord.Embed(
                title="Pets nejsou dostupné",
                description="Pets jsou dostupné až od Town Hall 14.",
                color=discord.Color.orange()
            )

        pet_data = PET_MAX_LEVELS.get(max_ph, {})

        # Rozdělení petů do dvou sloupců
        pets = list(pet_data.keys())
        half = len(pets) // 2
        col1 = pets[:half]
        col2 = pets[half:]

        embed = discord.Embed(
            title=f"{TOWN_HALL_EMOJIS.get(th_level, '')} TH {th_level} Pets (Pet House {max_ph})",
            color=discord.Color.green()
        )

        # První sloupec
        col1_text = ""
        for pet in col1:
            level = pet_data[pet]
            col1_text += f"{pet}: **{level if level > 0 else '-'}**\n"
        embed.add_field(name="Zvířata", value=col1_text, inline=True)

        # Druhý sloupec
        col2_text = ""
        for pet in col2:
            level = pet_data[pet]
            col2_text += f"{pet}: **{level if level > 0 else '-'}**\n"
        embed.add_field(name="\u200b", value=col2_text, inline=True)

        # Prázdný sloupec pro lepší zarovnání
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        embed.set_footer(text=f"Maximální úroveň Pet House pro TH{th_level} je {max_ph}")
        return embed

    def create_equipment_embed(th_level: int) -> discord.Embed:
        blacksmith_level = TH_TO_BLACKSMITH.get(th_level, 0)

        if blacksmith_level == 0:
            return discord.Embed(
                title="Blacksmith není dostupný",
                description="Blacksmith je dostupný až od Town Hall 8.",
                color=discord.Color.orange()
            )

        # Získání všech dostupných levelů Blacksmithu pro daný TH
        available_levels = [lvl for lvl in EQUIPMENT_DATA.keys() if lvl <= blacksmith_level]

        embed = discord.Embed(
            title=f"{TOWN_HALL_EMOJIS.get(th_level, '')} TH {th_level} - Blacksmith (Level {blacksmith_level})",
            color=discord.Color.dark_gold()
        )

        # Přidání informací o aktuálním max levelu
        current_data = EQUIPMENT_DATA.get(blacksmith_level, {})
        embed.add_field(
            name="🔹 Aktuální max levely",
            value=f"Common: **{current_data.get('common', 'N/A')}**\nEpic: **{current_data.get('epic', 'N/A')}**",
            inline=False
        )

        # Přidání seznamu odemčených equipmentů
        unlocked_items = []
        for lvl in available_levels:
            data = EQUIPMENT_DATA.get(lvl, {})
            unlocked_items.append(f"**Level {lvl}:** {data.get('unlock', 'N/A')}")

        embed.add_field(
            name="🔹 Odemčené equipmenty",
            value="\n".join(unlocked_items) if unlocked_items else "Žádné",
            inline=False
        )

        # Přidání informace o TH požadavcích
        embed.add_field(
            name="🔹 Požadavky na TH",
            value=f"Pro upgrade na vyšší level Blacksmithu potřebuješ:\n"
                  f"Level 2 → TH9\nLevel 3 → TH10\nLevel 4 → TH11\n"
                  f"Level 5 → TH12\nLevel 6 → TH13\nLevel 7 → TH14\n"
                  f"Level 8 → TH15\nLevel 9 → TH16",
            inline=False
        )

        embed.set_footer(text=f"Maximální úroveň Blacksmithu pro TH{th_level} je {blacksmith_level}")
        return embed

    def create_lab_embed(th_level: int) -> discord.Embed:
        lab_level = TH_TO_LAB.get(th_level, 0)

        if lab_level == 0:
            return discord.Embed(
                title="Laboratoř není dostupná",
                description="Laboratoř je dostupná až od Town Hall 3.",
                color=discord.Color.orange()
            )

        embed = discord.Embed(
            title=f"{TOWN_HALL_EMOJIS.get(th_level, '')} TH {th_level} - Laboratory (Level {lab_level})",
            color=discord.Color.purple()
        )

        # Funkce pro získání maximální úrovně
        def get_max_level(upgrades_dict):
            max_level = 0
            for lab_lvl, upgrade_lvl in upgrades_dict.items():
                if lab_lvl <= lab_level:
                    if isinstance(upgrade_lvl, tuple):
                        current_max = max(upgrade_lvl)
                    else:
                        current_max = upgrade_lvl
                    if current_max > max_level:
                        max_level = current_max
            return max_level

        # Přidání dostupných upgradů jednotek
        available_troops = []
        for troop, levels in TROOP_UPGRADES.items():
            max_level = get_max_level(levels)
            if max_level > 0:
                available_troops.append(f"**{troop}:** {max_level}")

        embed.add_field(
            name="🔹 Dostupné upgrady jednotek",
            value="\n".join(available_troops) if available_troops else "Žádné",
            inline=False
        )

        # Přidání dostupných upgradů Siege Machines
        available_siege = []
        for siege, levels in SIEGE_MACHINE_UPGRADES.items():
            max_level = get_max_level(levels)
            if max_level > 0:
                available_siege.append(f"**{siege}:** {max_level}")

        embed.add_field(
            name="🔹 Dostupné upgrady Siege Machines",
            value="\n".join(available_siege) if available_siege else "Žádné",
            inline=False
        )

        # Přidání dostupných upgradů kouzel
        available_spells = []
        for spell, levels in SPELL_UPGRADES.items():
            max_level = get_max_level(levels)
            if max_level > 0:
                available_spells.append(f"**{spell}:** {max_level}")

        embed.add_field(
            name="🔹 Dostupné upgrady kouzel",
            value="\n".join(available_spells) if available_spells else "Žádné",
            inline=False
        )

        return embed

    # ===== UPRAVENÝ PŘÍKAZ /max_lvl =====
    @bot.tree.command(
        name="max_lvl",
        description="Zobrazí max levely pro tvé Town Hall",
        guild=bot.guild_object
    )
    async def max_hero_lvl(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            links = get_all_links()
            members = get_all_members()

            # Získání všech možných ID reprezentací uživatele
            discord_ids_to_check = [
                str(interaction.user.id),  # String ID
                interaction.user.id,  # Integer ID
                f"<@{interaction.user.id}>"  # Mention formát
            ]

            coc_tag = None
            coc_name = None

            # Prohledáme všechny možné formáty ID
            for discord_id in discord_ids_to_check:
                if discord_id in links:
                    coc_tag, coc_name = links[discord_id]
                    break

            if not coc_tag:
                # Debug výpis pro kontrolu
                print(f"[DEBUG] User {interaction.user.id} not found in links. Available links: {links}")
                await interaction.followup.send(
                    "❌ Nemáš propojený účet. Propoj ho nejdříve pomocí ověření nebo příkazu `/propoj_ucet`.\n"
                    f"Pokud si myslíš, že je to chyba, kontaktuj administrátora a uveď své ID: `{interaction.user.id}`",
                    ephemeral=True
                )
                return

            # Normalizace tagu (pro případ, že v databázi není uppercase)
            coc_tag_upper = coc_tag.upper()

            # Hledání hráče - kontrolujeme obě varianty tagu (původní a uppercase)
            player = next(
                (m for m in members
                 if m['tag'].upper() == coc_tag_upper or m['tag'] == coc_tag),
                None
            )

            if not player:
                await interaction.followup.send(
                    "❌ Nenalezeny tvé herní údaje v databázi klanu. Jsi aktuálním členem klanu?",
                    ephemeral=True
                )
                return

            th_level = player.get('townHallLevel', 0)

            if th_level < 10 or th_level > 17:
                await interaction.followup.send(
                    f"❌ TVůj Town Hall {th_level} není podporován (podporujeme TH 10-17)",
                    ephemeral=True
                )
                return

            # Zobrazíme výběr sekce
            view = SectionSelectView(th_level)
            message = await interaction.followup.send(
                f"🔹 {interaction.user.display_name} - TH{th_level}\nVyber sekci, kterou chceš zobrazit:",
                view=view,
                ephemeral=True,
                wait=True
            )
            view.message = message

        except Exception as e:
            print(f"[ERROR] in max_lvl command: {str(e)}")
            await interaction.followup.send(
                "❌ Došlo k chybě při zpracování příkazu. Administrátor byl informován.",
                ephemeral=True
            )

    # ========== /infolog ==========
    @bot.tree.command(
        name="infolog",
        description="Zobrazí důležité debug informace o botovi (pouze pro leadra).",
        guild=bot.guild_object
    )
    async def infolog(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not _is_leader(interaction.user):
            await interaction.followup.send("❌ Tento příkaz může použít pouze leader.", ephemeral=True)
            return

        import sys
        import platform
        import psutil
        import time

        try:
            import coc
            coc_version = coc.__version__
        except Exception:
            coc_version = "Neznámá"

        # Převod sekund na srozumitelný čas
        def humanize_seconds(sec: int) -> str:
            d, rem = divmod(sec, 86400)
            h, rem = divmod(rem, 3600)
            m, s = divmod(rem, 60)
            parts = []
            if d: parts.append(f"{d}d")
            if h: parts.append(f"{h}h")
            if m: parts.append(f"{m}m")
            if s or not parts: parts.append(f"{s}s")
            return " ".join(parts)

        process = psutil.Process(os.getpid())
        bot_uptime = time.time() - process.create_time()
        uptime_str = humanize_seconds(int(bot_uptime))

        mem_info = process.memory_info()
        memory_mb = mem_info.rss / (1024 * 1024)

        os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
        py_version = sys.version.split()[0]
        discord_version = discord.__version__

        latency = round(bot.latency * 1000, 2)
        cogs = len(bot.cogs)

        try:
            active_tasks = len(asyncio.all_tasks())
        except RuntimeError:
            active_tasks = 0

        embed = discord.Embed(title="📊 InfoLog - Debug Informace", color=discord.Color.blue())
        embed.add_field(
            name="🤖 Bot Info", 
            value=f"**Uptime:** {uptime_str}\n**Ping:** {latency} ms\n**Cogs:** {cogs}\n**Async Tasks:** {active_tasks}", 
            inline=False
        )
        embed.add_field(
            name="💻 Systém & Prostředí", 
            value=f"**OS:** {os_info}\n**RAM (Bot):** {memory_mb:.2f} MB\n**Python:** {py_version}\n**Discord.py:** {discord_version}\n**Coc.py:** {coc_version}", 
            inline=False
        )

        if hasattr(bot, 'clan_tag'):
            embed.add_field(name="⚔️ Coc Config", value=f"**Clan Tag:** {bot.clan_tag}", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)