import asyncio
import re
import discord
from discord import app_commands, Interaction
from discord.ext import commands

# ROLE IDs z constants (domovský server)
from constants import (
    ROLE_VERIFIED,
    ROLE_ELDER,
    ROLE_CO_LEADER,
    ROLE_LEADER,
    ROLES_STAFF,
)



# ----- parsing intervalu -----
DURATION_RE = re.compile(
    r'^\s*(?:(?P<d>\d+)\s*d)?\s*(?:(?P<h>\d+)\s*h)?\s*(?:(?P<m>\d+)\s*m)?\s*(?:(?P<s>\d+)\s*s)?\s*$',
    re.IGNORECASE
)


def parse_duration_to_seconds(text: str) -> int | None:
    m = DURATION_RE.match(text or "")
    if not m:
        return None
    d = int(m.group("d") or 0)
    h = int(m.group("h") or 0)
    mnt = int(m.group("m") or 0)
    s = int(m.group("s") or 0)
    total = d * 86400 + h * 3600 + mnt * 60 + s
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


# ----- role helpers -----
def has_role(member: discord.Member | None, role_id: int) -> bool:
    return bool(member) and any(r.id == role_id for r in member.roles)


def tier_from_member(member: discord.Member | None) -> str | None:
    """
    Priorita: leader > co_leader > elder > verified > None
    """
    if not member:
        return None
    if has_role(member, ROLE_LEADER):
        return "leader"
    if has_role(member, ROLE_CO_LEADER):
        return "co_leader"
    if has_role(member, ROLE_ELDER):
        return "elder"
    if has_role(member, ROLE_VERIFIED):
        return "verified"
    return None


def tier_limit_seconds(tier: str | None) -> int | None:
    """
    Limity:
      verified -> 1 den
      elder -> 2 dny
      co_leader -> 4 dny
      leader -> bez limitu (None)
      None -> neověřený -> zamítnout dřív
    """
    if tier == "leader":
        return None
    if tier == "co_leader":
        return 4 * 24 * 60 * 60
    if tier == "elder":
        return 2 * 24 * 60 * 60
    if tier == "verified":
        return 1 * 24 * 60 * 60
    return 0  # not verified


class GlobalCommands(commands.Cog):
    """Globální slash příkazy – fungují i v DM a na všech serverech."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- interní: zjisti člena na domovském serveru ----------
    async def get_home_member(self, user_id: int) -> discord.Member | None:
        """
        Zkusí vrátit Membera z domovské guildy (self.bot.config['GUILD_ID']).
        Vrací None, pokud tam uživatel není nebo ho nejde dohledat.
        """
        guild_id = self.bot.config["GUILD_ID"]
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return None

        member = guild.get_member(user_id)
        if member:
            return member
        # zkusíme fetch – vyžaduje, aby uživatel byl v guildě
        try:
            return await guild.fetch_member(user_id)
        except discord.NotFound:
            return None
        except discord.Forbidden:
            return None
        except Exception:
            return None

    # ========== /upozorni_me ==========
    @app_commands.command(
        name="upozorni_me",
        description="Pošlu ti za daný čas soukromou zprávu (např. 1d 1h 1m 1s)."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        interval="Relativní čas (např. '1d 1h 1m 1s').",
        zprava="Volitelná zpráva, kterou ti připomenu."
    )
    async def upozorni_me(self, interaction: Interaction, interval: str, zprava: str | None = None):
        # ✅ Odpovídáme vždy ephemerálně (jen uživatel to uvidí)
        await interaction.response.defer(ephemeral=True, thinking=True)

        user = interaction.user

        # 1) zkus dohledat člena na domovské guildě
        member = await self.get_home_member(user.id)
        tier = tier_from_member(member)

        # 2) gate – musí být alespoň verified
        if tier is None:
            return await interaction.followup.send(
                "⛔ Nejprve se prosím **ověř** na našem serveru.",
                ephemeral=True
            )

        # 3) parse času
        seconds = parse_duration_to_seconds(interval)
        if seconds is None:
            return await interaction.followup.send(
                "❌ Špatný formát času. Příklad: `45m` nebo `1d 2h 30m`.",
                ephemeral=True
            )

        # 4) limit dle tieru
        limit = tier_limit_seconds(tier)
        if limit is not None and seconds > limit:
            return await interaction.followup.send(
                f"⛔ Překročen limit pro tvoji roli. Max: **{humanize_seconds(limit)}**.",
                ephemeral=True
            )

        # 5) potvrzení a naplánování
        await interaction.followup.send(
            f"✅ OK, připomenu ti to za **{humanize_seconds(seconds)}**.",
            ephemeral=True
        )

        async def task():
            try:
                await asyncio.sleep(seconds)
                text = (zprava or "🕑 Tvůj čas právě vypršel!").strip()
                try:
                    # Zkusíme poslat DM
                    await user.send(text)
                except discord.Forbidden:
                    # DM se nepodařilo – zkusíme followup v místě, kde byl příkaz spuštěn
                    try:
                        # Pro jistotu použijeme followup s ephemeral=True
                        await interaction.followup.send(
                            f"⚠️ Nemohu poslat DM. Připomínka: {text}",
                            ephemeral=True
                        )
                    except Exception:
                        # Pokud ani to nejde, už nic neuděláme
                        pass
            except Exception as e:
                print(f"[upozorni_me] Task error: {e}")

        asyncio.create_task(task())

    # ========== /random ==========
    @app_commands.command(
        name="random",
        description="Náhodné číslo (min/max) nebo hod mincí."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        min="Dolní mez (výchozí 1)",
        max="Horní mez (výchozí 6)",
        mince="Zapnout hod mincí místo čísla",
        zverejnit="Zda výsledek ukázat všem (defaultně skryté)"
    )
    async def random_cmd(self, interaction: Interaction, min: int = 1, max: int = 6, mince: bool = False, zverejnit: bool = False):
        # Rozhodneme, zda bude odpověď viditelná všem
        ephemeral = not zverejnit
        await interaction.response.defer(ephemeral=ephemeral, thinking=True)

        user = interaction.user

        # Ověření přes domovskou guildu / DB
        member = await self.get_home_member(user.id)
        tier = tier_from_member(member)

        if tier not in {"leader", "co_leader", "elder", "verified"}:
            # Pokud uživatel chtěl public, ale nemůže, smažeme deferred public msg a pošleme chybu soukromě
            if not ephemeral:
                await interaction.delete_original_response()
                return await interaction.followup.send(
                    "⛔ Tento příkaz je dostupný až po **ověření** na našem serveru.",
                    ephemeral=True
                )
            return await interaction.followup.send(
                "⛔ Tento příkaz je dostupný až po **ověření** na našem serveru.",
                ephemeral=True
            )

        import random
        if mince:
            result = random.choice(["Panna", "Orel"])
            msg = f"Výsledek: **{result}**"
            if zverejnit:
                msg = f"🪙 Hod mincí: **{result}**"
            return await interaction.followup.send(msg, ephemeral=ephemeral)

        if min > max:
            min, max = max, min
        span = max - min
        if span > 10_000_000:
            err_msg = "⛔ Rozsah je příliš velký."
            if not ephemeral:
                 await interaction.delete_original_response()
                 return await interaction.followup.send(err_msg, ephemeral=True)
            return await interaction.followup.send(err_msg, ephemeral=True)

        num = random.randint(min, max)

        if zverejnit:
            # Uživatel chtěl veřejný výsledek -> přidáme info o intervalu
            await interaction.followup.send(f"🎲 Hod ({min}-{max}): **{num}**", ephemeral=False)
        else:
            await interaction.followup.send(f"Výsledek: **{num}**", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GlobalCommands(bot))