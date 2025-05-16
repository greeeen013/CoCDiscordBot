import sqlite3
from datetime import datetime, timezone

import discord
from discord.ext import commands

from database import DB_PATH, remove_coc_link   # reuse existující logiku

# kanál, kam se loguje odchod + smazání propojení
LOG_CHANNEL_ID = 1371089891621998652


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
