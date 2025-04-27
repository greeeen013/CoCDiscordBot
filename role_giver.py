import discord

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

async def update_roles(guild: discord.Guild, user_mapping: dict, clan_members: list[dict]):
    """
    Aktualizuje role hráčům podle dat z databáze:
    - Přidává Town Hall role
    - Přidává League role
    - Spravuje individuální trofejovou roli
    """
    for discord_id, (coc_tag, _) in user_mapping.items():
        member = guild.get_member(int(discord_id))
        if not member:
            print(f"❌ [RoleGiver] Uživatel s ID {discord_id} nebyl nalezen.")
            continue

        player_data = next((p for p in clan_members if p['tag'] == coc_tag), None)
        if not player_data:
            print(f"❌ [RoleGiver] Clash hráč s tagem {coc_tag} nebyl nalezen v seznamu.")
            continue

        townhall_level = player_data.get('townHallLevel')
        league_name = player_data.get('league', "Unranked")
        trophies = player_data.get('trophies')

        # === Townhall kontrola ===
        if townhall_level < 11:
            print(f"⚠️ [RoleGiver] {member.display_name} má TH{townhall_level}, což je pod limitem 11. Přeskakuji.")
            continue

        # === Nastavení Townhall role ===
        th_role_id = TOWNHALL_ROLES.get(townhall_level)
        if th_role_id:
            th_role = guild.get_role(th_role_id)
            if th_role:
                await member.add_roles(th_role)
                print(f"✅ [RoleGiver] Přidána TH{townhall_level} role hráči {member.display_name}.")
            else:
                print(f"⚠️ [RoleGiver] Role TH{townhall_level} s ID {th_role_id} nebyla nalezena.")
        else:
            print(f"⚠️ [RoleGiver] Pro TH{townhall_level} není definována role.")

        # === Nastavení League role ===
        league_role_id = LEAGUE_ROLES.get(league_name)
        if league_role_id:
            league_role = guild.get_role(league_role_id)
            if league_role:
                await member.add_roles(league_role)
                print(f"✅ [RoleGiver] Přidána liga {league_name} hráči {member.display_name}.")
            else:
                print(f"⚠️ [RoleGiver] Role {league_name} nebyla nalezena.")
        else:
            print(f"⚠️ [RoleGiver] Pro ligu {league_name} není definována role.")

        # === Správa individuální trofejové role ===
        trophies_role = next((r for r in member.roles if r.name.endswith("Trophies")), None)
        new_trophies_name = f"{trophies} Trophies"

        if trophies_role:
            try:
                await trophies_role.edit(name=new_trophies_name)
                print(f"♻️ [RoleGiver] Přejmenována role na {new_trophies_name} pro {member.display_name}.")
            except discord.Forbidden:
                print(f"❌ [RoleGiver] Nemám právo přejmenovat roli {trophies_role.name}.")
        else:
            try:
                new_role = await guild.create_role(name=new_trophies_name, reason="Individuální role pro trofeje")
                await member.add_roles(new_role)
                print(f"✅ [RoleGiver] Vytvořena a přiřazena role {new_trophies_name} hráči {member.display_name}.")

                # ⚙️ POZICE ROLE (zatím neřešíme, ale tady to lze nastavovat):
                # await new_role.edit(position=nějaké_číslo)
            except discord.Forbidden:
                print(f"❌ [RoleGiver] Nemám právo vytvořit roli {new_trophies_name} pro {member.display_name}.")
