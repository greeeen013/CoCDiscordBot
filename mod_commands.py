import discord
from discord import app_commands
from discord.utils import get
from datetime import datetime, timedelta

from api_handler import fetch_current_war
from clan_war import ClanWarHandler
from database import remove_warning, add_warning, fetch_warnings


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

    @bot.tree.command(name="pridej_varovani", description="Přidá varování hráči podle CoC tagu", guild=bot.guild_object)
    @app_commands.describe(
        coc_tag="Clash of Clans tag hráče",
        date_time="Datum a čas (DD/MM/YYYY HH:MM)",
        reason="Důvod varování"
    )
    async def add_warning_cmd(interaction: discord.Interaction, coc_tag: str, date_time: str = None,
                              reason: str = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tento příkaz může použít pouze moderátor.", ephemeral=True)
            return
        add_warning(coc_tag, date_time, reason, bot)
        await interaction.response.send_message(f"✅ Varování přidáno pro {coc_tag}.", ephemeral=True)

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