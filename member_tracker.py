import sqlite3
from datetime import datetime, timezone

import asyncio
import discord
from typing import Optional
from discord.ext import commands

from database import DB_PATH, remove_coc_link, get_all_links  # reuse existující logiku
from constants import LOG_CHANNEL_ID, WELCOME_CHANNEL_ID as CLAN_LEAVE_LOG_ID

# ~~~~~ Fronta tagů, kterým je třeba udělat "úklid" ~~~~~
_leave_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=0)   # neomezená

async def discord_sync_members_once(bot: discord.Client):
    """
    • Zajistí tabulku `server_members`
    • Přidá do ní nově přítomné lidi
    • Pro zmizelé:
        – smaže řádek z `server_members`
        – zavolá remove_coc_link()
        – napíše hlášku do LOG_CHANNEL_ID
    """
    guild = getattr(bot, "guild_object", None)
    if guild is None:
        print("[member_tracker] ❌ bot.guild_object není nastavené – přeskočeno")
        return

    _ensure_table()

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # aktuální uživatelé (boty ignorujeme)
    current_ids = {str(m.id) for m in guild.members if not m.bot}

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT discord_id FROM server_members")
        db_ids = {row[0] for row in cur.fetchall()}

        # ➕ kdo se přidal
        to_add = current_ids - db_ids
        if to_add:
            cur.executemany(
                "INSERT OR IGNORE INTO server_members (discord_id, joined_at) VALUES (?, ?)",
                [(mid, now_iso) for mid in to_add],
            )

        # ➖ kdo zmizel
        to_remove = db_ids - current_ids
        for mid in to_remove:
            # 1) odeber propojení
            remove_coc_link(mid)
            # 2) smaž z tabulky
            cur.execute("DELETE FROM server_members WHERE discord_id = ?", (mid,))
            # 3) logni do kanálu
            channel = guild.get_channel(LOG_CHANNEL_ID)
            if channel:
                await channel.send(
                    f"👋 Uživatel <@{mid}> odešel ze serveru – jeho propojení bylo odstraněno."
                )
            print(f"[member_tracker] Odešel <@{mid}> – propojení smazáno")

        conn.commit()

    if to_add or to_remove:
        print(
            f"[member_tracker] Sync hotová – přidáno {len(to_add)}, odstraněno {len(to_remove)}"
        )


# -----------------------------------------------------------
#  interní util
# -----------------------------------------------------------
def _ensure_table():
    """Vytvoří tabulku server_members, pokud neexistuje."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_members (
                discord_id TEXT PRIMARY KEY,
                joined_at  TEXT
            )
            """
        )
        conn.commit()

def queue_clan_departure(tag: str):
    """Volá se ze `database.py`, kdykoli je hráč odstraněn z tabulky clan_members."""
    try:
        _leave_queue.put_nowait(tag.upper())
    except asyncio.QueueFull:
        print(f"⚠️ [member_tracker] Fronta plná, tag {tag} zahazuji.")

# --------------------------------------------------------
# veřejný worker – vytáhne tag z fronty a zpracuje
# --------------------------------------------------------
async def cleanup_after_coc_departure(bot: discord.Client, coc_tag: str):
    """
    Spustí úklid pro uživatele s daným CoC tagem, pokud je ještě propojený.
    """
    coc_tag = coc_tag.upper()
    guild = getattr(bot, "guild_object", None)
    if not guild:
        print("❌ [cleanup] guild_object není nastaven.")
        return

    links = get_all_links()
    discord_id = None
    for d_id, (tag, _) in links.items():
        if tag.upper() == coc_tag:
            discord_id = d_id
            break

    if discord_id is None:
        return  # uživatel nemá propojení – nic dál

    remove_coc_link(str(discord_id))

    member = guild.get_member(discord_id)
    if member:
        try:
            roles_to_remove = [r for r in member.roles if r != guild.default_role]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Opustil CoC klan")

            try:
                await member.edit(nick="Odešel z klanu", reason="Opustil CoC klan")
            except discord.Forbidden:
                pass
        except discord.Forbidden:
            print(f"⚠️ [cleanup] Nemám oprávnění upravit {member.display_name}")

    channel = guild.get_channel(CLAN_LEAVE_LOG_ID)
    if channel:
        embed = discord.Embed(
            title=f"👋 Díky, že jsi s námi byl, <@{discord_id}>!",
            description=(
                "(ne)budeš nám chybět 😉\n\n"
                "🧹 Tvoje propojení s Clash of Clans bylo odstraněno\n"
                "Role klanu byly odebrány."
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(
            text="🎯 Rozmyslíš-li si to, dveře Czech Heroes jsou ti opět otevřené!"
        )
        await channel.send(embed=embed)

    print(f"✅ [cleanup] Úklid hotov pro {coc_tag} / <@{discord_id}>")