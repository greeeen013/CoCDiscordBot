import os
import sqlite3
from datetime import datetime

import discord

# === Cesta k souboru databáze ===
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coc_data_info.sqlite3")

# === Pole, která budeme ukládat a sledovat pro změny ===
TRACKED_FIELDS = [
    "name", "tag", "role", "townHallLevel",
    "league", "trophies", "builderBaseLeague", "builderBaseTrophies",
    "clanRank", "previousClanRank",
    "donations", "donationsReceived"
]

IGNORED_FOR_CHANGES = ["donations", "donationsReceived"]

# === Funkce pro kontrolu existence databáze ===
def database_exists() -> bool:
    """Zkontroluje, zda existuje soubor databáze."""
    return os.path.exists(DB_PATH)

# === Funkce pro vytvoření nové databáze ===
def create_database():
    """Vytvoří novou SQLite databázi s tabulkami clan_members, coc_links a clan_warnings."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS clan_members (
                    name TEXT,
                    tag TEXT PRIMARY KEY,
                    role TEXT,
                    townHallLevel INTEGER,
                    league TEXT,
                    trophies INTEGER,
                    builderBaseLeague TEXT,
                    builderBaseTrophies INTEGER,
                    clanRank INTEGER,
                    previousClanRank INTEGER,
                    donations INTEGER,
                    donationsReceived INTEGER
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS coc_discord_links (
                    discord_name TEXT PRIMARY KEY,
                    coc_tag TEXT,
                    coc_name TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS clan_warnings (
                    coc_tag TEXT,
                    date_time TEXT,
                    reason TEXT
                )
            ''')
            conn.commit()
            print("✅ [database] Databáze a tabulky vytvořeny.")
    except Exception as e:
        print(f"❌ [database] Chyba při vytváření databáze: {e}")

# === Uloží nebo aktualizuje hráče ===
def update_or_create_members(data: list[dict]):
    """
    Pro každý záznam člena:
    - Pokud ještě neexistuje v databázi, přidá ho
    - Pokud existuje, porovná změny a případně aktualizuje
    - Hlásí změny, kromě těch, které jsou ignorované
    - Odstraní členy, kteří už v klanu nejsou
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            c.execute("SELECT tag FROM clan_members")
            existing_tags = {row[0] for row in c.fetchall()}
            incoming_tags = set()

            for member in data:
                try:
                    values = {
                        "name": member.get("name"),
                        "tag": member.get("tag"),
                        "role": member.get("role"),
                        "townHallLevel": member.get("townHallLevel"),
                        "league": member.get("league", {}).get("name", ""),
                        "trophies": member.get("trophies"),
                        "builderBaseLeague": member.get("builderBaseLeague", {}).get("name", ""),
                        "builderBaseTrophies": member.get("builderBaseTrophies"),
                        "clanRank": member.get("clanRank"),
                        "previousClanRank": member.get("previousClanRank"),
                        "donations": member.get("donations", 0),
                        "donationsReceived": member.get("donationsReceived", 0)
                    }

                    tag = values["tag"]
                    incoming_tags.add(tag)

                    c.execute("SELECT * FROM clan_members WHERE tag = ?", (tag,))
                    existing = c.fetchone()

                    if not existing:
                        c.execute("""
                            INSERT INTO clan_members VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, tuple(values.values()))

                        # Krásné a detailní vypsání statistik
                        print(f"🆕 [database] Přidán nový člen: {values['name']} ({tag})")
                        print("📊 Statistiky:")
                        print(f" • 🏰 TownHall Level: {values.get('townHallLevel', 'N/A')}")
                        print(f" • 🏅 League: {values.get('league', 'N/A')}")
                        print(f" • 🏆 Trofeje: {values.get('trophies', 'N/A')}")
                        print(f" • 🔨 Builder Base Trofeje: {values.get('builderBaseTrophies', 'N/A')}")
                        print(f" • 🏆 Clan Rank: {values.get('clanRank', 'N/A')}")
                        print(f" • ⬆️ Previous Clan Rank: {values.get('previousClanRank', 'N/A')}")
                        print(f" • 🛠️ Builder Base League: {values.get('builderBaseLeague', 'N/A')}")
                        print(f" • 👑 Role v klanu: {values.get('role', 'N/A')}")
                    else:
                        changes = []
                        for i, key in enumerate(TRACKED_FIELDS):
                            if key in IGNORED_FOR_CHANGES:
                                continue
                            old_val = existing[i]
                            new_val = values[key]
                            if str(old_val) != str(new_val):
                                delta = ""
                                if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                                    delta = f" ({int(new_val) - int(old_val):+})"
                                changes.append((key, old_val, new_val, delta))

                        if changes:
                            c.execute("""
                                UPDATE clan_members SET
                                    name = ?, tag = ?, role = ?, townHallLevel = ?,
                                    league = ?, trophies = ?, builderBaseLeague = ?, builderBaseTrophies = ?,
                                    clanRank = ?, previousClanRank = ?, donations = ?, donationsReceived = ?
                                WHERE tag = ?
                            """, (
                                values["name"], values["tag"], values["role"], values["townHallLevel"],
                                values["league"], values["trophies"], values["builderBaseLeague"], values["builderBaseTrophies"],
                                values["clanRank"], values["previousClanRank"], values["donations"], values["donationsReceived"],
                                tag
                            ))
                            print(f"♻️ Změny u hráče {values['name']} ({tag}):")
                            for change in changes:
                                print(f"   - {change[0]} změna: {change[1]} → {change[2]}{change[3]}")
                except Exception as member_error:
                    print(f"❌ [database] Chyba při zpracování člena: {member_error}")

            tags_to_remove = existing_tags - incoming_tags
            for tag in tags_to_remove:
                c.execute("DELETE FROM clan_members WHERE tag = ?", (tag,))
                print(f"🗑️ [database] Odebrán hráč s tagem {tag} – již není v klanu.")

    except Exception as e:
        print(f"❌ [database] Chyba při zápisu do databáze: {e}")

    conn.close()

# === Hlavní řídící funkce pro práci s databází ===
def process_clan_data(data: list[dict]):
    """
    Univerzální funkce pro zpracování dat z API:
    - Zkontroluje, zda existuje databáze
    - Pokud ne, vytvoří ji
    - Pak provede aktualizace nebo zápis hráčů
    """
    if not isinstance(data, list):
        print("❌ [database] Data nejsou ve správném formátu: očekáván seznam hráčů.")
        return

    if not database_exists():
        print("📁 Databáze neexistuje, bude vytvořena...")
        create_database()

    update_or_create_members(data)

def get_all_links():
    """
    Vrátí záznam propojení mezi Discord ID a CoC účtem.
    """
    conn = sqlite3.connect("coc_data_info.sqlite3")
    cursor = conn.cursor()

    cursor.execute("SELECT discord_name, coc_tag, coc_name FROM coc_discord_links")
    rows = cursor.fetchall()

    conn.close()

    # Předěláme správně na formát {discord_id: (coc_tag, coc_name)}
    result = {}
    for discord_id, coc_tag, coc_name in rows:
        result[int(discord_id)] = (coc_tag, coc_name)

    return result

# === Přidání propojení mezi Discord jménem a CoC účtem ===
def add_coc_link(discord_name: str, coc_tag: str, coc_name: str):
    """
    Přidá propojení Discord uživatele a Clash of Clans účtu.
    vstup: discord_name, coc_tag, coc_name
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO coc_discord_links (discord_name, coc_tag, coc_name)
                VALUES (?, ?, ?)
            """, (discord_name, coc_tag, coc_name))
            conn.commit()
            print(f"✅ [database] Propojení uloženo pro {discord_name} → {coc_tag} ({coc_name})")
    except Exception as e:
        print(f"❌ [database] Chyba při ukládání propojení: {e}")

# === Odstranění propojení podle Discord jména ===
def remove_coc_link(discord_name: str):
    """
    Smaže záznam propojení podle Discord jména.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM coc_discord_links WHERE discord_name = ?", (discord_name,))
            conn.commit()
            conn.close()
            print(f"🗑️ [database] Propojení odstraněno pro Discord jméno: {discord_name}")
    except Exception as e:
        print(f"❌ [database] Chyba při odstraňování propojení: {e}")

def get_all_members():
    """
    Vrátí všechny hráče z tabulky clan_members jako seznam slovníků.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name, tag, role, townHallLevel, league, trophies, builderBaseTrophies, clanRank, previousClanRank, donations, donationsReceived, builderBaseLeague FROM clan_members")
    rows = cursor.fetchall()

    conn.close()

    members = []
    for row in rows:
        members.append({
            "name": row[0],
            "tag": row[1],
            "role": row[2],
            "townHallLevel": row[3],
            "league": row[4],
            "trophies": row[5],
            "builderBaseTrophies": row[6],
            "clanRank": row[7],
            "previousClanRank": row[8],
            "donations": row[9],
            "donationsReceived": row[10],
            "builderBaseLeague": row[11],
        })

    return members

# === Funkce pro přidání varování ===
# === Přidání varování ===
def add_warning(coc_tag: str, date_time: str = None, reason: str = "Bez udaného důvodu", bot: discord.Client = None):
    if date_time:
        try:
            datetime.strptime(date_time, "%d/%m/%Y %H:%M")
        except ValueError:
            print(f"⚠️ [warning] Neplatný formát času: {date_time} – očekáváno ve formátu DD/MM/YYYY HH:MM. Vygenerován automaticky.")
            date_time = datetime.now().strftime("%d/%m/%Y %H:%M")
    else:
        date_time = datetime.now().strftime("%d/%m/%Y %H:%M")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO clan_warnings (coc_tag, date_time, reason) VALUES (?, ?, ?)
            """, (coc_tag, date_time, reason))
            conn.commit()
            print(f"⚠️ [warning] Varování přidáno pro {coc_tag} – {reason} ({date_time})")

        # Pokud máme bot objekt, pošleme zprávu
        if bot:
            import asyncio
            asyncio.create_task(notify_single_warning(bot, coc_tag, date_time, reason))

    except Exception as e:
        print(f"❌ [database] Chyba při ukládání varování: {e}")

# === Funkce pro výpis varování ===
def list_warnings():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT coc_tag, date_time, reason FROM clan_warnings")
            rows = c.fetchall()

            if not rows:
                print("😊 [warnings] Nenalezeno žádné varování.")
                return

            print("\n=== 🔶 Seznam varování ===")
            for i, (tag, dt, reason) in enumerate(rows, 1):
                print(f"{i}. {tag} – {dt} – Důvod: {reason}")

    except Exception as e:
        print(f"❌ [database] Chyba při čtení varování: {e}")

# === Funkce pro odstranění varování ===
def remove_warning(coc_tag: str, date_time: str, reason: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                DELETE FROM clan_warnings WHERE coc_tag = ? AND date_time = ? AND reason = ?
            """, (coc_tag, date_time, reason))
            if c.rowcount > 0:
                print(f"🗑️ [warning] Varování odstraněno: {coc_tag} – {date_time} – {reason}")
            else:
                print(f"❌ [warning] Varování nenalezeno nebo neodpovídá parametrům.")
            conn.commit()
    except Exception as e:
        print(f"❌ [database] Chyba při mazání varování: {e}")

async def cleanup_old_warnings():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT coc_tag, date_time, reason FROM clan_warnings")
            rows = c.fetchall()

            for tag, date_time, reason in rows:
                try:
                    dt = datetime.strptime(date_time, "%d/%m/%Y %H:%M")
                    if (datetime.now() - dt).days > 14:
                        c.execute("DELETE FROM clan_warnings WHERE coc_tag = ? AND date_time = ? AND reason = ?", (tag, date_time, reason))
                        print(f"🧹 [cleanup] Odstraněno staré varování: {tag} – {date_time} – {reason}")
                except Exception as e:
                    print(f"❌ [cleanup] Chyba při parsování času: {date_time} – {e}")
            conn.commit()
    except Exception as e:
        print(f"❌ [cleanup] Chyba při čištění varování: {e}")

# === Poslání varování jako zprávu na Discord ===
async def send_warning_notification(bot: discord.Client, tag: str, name: str, warnings: list[tuple[str, str]]):
    try:
        channel = bot.get_channel(1371105995270393867)
        if channel:
            msg = (
                f"<@317724566426222592>\n"
                f"**{tag}**\n"
                f"@{name}\n"
                + "\n".join([f"{i+1}. {dt} – {reason}" for i, (dt, reason) in enumerate(warnings)])
            )
            await channel.send(msg)
            print(f"📣 [notify] Zpráva o hráči {tag} odeslána na Discord.")
    except Exception as e:
        print(f"❌ [notify] Chyba při odesílání zprávy na Discord: {e}")

# === Rychlé upozornění na nové varování ===
async def notify_single_warning(bot: discord.Client, coc_tag: str, date_time: str, reason: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM clan_members WHERE tag = ?", (coc_tag,))
            result = c.fetchone()
            name = result[0] if result else "Neznámý hráč"

        channel = bot.get_channel(1371105995270393867)
        if channel:
            msg = f"{coc_tag}\n{name}\n{date_time} – {reason}"
            await channel.send(msg)
            await notify_warnings_exceed(bot)
            print(f"📣 [notify] Nové varování nahlášeno pro {coc_tag}.")
    except Exception as e:
        print(f"❌ [notify] Chyba při posílání jednoho varování: {e}")
# === Upozornění při 3+ varováních a oznámení na Discord ===
# === Upozornění při 3+ varováních ===
async def notify_warnings_exceed(bot: discord.Client):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT coc_tag, COUNT(*) FROM clan_warnings GROUP BY coc_tag HAVING COUNT(*) >= 3")
            tags = c.fetchall()

            for tag, count in tags:
                # Získání údajů o hráči
                c.execute("SELECT coc_name, discord_name FROM coc_discord_links WHERE coc_tag = ?", (tag,))
                result = c.fetchone()
                coc_name = result[0] if result else "Neznámý hráč"
                discord_mention = f"<@{result[1]}>" if result and result[1] else coc_name

                # Načti všechna varování hráče
                c.execute("SELECT date_time, reason FROM clan_warnings WHERE coc_tag = ?", (tag,))
                warnings = c.fetchall()

                # Najdi cílový kanál
                channel = bot.get_channel(1371105995270393867)
                if channel:
                    msg = (
                        f"<@317724566426222592>\n"
                        f"**{tag}**\n"
                        f"{discord_mention}\n"
                        + "\n".join([f"{i + 1}. {dt} – {reason}" for i, (dt, reason) in enumerate(warnings)])
                    )
                    await channel.send(msg)
                    print(f"📣 [notify] Odeslána notifikace pro hráče {tag} se {count} varováními.")
    except Exception as e:
        print(f"❌ [notify] Chyba při notifikaci o vícenásobných varováních: {e}")