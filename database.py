import asyncio
import os
import sqlite3
from datetime import datetime, timedelta

import discord
from discord.ui import View, Button

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
                    reason TEXT,
                    notified_at TEXT
                )
            ''')
            conn.commit()
            print("✅ [database] Databáze a tabulky vytvořeny.")
    except Exception as e:
        print(f"❌ [database] Chyba při vytváření databáze: {e}")

# === Uloží nebo aktualizuje hráče ===
def update_or_create_members(data: list[dict], bot=None):
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

                # Spusť úklid jen pokud je `bot` k dispozici
                if bot:
                    from member_tracker import cleanup_after_coc_departure
                    asyncio.create_task(cleanup_after_coc_departure(bot, tag))

    except Exception as e:
        print(f"❌ [database] Chyba při zápisu do databáze: {e}")

    conn.close()

# === Hlavní řídící funkce pro práci s databází ===
def process_clan_data(data: list[dict], bot=None):
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

    update_or_create_members(data, bot=bot)

def get_all_links():
    """
    Vrátí záznam propojení mezi Discord ID a CoC účtem ve formátu:
    {discord_id: (coc_tag, coc_name)}

    Returns:
        dict: Slovník s propojeními, nebo prázdný slovník při chybě
    """
    result = {}
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row  # Pro přístup přes názvy sloupců
            cursor = conn.cursor()

            # Získání všech propojení (přidán discord_id)
            cursor.execute("""
                SELECT discord_name, coc_tag, coc_name 
                FROM coc_discord_links
            """)

            for row in cursor.fetchall():
                result[int(row['discord_name'])] = (row['coc_tag'], row['coc_name'])


    except sqlite3.Error as e:
        print(f"❌ [DATABASE] Chyba při čtení propojení: {e}")

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

# === Funkce pro výpis varování ===
def fetch_warnings():
    """Vrátí list[(tag, date_time, reason)] seřazený jak je v DB."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT coc_tag, date_time, reason FROM clan_warnings")
        return c.fetchall()

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
class WarningReviewView(View):
    def __init__(self, coc_tag: str, coc_name: str, date_time: str, reason: str):
        super().__init__(timeout=None)
        self.coc_tag = coc_tag
        self.member_name = coc_name
        self.date_time = date_time
        self.reason = reason

    @discord.ui.button(label="✅ Potvrdit", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        try:
            # Získání jména z clan_members
            member_name = None
            all_members = get_all_members()
            for member in all_members:
                if member["tag"].upper() == self.coc_tag.upper():
                    member_name = member["name"]
                    break

            # Uložení varování
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO clan_warnings (coc_tag, date_time, reason, notified_at)
                    VALUES (?, ?, ?, NULL)
                """, (self.coc_tag, self.date_time, self.reason))
                conn.commit()

            await interaction.message.delete()

            # Sestav základní zprávu
            tag_line = f"**{self.coc_tag}**"
            if self.member_name:
                tag_line += f" ({self.member_name})"

            msg = (
                f"✅ {interaction.user.mention} potvrdil varování pro {tag_line}\n"
                f"📆 {self.date_time}\n"
                f"📝 {self.reason}"
            )

            # Použij get_all_links() místo SQL dotazu
            all_links = get_all_links()
            for discord_id, (tag, _) in all_links.items():
                if tag.upper() == self.coc_tag.upper():
                    user = await interaction.client.fetch_user(discord_id)
                    if user:
                        try:
                            await user.send(
                                f"⚠️ Dostal jsi varování ⚠️.\n"
                                f"👤 Clash of Clans tag: `{self.coc_tag}` ({self.member_name})\n"
                                f"📆 {self.date_time}\n"
                                f"📝 Důvod: {self.reason}"
                            )
                            msg += "\n📩 Hráč je na Discordu, DM zpráva byla odeslána."
                        except Exception as dm_error:
                            msg += "\n⚠️ Nepodařilo se odeslat DM zprávu hráči."
                            print(f"⚠️ [confirm] DM error: {dm_error}")
                    break  # už jsme našli odpovídající tag

            # Pošleme log zprávu
            log_channel = interaction.channel
            await log_channel.send(msg)

            print(
                f"✅ [review] {interaction.user.name} ({interaction.user.id}) potvrdil varování: {self.coc_tag} – {self.reason}"
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Chyba při ukládání varování: {e}", ephemeral=True
            )
            print(f"❌ [review] Chyba při potvrzení varování {self.coc_tag}: {e}")

    @discord.ui.button(label="❌ Zrušit", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: Button):
        await interaction.message.delete()

        log_channel = interaction.channel
        await log_channel.send(
            f"❌ {interaction.user.mention} zamítl varování pro **{self.coc_tag}**\n"
            f"📆 {self.date_time}\n📝 {self.reason}"
        )

        print(
            f"❌ [review] {interaction.user.name} ({interaction.user.id}) zamítl varování: {self.coc_tag} – {self.reason}")

# === Upozornění při 3+ varováních a oznámení na Discord ===
async def notify_warnings_exceed(bot: discord.Client):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT coc_tag, COUNT(*) FROM clan_warnings GROUP BY coc_tag HAVING COUNT(*) >= 3")
            tags = c.fetchall()

            for tag, count in tags:
                # Zjisti poslední notified_at
                c.execute("SELECT MAX(notified_at) FROM clan_warnings WHERE coc_tag = ?", (tag,))
                last_notified = c.fetchone()[0]
                recent_warnings = []

                if last_notified:
                    try:
                        last_dt = datetime.strptime(last_notified, "%d/%m/%Y %H:%M")
                        c.execute("SELECT date_time, reason FROM clan_warnings WHERE coc_tag = ?", (tag,))
                        all = c.fetchall()
                        recent_warnings = [
                            (dt, reason) for (dt, reason) in all
                            if datetime.strptime(dt, "%d/%m/%Y %H:%M") > last_dt
                        ]
                        if not recent_warnings:
                            continue  # nic nového
                    except Exception as e:
                        print(f"⚠️ [notify] Chyba při porovnávání času pro {tag}: {e}")
                        continue
                else:
                    # pokud žádný notified_at ještě nikdy nebyl
                    c.execute("SELECT date_time, reason FROM clan_warnings WHERE coc_tag = ?", (tag,))
                    recent_warnings = c.fetchall()

                # načti jméno
                c.execute("SELECT coc_name, discord_name FROM coc_discord_links WHERE coc_tag = ?", (tag,))
                result = c.fetchone()
                if result:
                    coc_name = result[0]
                    discord_mention = f"<@{result[1]}>" if result[1] else coc_name
                else:
                    c.execute("SELECT name FROM clan_members WHERE tag = ?", (tag,))
                    name_row = c.fetchone()
                    coc_name = name_row[0] if name_row else "Neznámý hráč"
                    discord_mention = f"@{coc_name}"

                channel = bot.get_channel(1371105995270393867)
                if channel:
                    msg = (
                            f"<@317724566426222592>\n"
                            f"**{tag}**\n"
                            f"{discord_mention}\n"
                            + "\n".join([f"{i + 1}. {dt} – {reason}" for i, (dt, reason) in enumerate(recent_warnings)])
                    )
                    await channel.send(msg)
                    print(f"📣 [notify] Nová notifikace pro {tag} – {len(recent_warnings)} nových varování.")

                    now = datetime.now().strftime("%d/%m/%Y %H:%M")
                    c.execute("UPDATE clan_warnings SET notified_at = ? WHERE coc_tag = ?", (now, tag))
                    conn.commit()

    except Exception as e:
        print(f"❌ [notify] Chyba při notifikaci o vícenásobných varováních: {e}")

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
            msg = f"{coc_tag}\n@{name}\n{date_time}\n{reason}"
            view = WarningReviewView(coc_tag, name, date_time, reason)
            await channel.send(msg, view=view)
            print(f"📣 [notify] Návrh na varování odeslán pro {coc_tag}.")
    except Exception as e:
        print(f"❌ [notify] Chyba při posílání jednoho varování: {e}")