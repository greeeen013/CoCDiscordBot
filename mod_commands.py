import discord
from discord import app_commands

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