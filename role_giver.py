import discord

from constants import ROLE_VERIFIED

# Role ID pro Townhall levely
TOWNHALL_ROLES = {
    17: 1365984171054469180,
    16: 1365984303535620148,
    15: 1365984329603354725,
    14: 1365984372406226994,
    13: 1365985135463370854,
    12: 1365984488185659423,
    11: 1365984518942621806,
}

# Role ID pro Ligy
LEAGUE_ROLES = {
    "Legend League": 1365984556187914292,
    "Titan League": 1365984696378589214,
    "Champion League": 1365984718004420730,
    "Master League": 1365984761918652446,
    "Crystal League": 1365984789399605368,
    "Gold League": 1365984815932772402,
    "Silver League": 1365984834865991720,
    "Bronze League": 1365984854746861638,
    "Unranked": 1365984879405436978,
}

# Správa Leader/CoLeader/Admin (Elder) rolí
clan_role_mappings = {
    "leader": 1366106894816510062,
    "coLeader": 1366106931042975845,
    "admin": 1366106980732633118  # Admin = Elder v databázi
}

async def update_roles(guild: discord.Guild, user_mapping: dict, clan_members: list[dict]):
    """
    Aktualizuje role hráčům podle dat z databáze:
    - Přidává/odebírá Town Hall role
    - Přidává/odebírá League role
    - Spravuje individuální trofejovou roli
    - Přidává ověřenou roli pokud chybí
    """
    verified_role = ROLE_VERIFIED
    if not verified_role:
        print(f"❌ [role_giver] Role 'Ověřený člen klanu' s ID {ROLE_VERIFIED} nebyla nalezena.")
        return

    for discord_id, (coc_tag, _) in user_mapping.items():
        member = guild.get_member(int(discord_id))
        if not member:
            print(f"❌ [role_giver] Uživatel s ID {discord_id} nebyl nalezen.")
            continue

        player_data = next((p for p in clan_members if p['tag'] == coc_tag), None)
        if not player_data:
            print(f"❌ [role_giver] Clash hráč s tagem {coc_tag} nebyl nalezen v seznamu.")
            continue

        townhall_level = player_data.get('townHallLevel')
        league_name = player_data.get('league', "Unranked")
        trophies = player_data.get('trophies')

        player_clan_role = player_data.get("role", "").lower()

        # 👑 === Správa clan rolí (Leader / CoLeader / Elder(Admin)) ===
        # Vyber správnou roli podle aktuální role v klanu
        if player_clan_role == "leader":
            current_role_id = 1366106894816510062
        elif player_clan_role == "coleader":
            current_role_id = 1366106931042975845
        elif player_clan_role == "admin":
            current_role_id = 1366106980732633118
        else:
            current_role_id = None  # Pokud je něco jiného (třeba "member"), tak nic nedělat

        # Pokud máme určeno, jaká role má být
        if current_role_id:
            desired_role = guild.get_role(current_role_id)

            if desired_role:
                # 🧹 Nejdřív odstraníme všechny ostatní clan role (Leader, CoLeader, Elder/Admin)
                clan_role_ids = {1366106894816510062, 1366106931042975845, 1366106980732633118}

                for role in member.roles:
                    if role.id in clan_role_ids and role != desired_role:
                        try:
                            await member.remove_roles(role, reason="Aktualizace clan role")
                            print(f"♻️ [role_giver] Odebrána stará clan role {role.name} hráči {member.display_name}.")
                        except Exception as e:
                            print(f"❌ [role_giver] Chyba při odebírání clan role {role.name}: {e}")

                # Přidání správné role pokud ji ještě nemá
                if desired_role not in member.roles:
                    try:
                        await member.add_roles(desired_role)
                        print(
                            f"✅ [role_giver] Přidána správná clan role {desired_role.name} hráči {member.display_name}.")
                    except Exception as e:
                        print(f"❌ [role_giver] Chyba při přidávání clan role {desired_role.name}: {e}")
            else:
                print(f"⚠️ [role_giver] Clan role s ID {current_role_id} nebyla nalezena.")

        # === Přidání ověřené role ===
        if verified_role not in member.roles:
            try:
                await member.add_roles(verified_role)
                print(f"✅ [role_giver] Přidána role 'Ověřený člen klanu' uživateli {member.display_name}.")
            except Exception as e:
                print(f"❌ [role_giver] Chyba při přidávání role ověřeného člena uživateli {member.display_name}: {e}")

        # 🏰 === Nastavení TownHall role ===
        if townhall_level < 11:
            print(f"⚠️ [role_giver] {member.display_name} má TH{townhall_level}, což je pod limitem 11. Přeskakuji.")
        else:
            th_role_id = TOWNHALL_ROLES.get(townhall_level)
            if th_role_id:
                th_role = guild.get_role(th_role_id)

                # 🧹 Nejprve odstraníme všechny existující TH role (TH11, TH12, TH13, atd.)
                for role in member.roles:
                    if role.id in TOWNHALL_ROLES.values() and role != th_role:
                        try:
                            await member.remove_roles(role, reason="Aktualizace TownHall role")
                            print(
                                f"♻️ [role_giver] Odebrána stará TownHall role {role.name} hráči {member.display_name}.")
                        except Exception as e:
                            print(f"❌ [role_giver] Chyba při odebírání TownHall role: {e}")

                # ✅ Přidáme správnou TH roli
                if th_role and th_role not in member.roles:
                    try:
                        await member.add_roles(th_role)
                        print(f"✅ [role_giver] Přidána TH{townhall_level} role hráči {member.display_name}.")
                    except Exception as e:
                        print(f"❌ [role_giver] Chyba při přidávání TH role: {e}")
            else:
                print(f"⚠️ [role_giver] Pro TH{townhall_level} není definována role.")


        # 🏆 === Nastavení League role ===
        # Získáme základní název ligy (jen první dvě slova)
        base_league_name = " ".join(league_name.split()[:2])

        league_role_id = LEAGUE_ROLES.get(base_league_name)
        if league_role_id:
            league_role = guild.get_role(league_role_id)

            # 🧹 Nejprve odstraníme všechny existující League role
            for role in member.roles:
                if role.id in LEAGUE_ROLES.values() and role != league_role:
                    try:
                        await member.remove_roles(role, reason="Aktualizace League role")
                        print(f"♻️ [role_giver] Odebrána stará League role {role.name} hráči {member.display_name}.")
                    except Exception as e:
                        print(f"❌ [role_giver] Chyba při odebírání League role: {e}")

            # ✅ Přidáme správnou ligovou roli
            if league_role and league_role not in member.roles:
                try:
                    await member.add_roles(league_role)
                    print(f"✅ [role_giver] Přidána liga {base_league_name} hráči {member.display_name}.")
                except Exception as e:
                    print(f"❌ [role_giver] Chyba při přidávání League role: {e}")
        else:
            print(f"⚠️ [role_giver] Pro ligu {base_league_name} není definována role.")

        # 🧹 Čištění starých trofejových rolí bez členů
        for role in guild.roles:
            if "Pohárků" in role.name and len(role.members) == 0:
                try:
                    await role.delete(reason="Čištění nevyužívaných trofejových rolí")
                    print(f"🗑️ [role_giver] Smazána neaktivní trofejová role: {role.name}")
                except discord.Forbidden:
                    print(f"❌ [role_giver] Nemám právo smazat roli: {role.name}")

        # === Správa individuální trofejové role ===
        # Vždy hledáme, jestli existuje role s novým jménem
        new_trophies_name = f"⁣          🏆{trophies} Pohárků🏆            ⁣"
        existing_role = discord.utils.get(guild.roles, name=new_trophies_name)

        if existing_role:
            # Role existuje
            if existing_role not in member.roles:
                try:
                    await member.add_roles(existing_role)
                    print(f"✅ [role_giver] Přiřazena existující role {new_trophies_name} hráči {member.display_name}.")
                except discord.Forbidden:
                    print(f"❌ [role_giver] Nemám právo přiřadit existující roli {existing_role.name}.")
        else:
            # Role neexistuje -> vytvořit novou
            try:
                new_role = await guild.create_role(name=new_trophies_name, reason="Individuální role pro trofeje")
                await member.add_roles(new_role)
                print(f"✅ [role_giver] Vytvořena a přiřazena nová role {new_trophies_name} hráči {member.display_name}.")
            except discord.Forbidden:
                print(f"❌ [role_giver] Nemám právo vytvořit roli {new_trophies_name} pro {member.display_name}.")

        # A navíc, smažeme starou trofejovou roli, pokud existuje a není stejná
        trophies_role = next((r for r in member.roles if "Pohárků" in r.name and r.name != new_trophies_name), None)
        if trophies_role:
            try:
                await member.remove_roles(trophies_role, reason="Nahrazení novou trofejovou rolí")
                print(f"♻️ [role_giver] Odebrána stará trofejová role {trophies_role.name} hráči {member.display_name}.")
            except discord.Forbidden:
                print(
                    f"❌ [role_giver] Nemám právo odebrat starou roli {trophies_role.name} hráči {member.display_name}.")
