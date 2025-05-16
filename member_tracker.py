import sqlite3
from datetime import datetime, timezone

import asyncio
import discord
from typing import Optional
from discord.ext import commands

from database import DB_PATH, remove_coc_link   # reuse existující logiku

LOG_CHANNEL_ID = 1371089891621998652

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
        print(f"[member_tracker] ⚠️ Fronta plná, tag {tag} zahazuji.")


# --------------------------------------------------------
# interní funkce – dělá celý úklid pro jeden CoC tag
# --------------------------------------------------------
async def _cleanup_for_tag(bot: discord.Client, guild: discord.Guild, tag: str):
    # import až tady → vyhneme se cyklickému importu
    from database import get_all_links, remove_coc_link

    links = get_all_links()            # {discord_id: (coc_tag, coc_name)}
    discord_id: Optional[int] = None
    for d_id, (coc_tag, _) in links.items():
        if coc_tag.upper() == tag:
            discord_id = d_id
            break

    if discord_id is None:
        return  # nikdo na serveru k tomuto tagu – nic víc neděláme

    # 1) smaž propojení v DB
    remove_coc_link(str(discord_id))

    # 2) pokus se najít člena na serveru
    member = guild.get_member(discord_id)
    if member:
        try:
            # odeber všechny role kromě @everyone
            roles_to_remove = [r for r in member.roles if r != guild.default_role]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Odešel z CoC klanu")

            # přejmenuj (ignoruj chybu oprávnění)
            try:
                await member.edit(nick="Odešel z klanu", reason="Odešel z CoC klanu")
            except discord.Forbidden:
                pass
        except discord.Forbidden:
            print(f"[member_tracker] ⚠️ Nemám oprávnění upravit uživatele {discord_id}")

    # 3) log do kanálu
    channel = guild.get_channel(1365768783083339878)
    if channel:
        # vybereme hezké jméno / mention
        name_or_mention = member.mention if member else f"<@{discord_id}>"

        embed = discord.Embed(
            title=f"👋 Díky, že jsi s námi byl, {name_or_mention}!",
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

    print(f"[member_tracker] Dokončen úklid pro tag {tag} / {discord_id}")


# --------------------------------------------------------
# veřejný worker – vytáhne tag z fronty a zpracuje
# --------------------------------------------------------
async def clan_departure_worker(bot: discord.Client):
    """Běží v samostatné corutině – startuje jej scheduler."""
    await bot.wait_until_ready()
    guild = getattr(bot, "guild_object", None)
    if guild is None:
        print("[member_tracker] ❌ bot.guild_object není nastavené, worker se ukončí")
        return

    print("[member_tracker] 👟 Clan-departure worker spuštěn")
    while not bot.is_closed():
        tag = await _leave_queue.get()
        try:
            await _cleanup_for_tag(bot, guild, tag)
        except Exception as e:
            print(f"[member_tracker] ⚠️ Chyba při úklidu pro {tag}: {e}")
        _leave_queue.task_done()