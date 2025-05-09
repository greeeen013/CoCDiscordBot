import asyncio

from api_handler import fetch_clan_members_list, fetch_player_data
from database import process_clan_data, get_all_links, get_all_members
from role_giver import update_roles
from api_handler import fetch_current_war, fetch_current_capital
from clan_war import ClanWarHandler
from clan_capital import ClanCapitalHandler


# === Stav pozastavení hodinového updatu ===
is_hourly_paused = False

# === Funkce pro hodinové tahání dat ===
async def hourly_clan_update(config: dict, bot):
    while True:
        if not is_hourly_paused:
            guild = bot.get_guild(config["GUILD_ID"])
            if guild is None:
                print(f"❌ [Scheduler] Guild s ID {config['GUILD_ID']} nebyl nalezen.")
                await asyncio.sleep(60)
                continue

            print("🔁 [Scheduler] Spouštím aktualizaci seznamu členů klanu...")
            data = await fetch_clan_members_list(config["CLAN_TAG"], config)
            if data:
                print(f"✅ [Scheduler] Načteno {len(data.get('items', []))} členů klanu.")
                process_clan_data(data.get("items", []))

            print("🔄 [Scheduler] Spouštím automatickou aktualizaci rolí...")
            links = get_all_links()
            members = get_all_members()
            await update_roles(guild, links, members)
            print("✅ [Scheduler] Aktualizace rolí dokončena.")

            # === WAR STATUS ===
            clan_war_handler = ClanWarHandler(bot, config)
            war_data = await fetch_current_war("#2QQ0PY9V8", config)
            if war_data:
                await clan_war_handler.process_war_data(war_data)

            # === CAPITAL STATUS ===
            clan_capital_handler = ClanCapitalHandler(bot, config)
            capital_data = await fetch_current_capital(config["CLAN_TAG"], config)
            if capital_data:
                await clan_capital_handler.process_capital_data(capital_data)

        else:
            print("⏸️ [Scheduler] Aktualizace seznamu klanu je momentálně pozastavena kvůli ověřování.")

        await asyncio.sleep(60*3)  # každých 15 minut

# === Funkce pro pozastavení hodinového updatu ===
def pause_hourly_update():
    """
    Nastaví příznak pro pozastavení hodinového updatu dat.
    """
    global is_hourly_paused
    is_hourly_paused = True
    print("⏸️ [scheduler] Hourly update byl pozastaven.")

# === Funkce pro obnovení hodinového updatu ===
def resume_hourly_update():
    """
    Vrátí zpět příznak, aby hourly update znovu běžel.
    """
    global is_hourly_paused
    is_hourly_paused = False
    print("▶️ [scheduler] Hourly update byl obnoven.")

# === Nová funkce pro verifikační smyčku ===
async def verification_check_loop(bot, player_tag, user, verification_channel, config):
    from verification import process_verification, end_verification

    print(f"🚀 [scheduler] Zahajuji ověřování hráče {user} s tagem {player_tag}.")

    pause_hourly_update()

    # === První pull ===
    player_data = await fetch_player_data(player_tag, config)
    print(f"📥 [scheduler] Načítám data hráče {player_tag}...")

    if not player_data:
        await verification_channel.send("❌ Chyba při načítání dat hráče.")
        print(f"❌ [scheduler] Chyba při fetchnutí dat pro {user}.")
        await end_verification(user, verification_channel)
        resume_hourly_update()
        return

    selected_item = await process_verification(bot, player_data, user, verification_channel)

    if not selected_item:
        print(f"❌ [scheduler] Nepodařilo se vybrat vybavení pro hráče {user}.")
        await end_verification(user, verification_channel)
        resume_hourly_update()
        return

    # === Další pull každé 2 minuty ===
    tries = 0
    while tries < 4:
        await asyncio.sleep(300)  # 5 minuty
        tries += 1

        print(f"🔄 [scheduler] zahajuji stahování data pro hráče {user}")
        player_data = await fetch_player_data(player_tag, config)

        print(f"🔄 [scheduler] Pokus {tries}/6 - ověřuji hráče {user}...")
        if player_data:
            print(f"🔄 [scheduler] volám funkci process_verification pro hráče {user}...")
            result = await process_verification(bot, player_data, user, verification_channel, selected_item)
            if result == "verified":
                print(f"🏁 [scheduler] Ověření hráče {user} dokončeno úspěšně.")
                await end_verification(user, verification_channel)
                resume_hourly_update()
                return
        else:
            print(f"❌ [scheduler] Chyba při načítání dat hráče {player_tag} - pokus {tries}/6.")
            await verification_channel.send("❌ Chyba při načítání dat hráče.")
            continue

    # Pokud po 6 pokusech (12 minut) se neověří
    # tak
    await end_verification(user, verification_channel) # zavolá funkci pro ukončení ověření
    await verification_channel.send("❌ Nepodařilo se ověřit během časového limitu. Zkus to prosím znovu.") # pošle zprávu do kanálu
    main_channel = verification_channel.guild.get_channel(1365437738467459265) # získá hlavní kanál
    await main_channel.set_permissions(user, overwrite=None)  # Vrátíme defaultní práva
    print(f"🗑️ [verification] {user} se neověřil takže místnost {verification_channel.name} po ukončené verifikaci byla smazána.") # vytiskne zprávu do konzole
    resume_hourly_update() # obnoví hodinový update

