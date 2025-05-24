import discord
from discord import app_commands
from discord.utils import get
from datetime import datetime, timedelta

from api_handler import fetch_current_war
from clan_war import ClanWarHandler
from database import remove_warning, fetch_warnings, notify_single_warning, get_all_links, remove_coc_link, add_coc_link


async def setup_mod_commands(bot):
    @bot.tree.command(name="clear", description="Vyčistí kanál nebo zadaný počet zpráv", guild=bot.guild_object)
    @app_commands.describe(pocet="Kolik zpráv smazat (nebo prázdné = kompletní vymazání)")
    async def clear(interaction: discord.Interaction, pocet: int = 0):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze moderátor.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            total_deleted = 0
            if pocet > 0:
                deleted = await interaction.channel.purge(limit=pocet)
                total_deleted = len(deleted)
            else:
                while True:
                    deleted = await interaction.channel.purge(limit=100)
                    total_deleted += len(deleted)
                    if len(deleted) < 100:
                        break

            await interaction.followup.send(f"✅ Vymazáno {total_deleted} zpráv v kanálu.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Nemám právo mazat zprávy v tomto kanálu.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Došlo k chybě při mazání zpráv: {e}", ephemeral=True)

    @bot.tree.command(name="lock", description="Uzamkne kanál pro psaní", guild=bot.guild_object)
    @app_commands.describe(duvod="Důvod pro uzamčení kanálu")
    async def lock(interaction: discord.Interaction, duvod: str = None):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze moderátor.", ephemeral=True)
            return

        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔒 Kanál uzamčen",
            description=f"Moderátor {interaction.user.mention} uzamkl tento kanál." + (f"\n**Důvod:** {duvod}" if duvod else ""),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="unlock", description="Odemkne kanál pro psaní", guild=bot.guild_object)
    async def unlock(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze moderátor.", ephemeral=True)
            return

        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔓 Kanál odemknut",
            description=f"Moderátor {interaction.user.mention} odemkl tento kanál.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="timeout", description="Umlčí uživatele na určitou dobu", guild=bot.guild_object)
    @app_commands.describe(
        uzivatel="Uživatel, kterého chceš umlčet",
        minuty="Doba umlčení v minutách",
        duvod="Důvod pro umlčení"
    )
    async def timeout(interaction: discord.Interaction, uzivatel: discord.Member, minuty: int, duvod: str = None):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze moderátor.", ephemeral=True)
            return

        duration = timedelta(minutes=minuty)
        await uzivatel.timeout(duration, reason=duvod)

        embed = discord.Embed(
            title="⏳ Uživatel umlčen",
            description=f"{uzivatel.mention} byl umlčen na {minuty} minut." + (f"\n**Důvod:** {duvod}" if duvod else ""),
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="untimeout", description="Zruší umlčení uživatele", guild=bot.guild_object)
    @app_commands.describe(uzivatel="Uživatel, kterému chceš zrušit umlčení")
    async def untimeout(interaction: discord.Interaction, uzivatel: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze moderátor.", ephemeral=True)
            return

        await uzivatel.timeout(None)

        embed = discord.Embed(
            title="🔊 Umlčení zrušeno",
            description=f"{uzivatel.mention} může znovu psát.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="kick", description="Vyhodí uživatele ze serveru", guild=bot.guild_object)
    @app_commands.describe(
        uzivatel="Uživatel, kterého chceš vyhodit",
        duvod="Důvod pro vyhození"
    )
    async def kick(interaction: discord.Interaction, uzivatel: discord.Member, duvod: str = None):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze moderátor.", ephemeral=True)
            return

        await uzivatel.kick(reason=duvod)

        embed = discord.Embed(
            title="👢 Uživatel vyhozen",
            description=f"{uzivatel.display_name} byl vyhozen ze serveru." + (f"\n**Důvod:** {duvod}" if duvod else ""),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="slowmode", description="Nastaví slowmode v kanálu", guild=bot.guild_object)
    @app_commands.describe(
        sekundy="Počet sekund mezi zprávami (0 pro vypnutí)"
    )
    async def slowmode(interaction: discord.Interaction, sekundy: int):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze moderátor.", ephemeral=True)
            return

        if sekundy < 0 or sekundy > 21600:
            await interaction.response.send_message("❌ Slowmode musí být mezi 0 a 21600 sekundami (6 hodin).", ephemeral=True)
            return

        await interaction.channel.edit(slowmode_delay=sekundy)

        if sekundy == 0:
            await interaction.response.send_message("✅ Slowmode vypnut.")
        else:
            await interaction.response.send_message(f"✅ Slowmode nastaven na {sekundy} sekund.")

    @bot.tree.command(
        name="pridej_varovani",
        description="Navrhne varování pro hráče podle CoC tagu",
        guild=bot.guild_object
    )
    @app_commands.describe(
        coc_tag="Clash of Clans tag hráče",
        date_time="Datum a čas (DD/MM/YYYY HH:MM)",
        reason="Důvod varování"
    )
    async def pridej_varovani(
            interaction: discord.Interaction,
            coc_tag: str,
            reason: str = "Bez udaného důvodu",
            date_time: str | None = None
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not coc_tag.startswith("#"):
            coc_tag = f"#{coc_tag}"

        if date_time:
            try:
                # Validuj ručně
                datetime.strptime(date_time, "%d/%m/%Y %H:%M")
            except ValueError:
                await interaction.followup.send(
                    "❌ Neplatný formát času. Použij formát `DD/MM/YYYY HH:MM`, např. `14/05/2025 18:30`.",
                    ephemeral=True
                )
                return
        else:
            # Automaticky nastav aktuální čas
            date_time = datetime.now().strftime("%d/%m/%Y %H:%M")

        try:
            await notify_single_warning(interaction.client, coc_tag, date_time, reason)
            await interaction.followup.send(
                f"✅ Návrh varování pro {coc_tag} byl odeslán ke schválení.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Chyba při vytváření varování: {e}",
                ephemeral=True
            )
            print(f"❌ [slash/pridej_varovani] {e}")
    @bot.tree.command(
        name="vypis_varovani",
        description="Vypíše všechna varování (jen pro tebe)",
        guild=bot.guild_object,
    )
    async def list_warnings_cmd(interaction: discord.Interaction):
        # kontrola práv
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "❌ Tento příkaz může použít pouze moderátor.", ephemeral=True
            )
            return

        # defer – dá nám víc než 3 s na odpověď
        await interaction.response.defer(ephemeral=True)

        rows = fetch_warnings()

        if not rows:
            await interaction.followup.send("😊 Nenalezeno žádné varování.", ephemeral=True)
            return

        # sestavíme text + chunkujeme pod 2000 znaků
        header = "🔶 **Seznam varování**\n"
        lines = [f"{i}. {tag} {dt} {reason}"
                 for i, (tag, dt, reason) in enumerate(rows, 1)]
        msg = header + "\n".join(lines)

        for start in range(0, len(msg), 1990):  # 1 990 = malá rezerva
            await interaction.followup.send(
                msg[start: start + 1990], ephemeral=True
            )


    @bot.tree.command(name="odeber_varovani", description="Odstraní konkrétní varování (musí to být 1:1 napsané", guild=bot.guild_object)
    @app_commands.describe(
        coc_tag="Tag hráče",
        date_time="Datum a čas varování (DD/MM/YYYY HH:MM)",
        reason="Přesný důvod varování"
    )
    async def remove_warning_cmd(interaction: discord.Interaction, coc_tag: str, date_time: str, reason: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze moderátor.", ephemeral=True)
            return
        remove_warning(coc_tag, date_time, reason)
        await interaction.response.send_message("🗑️ Varování odstraněno (pokud existovalo).", ephemeral=True)

    @bot.tree.command(
        name="kdo_neodehral",
        description="Vypíše hráče, kteří dosud neodehráli útok ve válce",
        guild=bot.guild_object
    )
    async def kdo_neodehral(interaction: discord.Interaction):
        # ✅ 1) kontrola oprávnění
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ Tento příkaz může použít pouze moderátor.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # ✅ 2) zajištění *jedné* sdílené instance ClanWarHandler
        clan_war_handler = getattr(bot, "clan_war_handler", None)
        if clan_war_handler is None:
            clan_war_handler = ClanWarHandler(bot, bot.config)
            bot.clan_war_handler = clan_war_handler

        # ✅ 3) načtení aktuálního stavu války
        war_data = await fetch_current_war(bot.clan_tag, bot.config)
        if not war_data or war_data.get("state") is None:
            await interaction.followup.send(
                "❌ Nepodařilo se získat data o aktuální klanové válce.",
                ephemeral=True
            )
            return

        state = war_data["state"]

        # ✅ 4) větvení podle stavu války
        if state == "notInWar":
            await interaction.followup.send(
                "⚔️ Momentálně neprobíhá žádná klanová válka.",
                ephemeral=True
            )
            return

        if state == "preparation":
            await interaction.followup.send(
                "🛡️ Válka je ve fázi přípravy. Útoky zatím nelze provádět.",
                ephemeral=True
            )
            return

        if state == "warEnded":
            missing = [
                m for m in war_data["clan"]["members"]
                if not m.get("attacks")
            ]
            if not missing:
                await interaction.followup.send(
                    "🏁 Válka již skončila. Všichni členové klanu provedli své útoky.",
                    ephemeral=True
                )
                return

            # seznam jmen/mentionů s mezerou i za posledním
            names = []
            for m in missing:
                tag = m["tag"]
                name = m["name"].replace('_', r'\_').replace('*', r'\*')
                mention = await clan_war_handler._get_discord_mention(tag)
                names.append(mention if mention else f"@{name}")
            msg = "🏁 Válka již skončila. Útok neprovedli: " + " ".join(names) + " "
            await interaction.followup.send(msg, ephemeral=True)
            return

        # state == "inWar"
        result = await clan_war_handler.remind_missing_attacks(
            war_data,
            send_warning=False  # jen vrátí text, nic nepingá
        )
        await interaction.followup.send(
            result or "❌ Nelze získat informace o válce.",
            ephemeral=True
        )

        # ------------------------------------------------------------------
        # /propoj_ucet  – přidá (nebo přepíše) propojení Discord ↔ CoC účtu
        # ------------------------------------------------------------------

    @bot.tree.command(
        name="propoj_ucet",
        description="Propojí zadaný Discord účet s Clash of Clans účtem a přiřadí roli.",
        guild=bot.guild_object
    )
    @app_commands.describe(
        uzivatel="Discord uživatel k propojení",
        coc_tag="Clash of Clans tag (např. #ABC123)",
        coc_name="Jméno v Clash of Clans"
    )
    async def propojit_ucet(
            interaction: discord.Interaction,
            uzivatel: discord.Member,
            coc_tag: str,
            coc_name: str
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Tento příkaz může použít pouze administrátor.",
                ephemeral=True
            )
            return

        coc_tag = coc_tag.upper()
        if not coc_tag.startswith("#"):
            coc_tag = f"#{coc_tag}"

        try:
            add_coc_link(str(uzivatel.id), coc_tag, coc_name)

            # ➕ Přiřazení role
            role = interaction.guild.get_role(1365768439473373235)
            if role:
                try:
                    await uzivatel.add_roles(role, reason="Propojení Clash of Clans účtu")
                except discord.Forbidden:
                    await interaction.followup.send(
                        "⚠️ Nepodařilo se přiřadit roli – chybí oprávnění.",
                        ephemeral=True
                    )

            await interaction.response.send_message(
                f"✅ Účet **{coc_name}** ({coc_tag}) byl propojen s "
                f"{uzivatel.mention} a byla mu přiřazena role.",
                ephemeral=False
            )

            # DM uživateli (nevadí, když selže)
            try:
                await uzivatel.send(
                    f"🔗 Tvůj Discord účet byl propojen s Clash of Clans účtem "
                    f"**{coc_name}** (`{coc_tag}`). Byla ti také přidána role na serveru."
                )
            except Exception:
                pass

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Nepodařilo se uložit propojení: {e}",
                ephemeral=True
            )

    # ------------------------------------------------------------------
    # /odpoj_ucet – odstraní propojení pro volajícího uživatele
    # ------------------------------------------------------------------
    @bot.tree.command(
        name="odpoj_ucet",
        description="Odpojí Clash of Clans účet od Discord uživatele a odebere roli.",
        guild=bot.guild_object
    )
    @app_commands.describe(
        uzivatel="Discord uživatel k odpojení (pokud vynecháš, odpojí tebe)"
    )
    async def odpoj_ucet(
            interaction: discord.Interaction,
            uzivatel: discord.Member | None = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Tento příkaz může použít pouze administrátor.",
                ephemeral=True
            )
            return

        # Pokud parametr chybí, bereme volajícího
        uzivatel = uzivatel or interaction.user

        try:
            remove_coc_link(str(uzivatel.id))

            # ➖ Odebrání role
            role = interaction.guild.get_role(1365768439473373235)
            if role and role in uzivatel.roles:
                try:
                    await uzivatel.remove_roles(role, reason="Odpojení Clash of Clans účtu")
                except discord.Forbidden:
                    await interaction.followup.send(
                        "⚠️ Nepodařilo se odebrat roli – chybí oprávnění.",
                        ephemeral=True
                    )

            await interaction.response.send_message(
                f"🗑️ Propojení bylo odstraněno a roli jsem odebral uživateli {uzivatel.mention}.",
                ephemeral=False
            )

            # DM (opět jen best-effort)
            try:
                await uzivatel.send(
                    "🔌 Tvé propojení s Clash of Clans účtem bylo zrušeno a role odebrána."
                )
            except Exception:
                pass

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Nepodařilo se odpojit účet: {e}",
                ephemeral=True
            )

    # ------------------------------------------------------------------
    # /seznam_propojeni – vypíše všechna propojení (jen volajícímu)
    # ------------------------------------------------------------------
    @bot.tree.command(
        name="seznam_propojeni",
        description="Vypíše seznam všech Discord ↔ CoC propojení.",
        guild=bot.guild_object
    )
    async def seznam_propojeni(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Tento příkaz může použít pouze administrátor.",
                ephemeral=True
            )
            return

        try:
            links = get_all_links()  # dict {discord_id: (coc_tag, coc_name)}
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Chyba při čtení databáze: {e}",
                ephemeral=True
            )
            return

        if not links:
            await interaction.response.send_message(
                "ℹ️ Zatím nejsou žádná propojení.",
                ephemeral=True
            )
            return

        lines = ["**Seznam propojených účtů:**"]
        for discord_id, (tag, name) in links.items():
            lines.append(f"- <@{discord_id}> → **{name}** (`{tag}`)")
        # zpráva jen volajícímu, aby se zbytečně nespamovalo
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @bot.tree.command(name="pravidla_discord", description="Zobrazí pravidla Discord serveru", guild=bot.guild_object)
    async def pravidla_discord(interaction: discord.Interaction):
        embed = discord.Embed(
            title="📜 Pravidla Discord serveru",
            description="Pravidla pro všechny členy našeho Discord serveru:",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="1. Chování a komunikace",
            value="• Respektujte všechny členy serveru\n"
                  "• Žádné urážky, rasismus, sexismu nebo jiná forma diskriminace\n"
                  "• Mluvte výhradně česky\n"
                  "• Žádné spammování nebo floodování zprávami\n"
                  "• Dodržujte témata kanálů",
            inline=False
        )

        embed.add_field(
            name="2. Sdílení obsahu",
            value="• Odkazy smíte posílat pouze pokud se týkají kontextu konverzace\n"
                  "• Zakázány jsou náhodné Discord invite nebo reklamy\n"
                  "• NSFW obsah je striktně zakázán",
            inline=False
        )

        embed.add_field(
            name="3. Role a oprávnění",
            value="• Nežádejte o vyšší role - ty se přidělují podle postavení v klanu\n"
                  "• Zneužívání rolí nebo botů bude potrestáno\n"
                  "• Moderátoři mají vždy pravdu",
            inline=False
        )

        embed.add_field(
            name="4. Hlasové kanály",
            value="• Respektujte toho, kdo mluví\n"
                  "• Žádné rušení hlukem v pozadí\n"
                  "• Hudba pouze v určených kanálech",
            inline=False
        )

        embed.set_footer(text="Porušení pravidel může vést k mute, kick nebo banu, podle závažnosti přestupku")

        await interaction.response.send_message("Pravidla zobrazena", ephemeral=True, delete_after=1)
        await interaction.channel.send(embed=embed)

    @bot.tree.command(name="pravidla_clan", description="Zobrazí pravidla herního klanu", guild=bot.guild_object)
    async def pravidla_clan(interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚔️ Pravidla Klanu Czech Heroes",
            description="Pravidla pro všechny členy našeho herního klanu:",
            color=discord.Color.gold()
        )

        # Sekce obecná pravidla
        embed.add_field(
            name="🔹 Obecná pravidla",
            value="• Minimální aktivita 3 dny - po delší neaktivitě hrozí kick\n"
                  "• Clan Games: od každého očekáváme minimálně 1000 bodů\n"
                  "• Clan Capital: povinné využít všech 6 útoků\n"
                  "• Donate: darujte co to jde, ideálně nemít donate na 0",
            inline=False
        )

        # Výrazně zvýrazněná sekce Clan War
        embed.add_field(
            name="⚔️ CLAN WAR - NEJDŮLEŽITĚJŠÍ PRAVIDLA",
            value="```diff\n"
                  "+ 1. útok: VŽDY MIRROR (stejné číslo)\n"
                  "+ Ideálně odehrát před 5. hodinou do konce války\n\n"
                  "+ 2. útok: oprava nějakého cizího útoku\n"
                  "+ Nebo na koho chcete, pokud zbývá méně než 5h do konce CW\n\n"
                  "! Neodehrání útoku = VAROVÁNÍ\n"
                  "```",
            inline=False
        )

        # Sekce přihlašování do waru
        embed.add_field(
            name="📝 Přihlašování do Clan War",
            value="• Pár hodin před začátkem války pošlu \"Clan War Sign-Up\"\n"
                  "• Palec nahoru = 100% účast (musíš dodržet pravidla)\n"
                  "• Palec dolů = 100% nebudeš ve válce\n"
                  "• Nereaguješ + zelený štít = možná účast (doplňujeme počet)\n"
                  "• Nereaguješ + červený štít = nebudeš ve válce",
            inline=False
        )

        embed.add_field(
            name="ℹ️ Poznámky",
            value="• Války vždy začínají ve večerních hodinách (17-24)\n"
                  "• Pravidla se mohou v budoucnu změnit\n"
                  "• Kicknutí členové mohou dostat pozvánku zpátky pokud vím že byly aktivní",
            inline=False
        )

        embed.set_footer(text="Po 3 varováních hrozí kick z klanu")

        await interaction.response.send_message("Pravidla zobrazena", ephemeral=True, delete_after=1)
        await interaction.channel.send(embed=embed)