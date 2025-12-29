import discord
import asyncio

from database import get_all_links, get_all_members
from role_giver import update_roles

from constants import (
    VERIFICATION_CHANNEL_ID,
    VERIFICATION_ROLE_ID,
    WELCOME_CHANNEL_ID,
    RULES_CHANNEL_ID,
    GENERAL_CHANNEL_ID
)

# Uchování informací o ověřování
verification_tasks = {}

EQUIPMENT_TO_HERO = {
    "Barbarian Puppet": "Barbarian King",
    "Snake Bracelet": "Barbarian King",
    "Giant Gauntlet": "Barbarian King",
    "Spiky Ball": "Barbarian King",
    "Rage Vial": "Barbarian King",
    "Earthquake Boots": "Barbarian King",
    "Vampstache": "Barbarian King",

    "Archer Puppet": "Archer Queen",
    "Action Figure": "Archer Queen",
    "Giant Arrow": "Archer Queen",
    "Magic Mirror": "Archer Queen",
    "Invisibility Vial": "Archer Queen",
    "Healer Puppet": "Archer Queen",
    "Frozen Arrow": "Archer Queen",

    "Henchmen Puppet": "Minion Prince",
    "Metal Pants": "Minion Prince",
    "Dark Orb": "Minion Prince",
    "Noble Iron": "Minion Prince",

    "Life Gem": "Grand Warden",
    "Lavaloon Puppet": "Grand Warden",
    "Fireball": "Grand Warden",
    "Eternal Tome": "Grand Warden",
    "Healing Tome": "Grand Warden",
    "Rage Gem": "Grand Warden",

    "Royale Gem": "Royal Champion",
    "Hog Rider Puppet": "Royal Champion",
    "Electro Boots": "Royal Champion",
    "Seeking Shield": "Royal Champion",
    "Haste Vial": "Royal Champion",
    "Rocket Spear": "Royal Champion"
}


async def start_verification_permission(interaction, player, config):
    """
    Odebere práva na čtení v hlavním kanálu a vytvoří privátní místnost pro ověřování.
    """
    guild = interaction.guild
    author = interaction.user

    # Najdeme verifikační roli
    verification_role = guild.get_role(VERIFICATION_ROLE_ID)
    if not verification_role:
        print("❌ Verifikační role nebyla nalezena!")
        return

    # Přidáme uživateli verifikační roli
    try:
        await author.add_roles(verification_role)
        print(f"✅ Uživateli {author.display_name} byla přidána verifikační role")
    except Exception as e:
        print(f"❌ Chyba při přidávání role: {e}")
        return

    overwrites = { # Vytvoření nové místnosti (textového kanálu)
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        author: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    new_channel = await guild.create_text_channel(f"verifikace-{player['name']}", overwrites=overwrites)
    print(f"✅ Vytvořena verifikační místnost: {new_channel.name}")

    await welcome_message(new_channel, player, author)  # Spustíme správu ověřování
    start_verification_checker(interaction.client, player["tag"], author, new_channel, config)

async def welcome_message(channel, player, author):
    """
    Pošle úvodní zprávu do nové místnosti.
    """
    await channel.send(f"👋 Ahoj <@{author.id}>! Připrav se na ověření tvého účtu. Za chvíli zahájíme kontrolu.")

def start_verification_checker(bot, player_tag, user, verification_channel, config):
    from scheduler import verification_check_loop
    verification_tasks[user.id] = bot.loop.create_task(
        verification_check_loop(bot, player_tag, user, verification_channel, config)
    )


async def end_verification(user, verification_channel):
    """
    Bezpečně ukončí verifikaci a smaže kanál
    """
    if not verification_channel:
        print(f"❌ [end_verification] Kanál pro {user} již neexistuje")
        return

    try:
        # Odebrání verifikační role
        verification_role = verification_channel.guild.get_role(VERIFICATION_ROLE_ID)
        if verification_role:
            await user.remove_roles(verification_role)
            print(f"✅ [end_verification] Uživateli {user} byla odebrána verifikační role")
        else:
            print(f"❌ [end_verification] Verifikační role nebyla nalezena")

        # Oznámení před smazáním
        await verification_channel.send("🗑️ Tento kanál bude smazán za 5 sekund...")
        await asyncio.sleep(5)

        # Kontrola existence kanálu před smazáním
        if verification_channel in user.guild.channels:
            await verification_channel.delete()
            print(f"✅ [end_verification] Kanál pro {user} úspěšně smazán")
        else:
            print(f"⚠️ [end_verification] Kanál pro {user} již byl smazán")

    except discord.Forbidden:
        print(f"❌ [end_verification] Nemám práva smazat kanál nebo odebrat roli pro {user}")
    except discord.NotFound:
        print(f"⚠️ [end_verification] Kanál pro {user} nebo role již neexistuje")
    except Exception as e:
        print(f"❌ [end_verification] Neočekávaná chyba u {user}: {e}")


async def succesful_verification(bot, user, verification_channel, selected_item, coc_name, coc_tag):
    """
    Oznámí úspěšné ověření a smaže verifikační místnost.
    """
    from scheduler import resume_hourly_update

    guild = verification_channel.guild

    await verification_channel.send(f"✅ Detekováno nasazení vybavení **{selected_item}**. Ověření dokončeno!")

    # Nastavení přezdívky podle jména v klanu
    try:
        await user.edit(nick=coc_name)
        print(f"✅ [verification] Přezdívka uživatele {user} nastavena na {coc_name}.")
        await verification_channel.send(f"✅ přidána přezdívka  **{user}** nastavena na **{coc_name}**.")
    except Exception as e:
        print(f"❌ [verification] Chyba při nastavování přezdívky uživatele {user}: {e}")
        await verification_channel.send(f"❌ chyba při nastavování přezdívky, někdo se na to brzo podívá.")

    try:
        # Zapsání uživatele do databáze
        from database import add_coc_link
        add_coc_link(user.id, coc_tag, coc_name)
        print(f"✅ [verification] Uživatel {user} zapsán do databáze coc_discord_links.")
    except Exception as e:
        print(f"❌ [verification] Chyba při zápisu do databáze: {e}")
        await verification_channel.send(f"❌ chyba při zápisu do databáze někdo se na to brzo podívá.")


    await end_verification(user, verification_channel)  # Zavolá funkci pro ukončení ověření
    print(f"✅ [verification] posíám welcome_on_server_message pro {user}...")
    await welcome_on_server_message(bot, user)  # Pošle uvítací zprávu do kanálu

    await update_role_when_new_member(bot, user)
    print(f"✅ [verification] Hráč {user} úspěšně ověřen - {selected_item} nasazen. ✅")
    resume_hourly_update()  # Obnoví hodinový update

async def welcome_on_server_message(bot, user):
    """
    Pošle úvodní zprávu do uvítací místnosti pomocí embed zprávy.
    """

    welcome_channel_id = WELCOME_CHANNEL_ID # ID uvítací místnosti
    rules_channel_id = RULES_CHANNEL_ID # ID kanálu s pravidly
    general_channel_id = GENERAL_CHANNEL_ID # ID obecné místnosti

    channel = bot.get_channel(welcome_channel_id)

    if not channel:
        print(f"❌ [welcome_on_server_message] Kanál s ID {welcome_channel_id} nebyl nalezen.")
        return

    embed = discord.Embed(
        title="👋 Vítej mezi ověřenými serveru našeho klanu Czech Heroes!",
        description=f"{user.mention}, vítej mezi námi!",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="📌 Co dál?",
        value=(
            f"🔍 Seznam se s pravidly v: <#{rules_channel_id}>\n"
            f"💬 Přidej se do konverzace v obecných chatech: <#{general_channel_id}>\n"
            "🎯 Prozkoumej všechny mopžnosti serveru\n"
            "👥 Poznej ostatní hráče v komunitě"
        ),
        inline=False
    )

    embed.set_footer(text="⚔️ Czech Heroes | Přejme příjemnou zábavu a úspěšné útoky!")

    await channel.send(embed=embed)
    print(f"ℹ️ [verification] Do welcome kanálu byla odeslaná welcome zpráva. pro {user}")


async def update_role_when_new_member(bot, user):
    """
    Aktualizuje role novému členovi (po ověření).
    """

    print(f"🔄 [verification] Updatím role pro uživatele {user}...")
    guild = bot.get_guild(bot.guild_object.id)  # Správně získáme guildu přes instanci bota
    links = get_all_links()
    members = get_all_members()
    await update_roles(guild, links, members)

async def process_verification(bot, player_data, user, verification_channel, selected_item=None):
    import random # Import random pro generování náhodného čísla aby to našlo true random equipment

    if not player_data:
        await verification_channel.send("❌ Nepodařilo se načíst data hráče.")
        print(f"❌ [verification] Chyba: hráč {user} - data None.")
        return None

    heroes = player_data.get("heroes", [])
    hero_equipment = player_data.get("heroEquipment", [])

    if not heroes or not hero_equipment:
        await verification_channel.send("❌ Nebylo možné najít vybavení hrdinů.")
        print(f"❌ [verification] Chyba: hráč {user} - chybí heroes nebo heroEquipment.")
        return None

    monitored_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince"]
    equipped_items = set()

    for hero in heroes:
        if hero.get("name") in monitored_heroes:
            for equip in hero.get("equipment", []):
                equipped_items.add(equip.get("name"))


    if selected_item is None:
        print(f"🔍 [verification] První pull pro hráče {user} - hledám vybavení...")
        unequipped_items = []
        for item in hero_equipment:
            name = item.get("name")
            level = item.get("level", 0)

            # Přidáme podmínku že vybavení musí být v našem seznamu
            if name not in EQUIPMENT_TO_HERO:
                continue  # Přeskočíme, pokud vybavení není známé

            if name not in equipped_items and level > 1:
                unequipped_items.append(name)

        if not unequipped_items:
            await verification_channel.send("❌ Nenašel jsem žádné dostupné vybavení k ověření.")
            print(f"❌ [verification] Hráč {user} - žádné vhodné vybavení.")
            return None

        chosen_item = random.choice(unequipped_items)

        print(f"🎯 [verification Debug] Hledám nasazení itemu: {chosen_item}")
        print(f"🎯 [verification Debug] Aktuálně nasazené předměty: {equipped_items}")

        embed = discord.Embed(
            title="🛡️ Ověření účtu - Nasaď vybavení",
            description="Abychom tě mohli ověřit, postupuj podle následujících kroků:",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🎯 Vybrané vybavení k nasazení:",
            value=f"🔥  **{chosen_item}**  🔥 na hrdinu **{EQUIPMENT_TO_HERO[chosen_item]}**",
            inline=False
        )

        embed.add_field(
            name="📜 Instrukce:",
            value=(
                "• **1.** Přihlas se do Clash of Clans\n"
                "• **2.** Nasaď vybavení uvedené výše\n"
                "• **3.** **Stačí jen equipnout** - nemusíš odehrát žádný útok ani jiné akce!\n"
                "• **4.** Bot každých 5 minuty kontroluje změny\n"
                "• **5.** Jakmile zjistíme změnu, ověření proběhne automaticky a bot tě přivítá ✅\n"
                "• **6.** Takže nemusíš se vracet zpátky a něco potvrzovat ✅\n"
                "• **7.** Pokud nestihneš do **20 minut**, ověření expiruje ❌\n"
                "• ps. nezapomeň si vybavení vrátit po verifikaci 😅\n"

            ),
            inline=False
        )

        embed.set_footer(text="⚠️ Změnil jsi, ale nefunguje? Klid - aktualizace dat ze serveru Clash of Clans trvá ~5-6 minuty. Při další kontrole to bude cajk 😉")

        await verification_channel.send(embed=embed)


        print(f"✅ [Verification] Hráč {user} má nasadit: {chosen_item}")
        return chosen_item

    else:
        print(f"🔄 [verification] Kontrola změny pro hráče {user}...")
        if selected_item in equipped_items:
            await succesful_verification(bot, user, verification_channel, selected_item, player_data["name"], player_data["tag"])
            return "verified"
        else:
            await verification_channel.send(f"⏳ Vybavení **{selected_item}** zatím není nasazeno. Další kontrola za 5 minuty...")
            print(f"⏳ [verification] Hráč {user} ještě nemá nasazené {selected_item}.")
            return None

