from dotenv import load_dotenv
import os

from database import create_database, database_exists
from discord_bot import start_bot


def load_config():
    load_dotenv()

    try:
        return {
            "COC_API_KEY": os.getenv("COC_API_KEY"),
            "DISCORD_BOT_TOKEN": os.getenv("DISCORD_BOT_TOKEN"),
            "GUILD_ID": int(os.getenv("GUILD_ID")),
            "CLAN_TAG": os.getenv("CLAN_TAG")
        }
    except (TypeError, ValueError) as e:
        print(f"❌ Chyba v načítání konfigurace: {e}")
        exit(1)

def main():
    if not database_exists():
        create_database()


    config = load_config()
    start_bot(config)

if __name__ == "__main__":
    main()
