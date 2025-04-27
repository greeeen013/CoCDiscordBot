import os
import sqlite3

# === Cesta k souboru databáze ===
DB_PATH = "coc_data_info.sqlite3"

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
    """Vytvoří novou SQLite databázi s tabulkami clan_members a coc_links."""
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
            conn.commit()
            conn.close()
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
            conn.close()
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