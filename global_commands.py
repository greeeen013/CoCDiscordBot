import asyncio
import re
import datetime as dt
import discord
from discord import app_commands, Interaction
from discord.ext import commands

# ====== NASTAVENÍ LIMITŮ A ROLE IDS ======
from constants import ROLE_ELDER, ROLE_CO_LEADER, ROLE_LEADER

# Limity v sekundách
LIMIT_NORMAL   = 2 * 24 * 60 * 60       # 2 dny
LIMIT_ELDER    = 5 * 24 * 60 * 60       # 5 dní
LIMIT_COLEADER = 6 * 24 * 60 * 60       # 6 dní
LIMIT_LEADER   = None                   # bez limitu

DURATION_PATTERN = re.compile(
    r'^\s*(?:(?P<d>\d+)\s*d)?\s*(?:(?P<h>\d+)\s*h)?\s*(?:(?P<m>\d+)\s*m)?\s*(?:(?P<s>\d+)\s*s)?\s*$',
    re.IGNORECASE
)

def parse_duration_to_seconds(text: str) -> int | None:
    """
    '1d 2h 30m 10s' -> sekundy (int)
    Povolené jednotky: d, h, m, s (libovolné pořadí, volitelné mezery).
    Prázdný vstup nebo 0 -> None.
    """
    m = DURATION_PATTERN.match(text or "")
    if not m:
        return None
    d = int(m.group("d") or 0)
    h = int(m.group("h") or 0)
    mnt = int(m.group("m") or 0)
    s = int(m.group("s") or 0)
    total = d*86400 + h*3600 + mnt*60 + s
    return total if total > 0 else None

def humanize_seconds(sec: int) -> str:
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s or not parts: parts.append(f"{s}s")
    return " ".join(parts)

def get_role_limit_seconds(member: discord.Member | None) -> int | None:
    """
    Vrátí max. povolený interval v sekundách dle role.
    None = bez limitu (leader).
    Pokud member není k dispozici (např. DM), vrací limit pro normálního uživatele.
    """
    if not isinstance(member, discord.Member):
        return LIMIT_NORMAL

    role_ids = {r.id for r in member.roles}
    if ROLE_LEADER in role_ids:
        return LIMIT_LEADER
    if ROLE_CO_LEADER in role_ids:
        return LIMIT_COLEADER
    if ROLE_ELDER in role_ids:
        return LIMIT_ELDER
    return LIMIT_NORMAL

class GlobalCommands(commands.Cog):
    """Globální slash příkazy pro všechny servery, kde je bot."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ----------------------------
    # /upozorni_me
    # ----------------------------
    @app_commands.command(
        name="upozorni_me",
        description="Pošlu ti za daný čas soukromou zprávu (např. 1d 1h 1m 1s)."
    )
    @app_commands.describe(
        interval="Relativní čas, např. '1d 1h 1m 1s' (pořadí libovolné).",
        zprava="Volitelná zpráva, kterou ti připomenu."
    )
    async def upozorni_me(
        self,
        interaction: Interaction,
        interval: str,
        zprava: str | None = None
    ):
        """Naplánuje DM připomínku za zadaný interval s role-based limitem."""
        # 1) parse interval
        seconds = parse_duration_to_seconds(interval)
        if seconds is None:
            return await interaction.response.send_message(
                "❌ Špatný formát času. Příklad: `1d 2h 30m` nebo `45m`.",
                ephemeral=True
            )

        # 2) limit podle role
        member = interaction.user if isinstance(interaction.user, discord.Member) else interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        limit = get_role_limit_seconds(member)

        if limit is not None and seconds > limit:
            return await interaction.response.send_message(
                f"⛔ Překročen limit pro tvoji roli. Max: **{humanize_seconds(limit)}**.",
                ephemeral=True
            )

        # 3) potvrzení (ephemeral) – ať splníme 3s limit
        when_text = humanize_seconds(seconds)
        await interaction.response.send_message(
            f"✅ OK, připomenu ti to za **{when_text}**.",
            ephemeral=True
        )

        # 4) naplánovat úkol na pozadí (nepřežije restart bota)
        user = interaction.user

        async def task():
            try:
                await asyncio.sleep(seconds)
                text = zprava.strip() if zprava else "🕑 Tvůj čas právě vypršel!"
                # pokus o DM
                try:
                    await user.send(text)
                except discord.Forbidden:
                    # DM selhalo (blok, nastavení soukromí…) – zkusíme odpovědět do kanálu, pokud to jde
                    if interaction.guild and interaction.channel:
                        await interaction.followup.send(
                            f"⚠️ Nemohu poslat DM **{user.mention}**. Připomínka: {text}",
                            ephemeral=False
                        )
            except Exception as e:
                # volitelně: log
                print(f"[upozorni_me] Task error: {e}")

        asyncio.create_task(task())

    # ----------------------------
    # /random
    # ----------------------------
    @app_commands.command(
        name="random",
        description="Náhodné číslo (min/max) nebo hod mincí."
    )
    @app_commands.describe(
        min="Dolní mez (výchozí 1)",
        max="Horní mez (výchozí 6)",
        mince="Zapnout hod mincí místo čísla"
    )
    async def random_cmd(
        self,
        interaction: Interaction,
        min: int = 1,
        max: int = 6,
        mince: bool = False
    ):
        import random

        if mince:
            result = random.choice(["Panna", "Orel"])
            return await interaction.response.send_message(f"Výsledek: **{result}**")

        if min > max:
            min, max = max, min

        # bezpečné ohraničení (volitelné)
        span = max - min
        if span > 10_000_000:
            return await interaction.response.send_message(
                "⛔ Rozsah je příliš velký.",
                ephemeral=True
            )

        num = random.randint(min, max)
        await interaction.response.send_message(f"Výsledek: **{num}**")

async def setup(bot: commands.Bot):
    await bot.add_cog(GlobalCommands(bot))
