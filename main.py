from dotenv import load_dotenv
import os
from bot_commands import start_bot

def load_config():
    load_dotenv()
    return {
        "COC_API_KEY": os.getenv("COC_API_KEY"),
        "DISCORD_BOT_TOKEN": os.getenv("DISCORD_BOT_TOKEN"),
        "GUILD_ID": int(os.getenv("GUILD_ID")),
        "CLAN_TAG": os.getenv("CLAN_TAG")
    }

def main():
    config = load_config()
    start_bot(config)

if __name__ == "__main__":
    main()
