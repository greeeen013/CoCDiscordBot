import asyncio
from pathlib import Path

import discord
from discord import app_commands
from discord.utils import get
from datetime import datetime, timedelta, timezone
from typing import Optional

from api_handler import fetch_current_war
from clan_war import ClanWarHandler
from database import remove_warning, fetch_warnings, notify_single_warning, get_all_links, remove_coc_link, add_coc_link


async def setup_mod_commands(bot):
    # Pomocná funkce pro automatické mazání ephemerálních zpráv
    async def auto_delete_ephemeral(message: discord.Message | discord.Interaction, delay: int = 180):
        """Automatically delete ephemeral message after specified delay"""
        try:
            await asyncio.sleep(delay)
            if isinstance(message, discord.Interaction):
                if message.response.is_done():
                    await message.delete_original_response()
            else:
                await message.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

    async def send_ephemeral(interaction: discord.Interaction, content: str, delete_after: int = 180, **kwargs):
        """Helper function to send ephemeral messages with auto-delete"""
        if interaction.response.is_done():
            msg = await interaction.followup.send(content, ephemeral=True, **kwargs)
        else:
            msg = await interaction.response.send_message(content, ephemeral=True, **kwargs)

        if delete_after and delete_after > 0:
            asyncio.create_task(auto_delete_ephemeral(msg, delete_after))
        return msg

    @bot.tree.command(name="clear", description="Vyčistí kanál nebo zadaný počet zpráv", guild=bot.guild_object)
    @app_commands.describe(pocet="Kolik zpráv smazat (nebo prázdné = kompletní vymazání)")
    async def clear(interaction: discord.Interaction, pocet: int = 0):
        if not interaction.user.guild_permissions.manage_messages:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
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

            await send_ephemeral(interaction, f"✅ Vymazáno {total_deleted} zpráv v kanálu.")
        except discord.Forbidden:
            await send_ephemeral(interaction, "❌ Nemám právo mazat zprávy v tomto kanálu.")
        except Exception as e:
            await send_ephemeral(interaction, f"❌ Došlo k chybě při mazání zpráv: {e}")

    @bot.tree.command(name="lock", description="Uzamkne kanál pro psaní", guild=bot.guild_object)
    @app_commands.describe(duvod="Důvod pro uzamčení kanálu")
    async def lock(interaction: discord.Interaction, duvod: str = None):
        if not interaction.user.guild_permissions.manage_channels:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔒 Kanál uzamčen",
            description=f"Moderátor {interaction.user.mention} uzamkl tento kanál." + (
                f"\n**Důvod:** {duvod}" if duvod else ""),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="unlock", description="Odemkne kanál pro psaní", guild=bot.guild_object)
    async def unlock(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
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
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        duration = timedelta(minutes=minuty)
        await uzivatel.timeout(duration, reason=duvod)

        embed = discord.Embed(
            title="⏳ Uživatel umlčen",
            description=f"{uzivatel.mention} byl umlčen na {minuty} minut." + (
                f"\n**Důvod:** {duvod}" if duvod else ""),
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="untimeout", description="Zruší umlčení uživatele", guild=bot.guild_object)
    @app_commands.describe(uzivatel="Uživatel, kterému chceš zrušit umlčení")
    async def untimeout(interaction: discord.Interaction, uzivatel: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
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
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
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
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        if sekundy < 0 or sekundy > 21600:
            await send_ephemeral(interaction, "❌ Slowmode musí být mezi 0 a 21600 sekundami (6 hodin).")
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
                datetime.strptime(date_time, "%d/%m/%Y %H:%M")
            except ValueError:
                await send_ephemeral(interaction,
                                     "❌ Neplatný formát času. Použij formát `DD/MM/YYYY HH:MM`, např. `14/05/2025 18:30`.")
                return
        else:
            date_time = datetime.now().strftime("%d/%m/%Y %H:%M")

        try:
            await notify_single_warning(interaction.client, coc_tag, date_time, reason)
            await send_ephemeral(interaction, f"✅ Návrh varování pro {coc_tag} byl odeslán ke schválení.")
        except Exception as e:
            await send_ephemeral(interaction, f"❌ Chyba při vytváření varování: {e}")
            print(f"❌ [slash/pridej_varovani] {e}")

    @bot.tree.command(
        name="vypis_varovani",
        description="Vypíše všechna varování (jen pro tebe)",
        guild=bot.guild_object,
    )
    async def list_warnings_cmd(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.moderate_members:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        await interaction.response.defer(ephemeral=True)

        rows = fetch_warnings()
        all_links = get_all_links()

        if not rows:
            await send_ephemeral(interaction, "😊 Nenalezeno žádné varování.")
            return

        header = "🔶 **Seznam varování**\n"
        lines = []

        for i, (tag, dt, reason) in enumerate(rows, 1):
            coc_name = next((name for _, (t, name) in all_links.items() if t == tag), "Neznámý hráč")
            lines.append(f"{i}. {tag} ({coc_name}) | {dt} | {reason}")

        msg = header + "\n".join(lines)

        for start in range(0, len(msg), 1990):
            await send_ephemeral(interaction, msg[start: start + 1990])

    @bot.tree.command(name="odeber_varovani", description="Odstraní konkrétní varování (musí to být 1:1 napsané",
                      guild=bot.guild_object)
    @app_commands.describe(
        coc_tag="Tag hráče",
        date_time="Datum a čas varování (DD/MM/YYYY HH:MM)",
        reason="Přesný důvod varování"
    )
    async def remove_warning_cmd(interaction: discord.Interaction, coc_tag: str, date_time: str, reason: str):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return
        remove_warning(coc_tag, date_time, reason)
        await send_ephemeral(interaction, "🗑️ Varování odstraněno (pokud existovalo).")

    @bot.tree.command(
        name="kdo_neodehral",
        description="Vypíše hráče, kteří dosud neodehráli útok ve válce.",
        guild=bot.guild_object
    )
    @app_commands.describe(
        zbyva="Zobrazit hráče, kteří mají ještě zbývající útoky (default: False, zobrazí hráče bez útoků)"
    )
    async def kdo_neodehral(interaction: discord.Interaction, zbyva: bool = False):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze moderátor.")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        clan_war_handler = getattr(bot, "clan_war_handler", None)
        if clan_war_handler is None:
            clan_war_handler = ClanWarHandler(bot, bot.config)
            bot.clan_war_handler = clan_war_handler

        war_data = await fetch_current_war(bot.clan_tag, bot.config)
        if not war_data or war_data.get("state") is None:
            await send_ephemeral(interaction, "❌ Nepodařilo se získat data o aktuální klanové válce.")
            return

        state = war_data["state"]

        if state == "notInWar":
            await send_ephemeral(interaction, "⚔️ Momentálně neprobíhá žádná klanová válka.")
            return

        if state == "preparation":
            await send_ephemeral(interaction, "🛡️ Válka je ve fázi přípravy. Útoky zatím nelze provádět.")
            return

        async def format_missing_players(members, prefix):
            if not members:
                await send_ephemeral(interaction, f"{prefix} Všichni členové klanu již provedli své útoky.")
                return

            await send_ephemeral(interaction, prefix)

            batch = []
            for m in members:
                tag = m["tag"]
                name = m["name"].replace('_', r'\_').replace('*', r'\*')
                mention = await clan_war_handler._get_discord_mention(tag)
                batch.append(mention if mention else f"@{name}")

                if len(batch) >= 5:
                    await send_ephemeral(interaction, " ".join(batch) + " .")
                    batch = []

            if batch:
                await send_ephemeral(interaction, " ".join(batch) + " .")

        if state == "warEnded":
            if zbyva:
                missing = [m for m in war_data["clan"]["members"] if
                           len(m.get("attacks", [])) < war_data.get("attacksPerMember", 1)]
            else:
                missing = [m for m in war_data["clan"]["members"] if not m.get("attacks")]
            await format_missing_players(missing, "🏁 Válka již skončila. Útok neprovedli:")
            return

        attacks_per_member = war_data.get("attacksPerMember", 1)
        if zbyva:
            missing = [m for m in war_data["clan"]["members"] if len(m.get("attacks", [])) < attacks_per_member]
        else:
            missing = [m for m in war_data["clan"]["members"] if len(m.get("attacks", [])) == 0]

        end_time = clan_war_handler._parse_coc_time(war_data.get('endTime', ''))
        if end_time:
            remaining = end_time - datetime.now(timezone.utc)
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            time_info = f" (zbývá {hours}h {minutes}m)"
        else:
            time_info = ""

        if zbyva:
            await format_missing_players(missing, f"⚔️ Probíhá válka{time_info}. Hráči s alespoň 1 zbývajícím útokem:")
        else:
            await format_missing_players(missing, f"⚔️ Probíhá válka{time_info}. Hráči, kteří neprovedli žádný útok:")

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
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        coc_tag = coc_tag.upper()
        if not coc_tag.startswith("#"):
            coc_tag = f"#{coc_tag}"

        try:
            add_coc_link(str(uzivatel.id), coc_tag, coc_name)

            role = interaction.guild.get_role(1365768439473373235)
            if role:
                try:
                    await uzivatel.add_roles(role, reason="Propojení Clash of Clans účtu")
                except discord.Forbidden:
                    await send_ephemeral(interaction, "⚠️ Nepodařilo se přiřadit roli – chybí oprávnění.")

            await interaction.response.send_message(
                f"✅ Účet **{coc_name}** ({coc_tag}) byl propojen s {uzivatel.mention} a byla mu přiřazena role.",
                ephemeral=False
            )

            try:
                await uzivatel.send(
                    f"🔗 Tvůj Discord účet byl propojen s Clash of Clans účtem **{coc_name}** (`{coc_tag}`).")
            except Exception:
                pass

        except Exception as e:
            await send_ephemeral(interaction, f"❌ Nepodařilo se uložit propojení: {e}")

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
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        uzivatel = uzivatel or interaction.user

        try:
            remove_coc_link(str(uzivatel.id))

            role = interaction.guild.get_role(1365768439473373235)
            if role and role in uzivatel.roles:
                try:
                    await uzivatel.remove_roles(role, reason="Odpojení Clash of Clans účtu")
                except discord.Forbidden:
                    await send_ephemeral(interaction, "⚠️ Nepodařilo se odebrat roli – chybí oprávnění.")

            await interaction.response.send_message(
                f"🗑️ Propojení bylo odstraněno a roli jsem odebral uživateli {uzivatel.mention}.",
                ephemeral=False
            )

            try:
                await uzivatel.send("🔌 Tvé propojení s Clash of Clans účtem bylo zrušeno a role odebrána.")
            except Exception:
                pass

        except Exception as e:
            await send_ephemeral(interaction, f"❌ Nepodařilo se odpojit účet: {e}")

    @bot.tree.command(
        name="seznam_propojeni",
        description="Vypíše seznam všech Discord ↔ CoC propojení.",
        guild=bot.guild_object
    )
    async def seznam_propojeni(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        try:
            links = get_all_links()
        except Exception as e:
            await send_ephemeral(interaction, f"❌ Chyba při čtení databáze: {e}")
            return

        if not links:
            await send_ephemeral(interaction, "ℹ️ Zatím nejsou žádná propojení.")
            return

        lines = ["**Seznam propojených účtů:**"]
        for discord_id, (tag, name) in links.items():
            lines.append(f"- <@{discord_id}> → **{name}** (`{tag}`)")

        await send_ephemeral(interaction, "\n".join(lines), delete_after=300)  # 5 minut pro delší výpisy

    @bot.tree.command(name="pravidla_discord", description="Zobrazí pravidla Discord serveru", guild=bot.guild_object)
    async def pravidla_discord(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        await send_ephemeral(interaction, "Pravidla zobrazena", delete_after=1)

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
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        await send_ephemeral(interaction, "Pravidla zobrazena", delete_after=1)

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

    @bot.tree.command(name="vitej", description="Vítej na našem Discord serveru", guild=bot.guild_object)
    async def vitej(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        await send_ephemeral(interaction, "Vítej zpráva odeslána", delete_after=1)

        embed = discord.Embed(
            title="🎉 Vítej na Discord serveru Czech Heroes!",
            description="Oficiální Discord pro herní klan **Czech Heroes** ze hry Clash of Clans!",
            color=discord.Color.green()
        )

        # Sekce pro členy klanu
        embed.add_field(
            name="🔹 Jsi členem našeho klanu?",
            value=(
                f"1. Projdi si pravidla v {interaction.guild.get_channel(1366000196991062086).mention}\n"
                f"2. Proveď ověření v {interaction.guild.get_channel(1366471838070476821).mention}\n"
                "3. Po ověření získáš automaticky:\n"
                "   - Speciální roli podle postavení v klanu (Leader, Co-leader, Elder...)\n"
                "   - Role na míru podle počtu pohárků, TH level, Liga\n"
                "   - Přezdívka na Discord serveru nastavena na herní jméno"
                "   - Přístup ke všem sekcím serveru"
            ),
            inline=False
        )

        # Sekce pro návštěvníky
        embed.add_field(
            name="🔹 Jsi návštěvník?",
            value=(
                "I pro tebe máme omezený přístup(někdy):\n"
                "- Můžeš pokecat v obecných chatech\n"
                "- Podívat se na pravidla\n"
                "- Případně se připojit do klanu a projít plnou verifikací"
            ),
            inline=False
        )

        # Sekce s výhodami serveru
        embed.add_field(
            name="📊 Co všechno zde najdeš?",
            value=(
                f"- Přehledné statistiky o Clan War v {interaction.guild.get_channel(1366835944174391379).mention}\n"
                f"   - Aktuální Clan War útoky a obrany v {interaction.guild.get_channel(1366835971395686554).mention}\n"
                f"- Detaily o Clan Capital v {interaction.guild.get_channel(1370467834932756600).mention}\n"
                f"- Herní eventy v {interaction.guild.get_channel(1367054076688339053).mention}\n"
                f"- Místo pro obecný pokec v {interaction.guild.get_channel(1370722795826450452).mention}\n"
                "- Tipy a triky jak hrát lépe\n"
                "- A mnohem více!"
            ),
            inline=False
        )

        embed.set_footer(text="Těšíme se na tebe v našem klanu i na Discordu!")

        await interaction.response.send_message("Vítej zpráva odeslána", ephemeral=True, delete_after=1)
        await interaction.channel.send(embed=embed)

    @bot.tree.command(
        name="vypis_log",
        description="Vypíše poslední řádky z log souboru (pouze pro administrátory)",
        guild=bot.guild_object
    )
    @app_commands.describe(
        pocet_radku="Kolik posledních řádků zobrazit (default: 50, max: 500)"
    )
    async def vypis_log(interaction: discord.Interaction, pocet_radku: int = 50):
        if not interaction.user.guild_permissions.administrator:
            await send_ephemeral(interaction, "❌ Tento příkaz může použít pouze administrátor.")
            return

        pocet_radku = min(max(pocet_radku, 1), 500)
        await interaction.response.defer(ephemeral=True, thinking=True)

        log_file = Path(__file__).parent / "CoCDiscordBot.log"

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if not lines:
                await send_ephemeral(interaction, "ℹ️ Log soubor je prázdný.")
                return

            last_lines = lines[-pocet_radku:]
            current_chunk = []
            current_length = 0

            for line in last_lines:
                line_length = len(line)

                if current_length + line_length > 1900:
                    if current_chunk:
                        await send_ephemeral(interaction, f"```\n{''.join(current_chunk)}\n```", delete_after=300)
                        current_chunk = []
                        current_length = 0

                    if line_length > 1900:
                        parts = [line[i:i + 1900] for i in range(0, len(line), 1900)]
                        for part in parts[:-1]:
                            await send_ephemeral(interaction, f"```\n{part}\n```", delete_after=300)
                        line = parts[-1]
                        line_length = len(line)

                current_chunk.append(line)
                current_length += line_length

            if current_chunk:
                await send_ephemeral(interaction, f"```\n{''.join(current_chunk)}\n```", delete_after=300)

        except FileNotFoundError:
            await send_ephemeral(interaction, f"❌ Log soubor '{log_file}' nebyl nalezen.")
        except Exception as e:
            await send_ephemeral(interaction, f"❌ Chyba při čtení log souboru: {e}")