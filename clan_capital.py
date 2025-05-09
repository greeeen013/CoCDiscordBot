import discord
from datetime import datetime
from typing import Optional


class ClanCapitalHandler:
    def __init__(self, bot, config):
        """
        Inicializace handleru pro správu Capital Raid embed zprávy.
        """
        self.bot = bot                              # Discord bot instance
        self.config = config                        # Konfigurační slovník (obsahuje např. COC API klíč, GUILD_ID apod.)
        self.capital_status_channel_id = 1370467834932756600  # ID Discord kanálu, kam se bude embed posílat
        self.current_capital_message_id = None      # Uchovává ID aktivní embed zprávy pro možnost úpravy
        self._last_state = None                     # Sleduje předchozí stav (např. 'ongoing', 'ended')

    def _create_capital_embed(self, state: str, data: dict) -> discord.Embed:
        """
        Vytvoří a vrátí embed podle stavu capital raidu ('ongoing' nebo 'ended').
        """
        if state == "ended":
            # Embed pro ukončený raid
            embed = discord.Embed(
                title="🏁 Capital Raid: Ukončeno",
                description="Statistiky budou doplněny později...",
                color=discord.Color.red()
            )
            embed.set_footer(text="Stav: ended")
            return embed

        # Embed pro probíhající raid
        start = self._parse_time(data.get("startTime"))      # začátek jako datetime
        end = self._parse_time(data.get("endTime"))          # konec jako datetime
        start_ts = int(start.timestamp()) if start else 0    # timestamp pro Discord tag
        end_ts = int(end.timestamp()) if end else 0

        embed = discord.Embed(
            title="🏰 Capital Raid: Probíhá",
            color=discord.Color.purple()
        )

        # Začátek a konec s formátem Discordu (zobrazí jak konkrétní datum, tak relativní čas)
        embed.add_field(name="Začátek", value=f"<t:{start_ts}>\n<t:{start_ts}:R>", inline=True)
        embed.add_field(name="Konec", value=f"<t:{end_ts}>\n<t:{end_ts}:R>", inline=True)

        # Statistiky s centrovaným formátem a monospaced fontem
        embed.add_field(
            name="💰 Loot",
            value=f"`{data.get('capitalTotalLoot', 0):^10,}`",
            inline=True
        )
        embed.add_field(
            name="⚔️ Raids Completed",
            value=f"`{data.get('raidsCompleted', 0):^10}`",
            inline=True
        )
        embed.add_field(
            name="🎯 Attacks",
            value=f"`{data.get('totalAttacks', 0):^10}`",
            inline=True
        )
        embed.add_field(
            name="🏙️ Districts Destroyed",
            value=f"`{data.get('enemyDistrictsDestroyed', 0):^10}`",
            inline=True
        )

        embed.set_footer(text="Stav: ongoing")
        return embed

    async def process_capital_data(self, capital_data: dict):
        """
        Zpracuje předaná data z Clash of Clans API a aktualizuje embed.
        Pokud došlo ke změně stavu raidu, zapíše do konzole.
        """
        if not capital_data:
            print("❌ [clan_capital] Žádná data o raidu ke zpracování")
            return

        # Získáme aktuální stav (např. 'ongoing' nebo 'ended')
        state = capital_data.get('state', 'unknown')

        # Pokud se stav změnil od minula, informujeme v konzoli
        if state != self._last_state:
            print(f"ℹ️ [clan_capital] Stav se změnil na: {state}")

        self._last_state = state

        # Vytvoříme embed na základě aktuálního stavu a dat
        embed = self._create_capital_embed(state, capital_data)

        # Odešleme nebo upravíme zprávu s embedem
        await self.update_capital_message(embed)

