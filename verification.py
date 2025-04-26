import discord
import asyncio



# Konstanty
VERIFICATION_CHANNEL_ID = 1365437738467459265

# Uchování informací o ověřování
verification_tasks = {}

async def start_verification_permission(interaction, player, config):
    """
    Odebere práva na čtení v hlavním kanálu a vytvoří privátní místnost pro ověřování.
    """
    guild = interaction.guild
    author = interaction.user

    main_channel = guild.get_channel(VERIFICATION_CHANNEL_ID) # Najdeme hlavní verifikační kanál

    await main_channel.set_permissions(author, read_messages=False) # Odebrání práva číst zprávy v hlavním kanálu

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
    Obnoví práva v hlavním kanálu a smaže verifikační místnost.
    """
    guild = verification_channel.guild
    main_channel = guild.get_channel(VERIFICATION_CHANNEL_ID)

    await verification_channel.send("❌ Nepodařilo se ověřit během časového limitu. Zkus to prosím znovu.")
    await asyncio.sleep(5)
    await verification_channel.send("🗑️ místnost bude automaticky smazána za 3 sekundy...")
    await main_channel.set_permissions(user, overwrite=None)  # Vrátíme defaultní práva
    await verification_channel.delete()
    print(f"🗑️ [verification] {user} se neověřil takže místnost {verification_channel.name} po ukončené verifikaci byla smazána.")

async def succesful_verification(user, verification_channel, selected_item, coc_name):
    """
    Oznámí úspěšné ověření a smaže verifikační místnost.
    """
    guild = verification_channel.guild
    role = guild.get_role(1365768439473373235)  # Získání role podle ID

    await verification_channel.send(f"✅ Detekováno nasazení vybavení **{selected_item}**. Ověření dokončeno!")
    # Přidání role uživateli
    if role:
        await user.add_roles(role)
        print(f"✅ [verification] Role {role.name} byla přidána uživateli {user}.")
        await verification_channel.send(f"✅ přidána role **{role.name}**.")

    # Nastavení přezdívky podle jména v klanu
    try:
        await user.edit(nick=coc_name)
        print(f"✅ [verification] Přezdívka uživatele {user} nastavena na {coc_name}.")
        await verification_channel.send(f"✅ přidána přezdívka  **{user}** nastavena na **{coc_name}**.")
    except Exception as e:
        print(f"❌ [verification] Chyba při nastavování přezdívky uživatele {user}: {e}")
        await verification_channel.send(f"❌ chyba při nastavování přezdívky někdo se na to brzo podívá.")


    print(f"✅ [verification] Hráč {user} úspěšně ověřen - {selected_item} nasazen.")

async def welcome_on_server_message(player):
    """
    Pošle úvodní zprávu do nové místnosti.
    """
    verification_channel= 1365768783083339878
    await verification_channel.send(f"👋 Ahoj @{player}! Vítej na serveru")

async def process_verification(player_data, user, verification_channel, selected_item=None):
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

            if name not in equipped_items and level > 1:
                unequipped_items.append(name)

        if not unequipped_items:
            await verification_channel.send("❌ Nenašel jsem žádné dostupné vybavení k ověření.")
            print(f"❌ [verification] Hráč {user} - žádné vhodné vybavení.")
            return None

        chosen_item = unequipped_items[0]

        print(f"🎯 [verification Debug] Hledám nasazení itemu: {chosen_item}")
        print(f"🎯 [verification Debug] Aktuálně nasazené předměty: {equipped_items}")

        embed = discord.Embed(
            title="🛡️ Ověření účtu - Nasaď vybavení",
            description="Abychom tě mohli ověřit, postupuj podle následujících kroků:",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🎯 Vybrané vybavení k nasazení:",
            value=f"     **{chosen_item}**",
            inline=False
        )

        embed.add_field(
            name="📜 Instrukce:",
            value=(
                "• **1.** Přihlas se do Clash of Clans\n"
                "• **2.** Nasaď vybavení uvedené výše\n"
                "• **3.** **Stačí jen equipnout** - nemusíš odehrát žádný útok ani jiné akce!\n"
                "• **4.** Bot každé 3 minuty kontroluje změny\n"
                "• **5.** Jakmile zjistíme změnu, ověření bude automaticky dokončeno a bot tě přivítá ✅\n"
                "• **6.** Pokud nestihneš do **15 minut**, ověření expiruje ❌"
            ),
            inline=False
        )

        embed.set_footer(text="⚠️ Změnil jsi, ale nefunguje? Klid - aktualizace dat ze serveru Clash of Clans trvá ~3 minuty. Při další kontrole to bude cajk 😉")

        await verification_channel.send(embed=embed)


        print(f"✅ [Verification] Hráč {user} má nasadit: {chosen_item}")
        return chosen_item

    else:
        print(f"🔄 [verification] Kontrola změny pro hráče {user}...")
        if selected_item in equipped_items:
            succesful_verification(user, verification_channel, selected_item, player_data["name"])
            return "verified"
        else:
            await verification_channel.send(f"⏳ Vybavení **{selected_item}** zatím není nasazeno. Další kontrola za 3 minuty...")
            print(f"⏳ [verification] Hráč {user} ještě nemá nasazené {selected_item}.")
            return None

