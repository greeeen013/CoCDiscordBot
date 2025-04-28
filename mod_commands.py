import discord
from discord import app_commands
from discord.utils import get
from datetime import datetime, timedelta

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