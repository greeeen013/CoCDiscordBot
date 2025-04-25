import os
import json
import sqlite3

# === Cesta k souboru databáze ===
DB_PATH = "coc_data_info.sqlite3"

# === Pole, která budeme ukládat a sledovat pro změny ===
TRACKED_FIELDS = [
    "tag", "name", "role", "townHallLevel",
    "league", "trophies", "builderBaseTrophies",
    "clanRank", "previousClanRank",
    "donations", "donationsReceived", "builderBaseLeague"
]

IGNORED_FOR_CHANGES = ["donations", "donationsReceived"]

# === Funkce pro kontrolu existence databáze ===
def database_exists() -> bool:
    """Zkontroluje, zda existuje soubor databáze."""
    return os.path.exists(DB_PATH)

# === Funkce pro vytvoření nové databáze ===
def create_database():
    """Vytvoří novou SQLite databázi s tabulkou clan_members."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS clan_members (
                    tag TEXT PRIMARY KEY,
                    name TEXT,
                    role TEXT,
                    townHallLevel INTEGER,
                    league TEXT,
                    trophies INTEGER,
                    builderBaseTrophies INTEGER,
                    clanRank INTEGER,
                    previousClanRank INTEGER,
                    donations INTEGER,
                    donationsReceived INTEGER,
                    builderBaseLeague TEXT
                )
            ''')
            conn.commit()
            print("✅ Databáze vytvořena.")
    except Exception as e:
        print(f"❌ Chyba při vytváření databáze: {e}")

# === Uloží nebo aktualizuje hráče ===
def update_or_create_members(data: list[dict]):
    """
    Pro každý záznam člena:
    - Pokud ještě neexistuje v databázi, přidá ho
    - Pokud existuje, porovná změny a případně aktualizuje
    - Hlásí změny, kromě těch, které jsou ignorované
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # Načtení všech existujících tagů před zpracováním
            c.execute("SELECT tag FROM clan_members")
            existing_tags = {row[0] for row in c.fetchall()}
            incoming_tags = set()

            for member in data:
                try:
                    # Předzpracování hodnot a ošetření chybějících polí
                    values = {
                        "tag": member.get("tag"),
                        "name": member.get("name"),
                        "role": member.get("role"),
                        "townHallLevel": member.get("townHallLevel"),
                        "league": member.get("league", {}).get("name", ""),
                        "trophies": member.get("trophies"),
                        "builderBaseTrophies": member.get("builderBaseTrophies"),
                        "clanRank": member.get("clanRank"),
                        "previousClanRank": member.get("previousClanRank"),
                        "donations": member.get("donations", 0),
                        "donationsReceived": member.get("donationsReceived", 0),
                        "builderBaseLeague": member.get("builderBaseLeague", {}).get("name", "")
                    }

                    tag = values["tag"]
                    incoming_tags.add(tag)

                    # Získání předchozích dat
                    c.execute("SELECT * FROM clan_members WHERE tag = ?", (tag,))
                    existing = c.fetchone()

                    if not existing:
                        # Nový záznam
                        c.execute("""
                            INSERT INTO clan_members VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, tuple(values.values()))
                        print(f"🆕 Přidán nový člen: {values['name']} ({tag})")
                    else:
                        # Porovnání hodnot a aktualizace
                        changes = []
                        for i, key in enumerate(TRACKED_FIELDS):
                            if key in IGNORED_FOR_CHANGES:
                                continue
                            old_val = existing[i]
                            new_val = values[key]
                            if str(old_val) != str(new_val):
                                changes.append((key, old_val, new_val))

                        if changes:
                            c.execute("""
                                UPDATE clan_members SET
                                    name = ?, role = ?, townHallLevel = ?, league = ?,
                                    trophies = ?, builderBaseTrophies = ?, clanRank = ?, previousClanRank = ?,
                                    donations = ?, donationsReceived = ?, builderBaseLeague = ?
                                WHERE tag = ?
                            """, (
                                values["name"], values["role"], values["townHallLevel"], values["league"],
                                values["trophies"], values["builderBaseTrophies"], values["clanRank"], values["previousClanRank"],
                                values["donations"], values["donationsReceived"], values["builderBaseLeague"], tag
                            ))
                            print(f"♻️ Změny u hráče {values['name']} ({tag}):")
                            for change in changes:
                                print(f"   - {change[0]} změna: {change[1]} → {change[2]}")
                except Exception as member_error:
                    print(f"❌ Chyba při zpracování člena: {member_error}")

            # Odstranění hráčů, kteří již nejsou v klanu
            tags_to_remove = existing_tags - incoming_tags
            for tag in tags_to_remove:
                c.execute("DELETE FROM clan_members WHERE tag = ?", (tag,))
                print(f"🗑️ Odebrán hráč s tagem {tag} – již není v klanu.")

    except Exception as e:
        print(f"❌ Chyba při zápisu do databáze: {e}")

# === Hlavní řídící funkce pro práci s databází ===
def process_clan_data(data: list[dict]):
    """
    Univerzální funkce pro zpracování dat z API:
    - Zkontroluje, zda existuje databáze
    - Pokud ne, vytvoří ji
    - Pak provede aktualizace nebo zápis hráčů
    """
    if not isinstance(data, list):
        print("❌ Data nejsou ve správném formátu: očekáván seznam hráčů.")
        return

    if not database_exists():
        print("📁 Databáze neexistuje, bude vytvořena...")
        create_database()

    update_or_create_members(data)