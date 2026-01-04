import asyncio
import os
import re
import urllib.parse
import discord
from discord import app_commands, Interaction
from discord.ext import commands

# ROLE IDs z constants (domovský server)
from constants import (
    ROLE_VERIFIED,
    ROLE_ELDER,
    ROLE_CO_LEADER,
    ROLE_LEADER,
    ROLE_LEADER,
    ROLES_STAFF,
)
import media_downloader
import web_server
import time



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
        self.url_cooldowns = {}  # user_id -> timestamp (kdy byl příkaz naposledy použit)

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
        skryt="Zda výsledek skrýt (defaultně viditelné všem)"
    )
    async def random_cmd(self, interaction: Interaction, min: int = 1, max: int = 6, mince: bool = False, skryt: bool = False):
        # Rozhodneme, zda bude odpověď viditelná všem
        ephemeral = skryt
        await interaction.response.defer(ephemeral=ephemeral, thinking=True)

        user = interaction.user


        import random
        if mince:
            result = random.choice(["Panna", "Orel"])
            msg = f"Výsledek: **{result}**"
            if not skryt:
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

        if not skryt:
            # Uživatel chtěl veřejný výsledek -> přidáme info o intervalu
            await interaction.followup.send(f"🎲 Hod ({min}-{max}): **{num}**", ephemeral=False)
        else:
            await interaction.followup.send(f"Výsledek: **{num}**", ephemeral=True)

    # ========== /utility Group ==========
    utility_group = app_commands.Group(name="utility", description="Užitečné nástroje (stahování atd.)")

    @utility_group.command(
        name="download",
        description="Stáhne video z URL a pošle ho (s možností statistik)."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        url="Odkaz na video (TikTok, YouTube, Instagram...)",
        statistika="Zobrazit statistiky videa? (Default: Vypnuto)",
        skryt="Pokud zapnuto, video i statistiky uvidíš jen ty (Ephemeral).",
        original="Přidat odkaz na originální video do embedu?"
    )
    @app_commands.choices(statistika=[
        app_commands.Choice(name="Vypnuto", value="off"),
        app_commands.Choice(name="Zapnuto (Veřejné)", value="public"),
        app_commands.Choice(name="Zapnuto (Jen pro mě)", value="private"),
    ])
    async def download_cmd(self, interaction: Interaction, url: str, statistika: str = "off", skryt: bool = False, original: bool = False):
        # 0) Okamžitý defer, aby nedošlo k timeoutu (Unknown Interaction)
        defer_ephemeral = skryt
        await interaction.response.defer(ephemeral=skryt, thinking=True)

        user_id = interaction.user.id
        now = time.time()

        # 1) Zjistíme cooldown limit dle role
        member = await self.get_home_member(user_id)
        tier = tier_from_member(member)
        
        if tier == "leader":
            limit = 0
        elif tier == "co_leader":
            limit = 2 * 60
        elif tier == "elder":
            limit = 6 * 60
        else:
            limit = 30 * 60
            
        # 2) Check cooldown
        last_used = self.url_cooldowns.get(user_id, 0)
        
        if limit > 0 and (now - last_used) < limit:
            remaining = int(limit - (now - last_used))
            m, s = divmod(remaining, 60)
            await interaction.followup.send(
                f"⏳ Musíš počkat ještě **{m}m {s}s** před dalším stažením.",
                ephemeral=True
            )
            return

        # Uložíme čas použití
        self.url_cooldowns[user_id] = now

        progress_info = {'status': 'starting', 'percent': 0, 'eta': None}
        progress_msg = None 
        
        try:
            loop = asyncio.get_running_loop()
            
            # --- Progress Task ---
            task = loop.run_in_executor(None, media_downloader.download_media, url, progress_info)
            start_time = time.time()
            
            while not task.done():
                try:
                    await asyncio.wait([task], timeout=2.0)
                except Exception:
                    pass
                
                elapsed = time.time() - start_time
                # Show progress if it takes longer than 3s (responsiveness)
                if not task.done() and elapsed > 3:
                    eta = progress_info.get('eta')
                    percent = progress_info.get('percent', 0)
                    status_text = "stahování..."
                    
                    if progress_info.get('status') == 'processing':
                         status_text = "zpracování..."
                         eta_str = "??"
                    else:
                         if eta:
                             m, s = divmod(int(eta), 60)
                             eta_str = f"{m}m {s}s"
                         else:
                             eta_str = "??"
                    
                    msg_content = f"⏳ **Stahování**: {percent:.1f}% | ETA: **{eta_str}** | {status_text}"
                    
                    try:
                        if progress_msg is None:
                             progress_msg = await interaction.followup.send(msg_content, ephemeral=True)
                        else:
                             await progress_msg.edit(content=msg_content)
                    except Exception:
                         pass

            result = await task
            # ---------------------

        except Exception as e:
            await interaction.followup.send(f"❌ Chyba při spouštění stahování: {str(e)}", ephemeral=True)
            return

        if "error" in result:
            if progress_msg:
                await progress_msg.delete()
            await interaction.followup.send(f"❌ Chyba při stahování: {result['error']}", ephemeral=True)
            return

        # --- Embed Construction ---
        title_text = result.get('title', '?')
        uploader_text = result.get('uploader', '?')
        
        description_text = f"Name: **{title_text}**\nAutor: **{uploader_text}**"
        
        if original:
             description_text += f"\nOriginal: [Odkaz]({url})"
        
        embed = discord.Embed(description=description_text, color=discord.Color.orange())
        embed.set_author(name="Media downloader", icon_url=self.bot.user.display_avatar.url)
        
        res = result.get('resolution', '?')
        dur = result.get('duration', 0)
        mins, secs = divmod(dur, 60)
        dur_str = f"{int(mins)}:{int(secs):02d}"
        size_mb = result.get('filesize_mb', 0)
        
        footer_text = f"{res} | {dur_str} | {size_mb} MB"
        
        if statistika != "off":
            embed.set_footer(text=footer_text)
        
        
        SAFE_LIMIT_MB = 2000 
        filesize = result.get('filesize_mb', 0)
        filename = result['filename']
        
        
        # Helper for sending with token expiration fallback
        async def robust_send(content=None, embed=None, file_path=None, ephemeral=False):
            # Create file object if needed
            file_obj = discord.File(file_path) if file_path else None
            try:
                await interaction.followup.send(content=content, embed=embed, file=file_obj, ephemeral=ephemeral)
            except (discord.NotFound, discord.HTTPException) as e:
                # 50027 = Invalid Webhook Token, 10062 = Unknown Interaction
                # 404 = Not Found (webhook deleted or expired)
                is_auth_error = isinstance(e, discord.HTTPException) and e.code == 50027
                is_not_found = isinstance(e, discord.NotFound) or (isinstance(e, discord.HTTPException) and e.status == 404)
                
                if is_auth_error or is_not_found:
                    # Token expired or interaction lost.
                    # Recreate file object for fallback because previous attempt might have closed it
                    if file_path:
                        file_obj = discord.File(file_path)
                    
                    if ephemeral:
                        # Fallback to DM
                        try:
                            await interaction.user.send(content=content, embed=embed, file=file_obj)
                            # Only send warning text if we just sent something
                            await interaction.user.send("⚠️ Interakce vypršela (limit 15 min), posílám výsledek do DM.")
                        except Exception as dm_error:
                            print(f"❌ Nepodařilo se poslat DM po vypršení tokenu: {dm_error}")
                    else:
                        # Fallback to Channel
                        if interaction.channel:
                             permission_check = interaction.channel.permissions_for(interaction.guild.me)
                             if permission_check.send_messages:
                                 await interaction.channel.send(content=content, embed=embed, file=file_obj)
                             else:
                                 print("❌ Nemám práva psát do kanálu po vypršení tokenu.")
                else:
                    # Re-raise other errors (like 413 Entity Too Large)
                    raise e
                    
        # Helper to force web upload
        async def do_web_host_flow():
            if progress_msg:
                 try:
                    await progress_msg.edit(content="⏳ **Nahrávám na webserver...**")
                 except:
                    pass

            key = await web_server.add_file(filename)
            safe_filename = urllib.parse.quote(os.path.basename(filename))
            base_url = "https://discordvids.420013.xyz"
            page_url = f"{base_url}/videa-z-discordu/{key}"
            direct_url = f"{base_url}/download/{key}/{safe_filename}"
            

            embed.description += f"\n\n[Zobrazit stránku ke stažení]({page_url})"
            if statistika != "off":
                 embed.set_footer(text=f"{footer_text} | ⚠️ >Limit")
            else:
                 embed.set_footer(text="⚠️ >Limit")

            if skryt:
                await robust_send(embed=embed, ephemeral=True)
                await robust_send(content=f"**Přímý odkaz:**\n{direct_url}", ephemeral=True)
            else:
                embed_is_public = (statistika == "public")
                if not embed_is_public:
                    await robust_send(embed=embed, ephemeral=True)
                else:
                    await robust_send(embed=embed, ephemeral=False)
                await robust_send(content=direct_url, ephemeral=False)

        try:
            if filesize > SAFE_LIMIT_MB:
                 await do_web_host_flow()
            else:
                # Update progress info for Uploading
                if progress_msg:
                    try:
                        await progress_msg.edit(content="📤 **Nahrávám na Discord...** (to může chvíli trvat)")
                    except:
                        pass
                
                # --- Presentation Logic ---
                if skryt:
                     await robust_send(file_path=filename, embed=embed, ephemeral=True)
                else:
                     if statistika == "off" and not original:
                          await robust_send(file_path=filename, ephemeral=False)
                     elif statistika == "public" or original:
                          await robust_send(file_path=filename, embed=embed, ephemeral=False)
                     elif statistika == "private":
                          await robust_send(file_path=filename, ephemeral=False)
                          await robust_send(embed=embed, ephemeral=True)
                     else:
                          await robust_send(file_path=filename, ephemeral=False)

        except discord.HTTPException as e:
            if e.status == 413 or e.code == 40005:
                # File too large fallback
                if progress_msg:
                    try:
                        await progress_msg.edit(content="⚠️ Soubor je moc velký na Discord, nahrávám na web...")
                    except:
                        pass 
                await do_web_host_flow()
            else:
                try:
                    await interaction.followup.send(f"❌ Chyba při odesílání na Discord: {e}", ephemeral=True)
                except:
                    print(f"❌ Chyba odesílání (token exp?): {e}")
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Obecná chyba: {e}", ephemeral=True)
            except:
                print(f"❌ Obecná chyba (token exp?): {e}")
        finally:
            if progress_msg:
                try:
                    await progress_msg.delete()
                except:
                    pass
            
            is_hosted = False
            for k, v in web_server.file_storage.items():
                if v['filename'] == os.path.basename(filename):
                    is_hosted = True
                    break
            
            if not is_hosted and filesize <= SAFE_LIMIT_MB:
                 media_downloader.delete_file(filename)


async def setup(bot: commands.Bot):
    await bot.add_cog(GlobalCommands(bot))