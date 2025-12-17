# discord_team_bot_full_uncompressed_fixed.py
# Vollständiger, unkomprimierter Discord-Team-Bot
# WICHTIG: Ersetze BOT_TOKEN durch deinen Bot-Token bevor du startest.
# Tipp: Token NIEMALS öffentlich posten. Wenn du das getan hast, reset the token.

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import datetime
import time
import os
import json
import logging
import re
from typing import Optional, Dict, Any

# ============================
# KONFIGURATION (ANPASSEN)
# ============================
# Security: Do NOT paste your token anywhere public. Replace placeholder below.
BOT_TOKEN = "YOUR_TOKEN"

# Optional: Moderations log channel (set to 0 / None to disable)
MOD_LOG_CHANNEL_ID = 0

# Optional welcome channel
WELCOME_CHANNEL_ID = 0

# Folder for backups and warn imports/exports
BACKUP_FOLDER_PATH = r"C:\Users\USER\Documents\backup"
WARN_FILE = "teamwarn_data.json"
LOG_FILE = "bot_actions.log"

# Role names / defaults
MUTED_ROLE_NAME = "Muted"
TEAMLEADER_ROLE_NAME = "Teamleiter"

# Embed customization
EMBED_COLOR = discord.Color.from_rgb(139, 69, 19)  # SaddleBrown (braun)
TEAM_EMBED_THUMBNAIL = "YOUR_THUMBNAIL"

# Spam & profanity
SPAM_THRESHOLD = 4
SPAM_TIME_WINDOW = 3  # seconds
BLACKLIST = [
    # german insults (user provided). Keep or customize to your needs.
    "arschloch", "wichser", "hurensohn", "fotze", "vollidiot", "depp", "idiot",
    "dummkopf", "vollpfosten", "spast", "opfer", "fick", "hure", "nutte",
    "penner", "schwein", "sau", "spasti", "fresse", "hirnlos", "gehirnverbrannt",
    "knalltüte", "loser", "arschgeige", "drecksack", "lump", "missgeburt",
    "bastard", "bitch", "kanake", "spacko", "schlampe", "drecksau", "fotzensohn",
    "blödian", "ekelpaket", "fettarsch", "fettsack", "hackfresse", "hohlbirne",
    "kotzbrocken", "krüppel", "sackgesicht", "schmarotzer", "schnuller",
    "trottel", "gsindl", "mistkerl", "mistschwein", "sauhund", "schweinehund",
    "nulpe", "rotzlöffel", "stinkstiefel", "ungustl", "vollhonk", "banause",
    "dummrian", "fatzke", "kackbratze", "sacklump"
]

# Warn durations mapping
DURATION_MAP = {
    "1Woche": 7 * 24 * 3600,
    "2Wochen": 14 * 24 * 3600,
    "1Monat": 30 * 24 * 3600,
    "2Monate": 60 * 24 * 3600,
    "7Monate": 210 * 24 * 3600,
    "1Jahr": 365 * 24 * 3600,
    "Unendlich": None
}

# cooldown for warn commands per moderator (in seconds)
WARN_COOLDOWN = 5

# ============================
# Logging config
# ============================
if not os.path.exists(os.path.dirname(LOG_FILE)) and os.path.dirname(LOG_FILE) != "":
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# Console logging also
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# ============================
# Bot & Intents
# ============================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# runtime storage
spam_data: Dict[int, Dict[str, Any]] = {}
warn_cooldowns: Dict[str, float] = {}

# ============================
# Helper: warn file IO
# ============================
def load_warns() -> Dict[str, Any]:
    """Lade die Warn-Datenbank (JSON)."""
    if not os.path.exists(WARN_FILE):
        return {}
    try:
        with open(WARN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            else:
                logging.warning("Warn-Datei enthält kein Dict -> neu initialisiert")
                return {}
    except Exception as e:
        logging.exception("Fehler beim Laden der Warn-Datei")
        return {}

def save_warns(data: Dict[str, Any]) -> None:
    """Speichere Warn-Datenbank (JSON)."""
    try:
        with open(WARN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        logging.exception("Fehler beim Speichern der Warn-Datei")

# ============================
# Embed helpers
# ============================
def make_embed(title: str, description: str, color: Optional[discord.Color] = None) -> discord.Embed:
    c = color if color is not None else EMBED_COLOR
    embed = discord.Embed(title=title, description=description, color=c)
    # thumbnail top-right
    if TEAM_EMBED_THUMBNAIL:
        try:
            embed.set_thumbnail(url=TEAM_EMBED_THUMBNAIL)
        except Exception:
            pass
    embed.set_footer(text="© ZeroV Studios")
    return embed

def team_embed_join(user: discord.Member, role: discord.Role, ping_role: Optional[discord.Role] = None) -> discord.Embed:
    desc = f"Hiermit tritt {user.mention} dem Team als {role.mention} bei.\n\nMit freundlichen Grüßen {ping_role.mention if ping_role else ''}"
    return make_embed("Teambeitritt", desc)

def team_embed_uprank(user: discord.Member, old_role: discord.Role, new_role: discord.Role, reason: Optional[str], ping_role: Optional[discord.Role] = None) -> discord.Embed:
    desc = (f"Hiermit erhält {user.mention} ein Uprank von {old_role.mention} auf {new_role.mention}.\n\n"
            f"{('Grund: ' + reason) if reason else ''}\n\nMit freundlichen Grüßen {ping_role.mention if ping_role else ''}")
    return make_embed("Uprank", desc)

def team_embed_downrank(user: discord.Member, old_role: discord.Role, new_role: discord.Role, reason: Optional[str], ping_role: Optional[discord.Role] = None) -> discord.Embed:
    desc = (f"Hiermit erhält {user.mention} ein Downrank von {old_role.mention} auf {new_role.mention}.\n\n"
            f"{('Grund: ' + reason) if reason else ''}\n\nMit freundlichen Grüßen {ping_role.mention if ping_role else ''}")
    return make_embed("Downrank", desc)

def team_embed_kick(user: discord.Member, reason: Optional[str], ping_role: Optional[discord.Role] = None) -> discord.Embed:
    # Format requested by user:
    # "Hier mit erhält @USERPING einen Team Kick LEHRZEILE Grund LEHRZEILE Danke für deinen Einsatz LEHRZEILE MFG @ROLLENPING"
    desc = (f"Hiermit erhält {user.mention} einen Team Kick\n\n"
            f"Grund: {reason or 'Kein Grund angegeben'}\n\n"
            f"Danke für deinen Einsatz\n\n"
            f"Mit Freundlichen Grüßen {ping_role.mention if ping_role else ''}")
    return make_embed("Team Kick", desc)

def team_embed_warn(user: discord.Member, level: int, reason: Optional[str], ping_role: Optional[discord.Role] = None) -> discord.Embed:
    # requested format:
    # "TEAM WARN. Hiermit erhält @USERPING Sein AUSWÄHLBARE ZAHL 1-3 Warn LEHRZEILE Grund LEHRZEILE MFG @ROLLENPING"
    desc = (f"Hiermit erhält {user.mention} seine {level}. Warnung.\n\n"
            f"Grund: {reason or 'Kein Grund angegeben'}\n\n"
            f"Mit Freundlichen Grüßen {ping_role.mention if ping_role else ''}")
    return make_embed("TEAM WARN", desc)

# ============================
# Mod log helper
# ============================
async def send_mod_log(action_title: str, user_target: discord.abc.User, moderator: discord.Member, reason: Optional[str] = None, channel: Optional[discord.TextChannel] = None):
    logging.info(f"{action_title} | target={getattr(user_target, 'id', user_target)} | by={moderator.id} | reason={reason}")
    if not MOD_LOG_CHANNEL_ID:
        return
    ch = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if not ch:
        logging.warning("MOD_LOG_CHANNEL_ID gesetzt, aber Channel nicht gefunden")
        return
    embed = make_embed(action_title, f"User: {getattr(user_target, 'mention', str(user_target))}\nGrund: {reason or 'Kein Grund angegeben'}\nModerator: {moderator.mention}")
    if channel:
        embed.add_field(name="Kanal", value=channel.mention, inline=False)
    try:
        await ch.send(embed=embed)
    except Exception:
        logging.exception("Fehler beim Senden an Mod-Log Channel")

# ============================
# Permission / hierarchy helpers
# ============================
def bot_can_manage_member(guild: discord.Guild, member: discord.Member) -> bool:
    bot_member = guild.get_member(bot.user.id)
    if bot_member is None or member is None:
        return False
    try:
        return bot_member.top_role.position > member.top_role.position
    except Exception:
        return False

def invoker_can_modify_target(invoker: discord.Member, target: discord.Member) -> bool:
    # disallow self-target
    if invoker == target:
        return False
    try:
        return invoker.top_role.position > target.top_role.position
    except Exception:
        return False

def invoker_warn_permission_level(invoker: discord.Member) -> int:
    """
    Determine maximum warn level invoker can give.
    Return 3 for admin, 2 for teamleader, 1 for manage_roles, 0 otherwise.
    """
    if invoker.guild_permissions.administrator:
        return 3
    for r in invoker.roles:
        if r.name == TEAMLEADER_ROLE_NAME:
            return 2
    if invoker.guild_permissions.manage_roles:
        return 1
    return 0

# ============================
# Events
# ============================
@bot.event
async def on_ready():
    # sync tree commands; tolerate exceptions
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synchronisierte {len(synced)} Commands.")
    except Exception as e:
        logging.exception("Fehler beim Synchronisieren der Commands")
    logging.info(f"Eingeloggt als {bot.user} (ID: {bot.user.id})")
    # start background task
    try:
        check_expired_warns.start()
        logging.info("Background tasks gestartet.")
    except RuntimeError:
        logging.warning("Background tasks bereits gestartet oder fehlerhaft.")

@bot.event
async def on_member_join(member: discord.Member):
    if WELCOME_CHANNEL_ID:
        ch = bot.get_channel(WELCOME_CHANNEL_ID)
        if ch:
            embed = make_embed("Herzlich Willkommen!", f"🎉 {member.mention} ist unserem Server beigetreten! Viel Spaß!")
            try:
                if member.avatar:
                    embed.set_thumbnail(url=member.avatar.url)
            except Exception:
                pass
            try:
                await ch.send(embed=embed)
            except Exception:
                logging.exception("Fehler beim Senden der Willkommensnachricht")

@bot.event
async def on_message(message: discord.Message):
    # avoid processing bots
    if message.author.bot:
        return

    # Link blocker (simple)
    if "http://" in message.content or "https://" in message.content:
        try:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention}, Links sind in diesem Kanal nicht erlaubt!", delete_after=5)
        except discord.Forbidden:
            logging.warning("Keine Berechtigung: Nachricht löschen")
        except Exception:
            logging.exception("Fehler beim Link-Blocker")
        await bot.process_commands(message)
        return

    # profanity filter (naive substring check)
    try:
        content = message.content.lower()
        for bad in BLACKLIST:
            if bad in content:
                # delete and log
                try:
                    await message.delete()
                except discord.Forbidden:
                    await message.channel.send(f"⚠️ {message.author.mention} hat ein Schimpfwort benutzt, aber ich habe nicht die Berechtigung, die Nachricht zu löschen.")
                    await bot.process_commands(message)
                    return

                # try to ban; if cannot, warn in channel
                try:
                    await message.guild.ban(message.author, reason="Beleidigung erkannt.")
                    await send_mod_log("Ban", message.author, bot.user, "Beleidigung erkannt.", channel=message.channel)
                except Exception:
                    try:
                        await message.channel.send(f"⚠️ {message.author.mention} hat ein Schimpfwort benutzt, konnte aber nicht gebannt werden.")
                    except Exception:
                        pass
                await bot.process_commands(message)
                return
    except Exception:
        logging.exception("Fehler beim Profanity-Check")

    # spam protection
    try:
        uid = message.author.id
        now = datetime.datetime.utcnow()
        if uid not in spam_data:
            spam_data[uid] = {"count": 1, "last_time": now, "warned": False}
        else:
            last_time = spam_data[uid]["last_time"]
            dt = (now - last_time).total_seconds()
            if dt < SPAM_TIME_WINDOW:
                spam_data[uid]["count"] += 1
            else:
                spam_data[uid] = {"count": 1, "last_time": now, "warned": False}
            spam_data[uid]["last_time"] = now

        if spam_data[uid]["count"] >= SPAM_THRESHOLD:
            if not spam_data[uid]["warned"]:
                try:
                    await message.channel.send(f"⚠️ {message.author.mention}, bitte spamme nicht! Eine weitere Regelverletzung führt zu einem Timeout.", delete_after=10)
                except Exception:
                    pass
                spam_data[uid]["warned"] = True
                spam_data[uid]["count"] = 0
            else:
                try:
                    until = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                    await message.author.timeout(until)
                    await message.channel.send(f"⚠️ {message.author.mention} wurde für 1 Stunde getimeoutet.", delete_after=10)
                    await send_mod_log("Timeout", message.author, bot.user, "Spam", channel=message.channel)
                    del spam_data[uid]
                except Exception:
                    try:
                        await message.channel.send(f"⚠️ {message.author.mention} hat gespammt, aber ich habe nicht die Berechtigung, den Nutzer zu timeouten.")
                    except Exception:
                        pass
    except Exception:
        logging.exception("Fehler beim Spam-Schutz")

    # allow commands to be processed too
    await bot.process_commands(message)

# ============================
# Moderation / utility slash commands
# ============================

# generic decorator for permission checks to raise app command MissingPermissions properly
def requires_perms(**perms):
    def wrapper(func):
        return app_commands.checks.has_permissions(**perms)(func)
    return wrapper

# KICK
@bot.tree.command(name="kick", description="Kickt einen Nutzer vom Server.")
@requires_perms(kick_members=True)
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben"):
    await interaction.response.defer(ephemeral=True)
    if not bot_can_manage_member(interaction.guild, member):
        return await interaction.followup.send("Ich kann diesen Nutzer nicht kicken (Rollen-Hierarchie).", ephemeral=True)
    try:
        await member.kick(reason=reason)
        await send_mod_log("Kick", member, interaction.user, reason)
        await interaction.followup.send("Kick ausgeführt.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Kicken")
        await interaction.followup.send("Fehler beim Kicken (Berechtigungen?).", ephemeral=True)

# BAN
@bot.tree.command(name="ban", description="Bannt einen Nutzer.")
@requires_perms(ban_members=True)
async def slash_ban(interaction: discord.Interaction, user: str, reason: str = "Kein Grund angegeben"):
    await interaction.response.defer(ephemeral=True)
    # support mention, id or name
    try:
        member = None
        try:
            uid = int(user)
            member = await interaction.guild.fetch_member(uid)
        except Exception:
            m = re.match(r'<@!?(\d+)>', user)
            if m:
                uid = int(m.group(1))
                member = await interaction.guild.fetch_member(uid)
            else:
                member = interaction.guild.get_member_named(user)
        if member:
            if not bot_can_manage_member(interaction.guild, member):
                return await interaction.followup.send("Ich kann diesen Nutzer nicht bannen (Rollen-Hierarchie).", ephemeral=True)
            await interaction.guild.ban(member, reason=reason)
            await send_mod_log("Ban", member, interaction.user, reason)
            await interaction.followup.send("Ban ausgeführt.", ephemeral=True)
        else:
            # try by id
            uid = int(user)
            await interaction.guild.ban(discord.Object(id=uid), reason=reason)
            user_obj = await bot.fetch_user(uid)
            await send_mod_log("Ban (ID)", user_obj, interaction.user, reason)
            await interaction.followup.send("Nutzer-ID gebannt.", ephemeral=True)
    except ValueError:
        await interaction.followup.send("Ungültige User-Angabe.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Bannen")
        await interaction.followup.send("Fehler beim Bannen.", ephemeral=True)

# UNBAN
@bot.tree.command(name="unban", description="Entbannt einen Nutzer.")
@requires_perms(ban_members=True)
async def slash_unban(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer(ephemeral=True)
    try:
        uid = int(user_id)
        user_obj = await bot.fetch_user(uid)
        await interaction.guild.unban(user_obj)
        await send_mod_log("Unban", user_obj, interaction.user, "Entbannung")
        await interaction.followup.send("Unban ausgeführt.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Entbannen")
        await interaction.followup.send("Fehler beim Entbannen.", ephemeral=True)

# CLEAR
@bot.tree.command(name="clear", description="Löscht eine Anzahl Nachrichten.")
@requires_perms(manage_messages=True)
async def slash_clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    try:
        await interaction.channel.purge(limit=amount + 1)
        await send_mod_log("Clear", interaction.user, interaction.user, f"{amount} Nachrichten in {interaction.channel.name}", channel=interaction.channel)
        await interaction.followup.send("Nachrichten gelöscht.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Löschen von Nachrichten")
        await interaction.followup.send("Fehler beim Löschen von Nachrichten.", ephemeral=True)

# TIMEOUT
@bot.tree.command(name="timeout", description="Setzt einen Nutzer in Timeout (z.B. 10m, 1h).")
@requires_perms(moderate_members=True)
async def slash_timeout(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "Kein Grund angegeben"):
    await interaction.response.defer(ephemeral=True)
    if not bot_can_manage_member(interaction.guild, member):
        return await interaction.followup.send("Ich kann diesen Nutzer nicht in den Timeout versetzen.", ephemeral=True)
    try:
        seconds = 0
        if duration.endswith('s'):
            seconds = int(duration[:-1])
        elif duration.endswith('m'):
            seconds = int(duration[:-1]) * 60
        elif duration.endswith('h'):
            seconds = int(duration[:-1]) * 3600
        elif duration.endswith('d'):
            seconds = int(duration[:-1]) * 86400
        else:
            raise ValueError("Ungültige Dauer")
    except Exception:
        return await interaction.followup.send("Ungültige Zeitangabe. Nutze s/m/h/d.", ephemeral=True)

    if seconds <= 0:
        return await interaction.followup.send("Ungültige Zeitangabe.", ephemeral=True)

    try:
        until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
        await member.timeout(until)
        await send_mod_log("Timeout", member, interaction.user, f"Dauer: {duration}. Grund: {reason}")
        await interaction.followup.send("Timeout gesetzt.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Setzen des Timeouts")
        await interaction.followup.send("Fehler beim Setzen des Timeouts.", ephemeral=True)

# USERINFO
@bot.tree.command(name="userinfo", description="Zeigt Informationen über einen Nutzer.")
async def slash_userinfo(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()
    try:
        last_messages_info = ""
        for ch in interaction.guild.text_channels:
            try:
                async for msg in ch.history(limit=50):
                    if msg.author == member:
                        last_messages_info += f"[{ch.mention}]: {msg.content[:50]}...\n"
                        break
            except Exception:
                continue

        desc = "Hier sind einige Details über den Nutzer."
        embed = make_embed(f"Informationen zu {member.display_name}", desc)
        try:
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
        except Exception:
            pass
        embed.add_field(name="Nutzername", value=member.name, inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Beigetreten am", value=member.joined_at.strftime("%d.%m.%Y") if member.joined_at else "Unbekannt", inline=True)
        embed.add_field(name="Account erstellt am", value=member.created_at.strftime("%d.%m.%Y") if member.created_at else "Unbekannt", inline=True)
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        embed.add_field(name="Rollen", value=", ".join(roles) if roles else "Keine", inline=False)
        embed.add_field(name="Letzte Nachrichten (kurz)", value=last_messages_info or "Keine gefunden", inline=False)
        await interaction.followup.send(embed=embed)
    except Exception:
        logging.exception("Fehler in userinfo")
        await interaction.followup.send("Fehler beim Abrufen der Nutzerinfo.", ephemeral=True)

# LOCK / UNLOCK
@bot.tree.command(name="lock", description="Sperrt einen Kanal.")
@requires_perms(manage_channels=True)
async def slash_lock(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None, reason: str = "Kein Grund angegeben"):
    await interaction.response.defer(ephemeral=True)
    channel = channel or interaction.channel
    try:
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        if overwrite.send_messages is False:
            return await interaction.followup.send("Kanal ist bereits gesperrt.", ephemeral=True)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)
        await send_mod_log("Lock", interaction.user, interaction.user, reason, channel=channel)
        await interaction.followup.send("Kanal gesperrt.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Sperren des Kanals")
        await interaction.followup.send("Fehler beim Sperren des Kanals.", ephemeral=True)

@bot.tree.command(name="unlock", description="Entsperrt einen Kanal.")
@requires_perms(manage_channels=True)
async def slash_unlock(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None, reason: str = "Kein Grund angegeben"):
    await interaction.response.defer(ephemeral=True)
    channel = channel or interaction.channel
    try:
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        if overwrite.send_messages is None or overwrite.send_messages is True:
            return await interaction.followup.send("Kanal ist bereits entsperrt.", ephemeral=True)
        overwrite.send_messages = True
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)
        await send_mod_log("Unlock", interaction.user, interaction.user, reason, channel=channel)
        await interaction.followup.send("Kanal entsperrt.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Entsperren des Kanals")
        await interaction.followup.send("Fehler beim Entsperren des Kanals.", ephemeral=True)

# SLOWMODE
@bot.tree.command(name="slowmode", description="Setzt Slowmode für Kanal (0 zum deaktivieren).")
@requires_perms(manage_channels=True)
async def slash_slowmode(interaction: discord.Interaction, seconds: int, channel: Optional[discord.TextChannel] = None):
    await interaction.response.defer(ephemeral=True)
    channel = channel or interaction.channel
    if not (0 <= seconds <= 21600):
        return await interaction.followup.send("Slowmode muss 0-21600 Sekunden sein.", ephemeral=True)
    try:
        await channel.edit(slowmode_delay=seconds)
        await send_mod_log("Slowmode", interaction.user, interaction.user, f"{seconds} Sekunden", channel=channel)
        await interaction.followup.send("Slowmode gesetzt.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Setzen des Slowmode")
        await interaction.followup.send("Fehler beim Setzen des Slowmode.", ephemeral=True)

# ROLE add/remove
@bot.tree.command(name="role", description="Weist eine Rolle zu oder entfernt sie.")
@requires_perms(manage_roles=True)
async def slash_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role, action: str):
    await interaction.response.defer(ephemeral=True)
    action = action.lower()
    try:
        if action not in ["add", "remove"]:
            return await interaction.followup.send("Aktion muss 'add' oder 'remove' sein.", ephemeral=True)
        if not bot_can_manage_member(interaction.guild, member):
            return await interaction.followup.send("Ich kann diese Rolle nicht verwalten (Rollen-Hierarchie).", ephemeral=True)
        if action == "add":
            if role in member.roles:
                return await interaction.followup.send("Nutzer hat die Rolle bereits.", ephemeral=True)
            await member.add_roles(role)
            await send_mod_log("Rolle hinzugefügt", member, interaction.user, f"Rolle: {role.name}")
            await interaction.followup.send("Rolle hinzugefügt.", ephemeral=True)
        else:
            if role not in member.roles:
                return await interaction.followup.send("Nutzer hat die Rolle nicht.", ephemeral=True)
            await member.remove_roles(role)
            await send_mod_log("Rolle entfernt", member, interaction.user, f"Rolle: {role.name}")
            await interaction.followup.send("Rolle entfernt.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Verwalten der Rolle")
        await interaction.followup.send("Fehler beim Verwalten der Rolle.", ephemeral=True)

# AVATAR
@bot.tree.command(name="avatar", description="Zeigt Avatar eines Nutzers.")
async def slash_avatar(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    await interaction.response.defer()
    member = member or interaction.user
    try:
        embed = make_embed(f"Avatar von {member.display_name}", "")
        if member.avatar:
            embed.set_image(url=member.avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception:
        logging.exception("Fehler bei avatar command")
        await interaction.followup.send("Fehler beim Abrufen des Avatars.", ephemeral=True)

# NICK
@bot.tree.command(name="nick", description="Ändert den Spitznamen eines Nutzers.")
@requires_perms(manage_nicknames=True)
async def slash_nick(interaction: discord.Interaction, member: discord.Member, new_nick: str):
    await interaction.response.defer(ephemeral=True)
    try:
        if not bot_can_manage_member(interaction.guild, member):
            return await interaction.followup.send("Ich kann diesen Spitznamen nicht ändern (Rollen-Hierarchie).", ephemeral=True)
        await member.edit(nick=new_nick)
        await send_mod_log("Nickname geändert", member, interaction.user, f"Neuer Nick: {new_nick}")
        await interaction.followup.send("Nickname geändert.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Ändern des Nicknames")
        await interaction.followup.send("Fehler beim Ändern des Nicknames.", ephemeral=True)

# MUTE / UNMUTE
@bot.tree.command(name="mute", description="Stummschaltet einen Nutzer.")
@requires_perms(manage_roles=True)
async def slash_mute(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben"):
    await interaction.response.defer(ephemeral=True)
    try:
        if not bot_can_manage_member(interaction.guild, member):
            return await interaction.followup.send("Ich kann diesen Nutzer nicht stummschalten.", ephemeral=True)
        muted_role = discord.utils.get(interaction.guild.roles, name=MUTED_ROLE_NAME)
        if not muted_role:
            muted_role = await interaction.guild.create_role(name=MUTED_ROLE_NAME)
            for ch in interaction.guild.channels:
                try:
                    await ch.set_permissions(muted_role, send_messages=False, speak=False)
                except Exception:
                    continue
        if muted_role in member.roles:
            return await interaction.followup.send("User ist bereits stummgeschaltet.", ephemeral=True)
        await member.add_roles(muted_role, reason=reason)
        await send_mod_log("Mute", member, interaction.user, reason)
        await interaction.followup.send("User stummgeschaltet.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Stummschalten")
        await interaction.followup.send("Fehler beim Stummschalten.", ephemeral=True)

@bot.tree.command(name="unmute", description="Entfernt Stummschaltung.")
@requires_perms(manage_roles=True)
async def slash_unmute(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben"):
    await interaction.response.defer(ephemeral=True)
    try:
        muted_role = discord.utils.get(interaction.guild.roles, name=MUTED_ROLE_NAME)
        if not muted_role or muted_role not in member.roles:
            return await interaction.followup.send("User ist nicht stummgeschaltet.", ephemeral=True)
        await member.remove_roles(muted_role, reason=reason)
        await send_mod_log("Unmute", member, interaction.user, reason)
        await interaction.followup.send("User entstummt.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Entstummen")
        await interaction.followup.send("Fehler beim Entstummen.", ephemeral=True)

# ============================
# Backup / Restore / Import / Export
# ============================

@bot.tree.command(name="backup", description="Erstellt ein JSON-Backup des Servers.")
@requires_perms(administrator=True)
async def slash_backup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        if not os.path.exists(BACKUP_FOLDER_PATH):
            os.makedirs(BACKUP_FOLDER_PATH, exist_ok=True)
        guild = interaction.guild
        data = {
            "name": guild.name,
            "id": str(guild.id),
            "date": str(datetime.datetime.utcnow()),
            "roles": [{"name": r.name, "permissions": r.permissions.value, "color": getattr(r.color, "value", 0), "position": r.position} for r in guild.roles],
            "channels": [{"name": c.name, "type": str(c.type), "category_id": str(c.category_id) if c.category else None, "position": c.position} for c in guild.channels]
        }
        filename = f"{guild.name}_backup_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        path = os.path.join(BACKUP_FOLDER_PATH, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        await interaction.followup.send(f"Backup erstellt: `{path}`", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Erstellen des Backups")
        await interaction.followup.send("Fehler beim Backup erstellen.", ephemeral=True)

@bot.tree.command(name="restore", description="Analysiert ein Backup (keine automatische Wiederherstellung).")
@requires_perms(administrator=True)
async def slash_restore(interaction: discord.Interaction, filename: str):
    await interaction.response.defer(ephemeral=True)
    path = os.path.join(BACKUP_FOLDER_PATH, filename)
    if not os.path.exists(path):
        return await interaction.followup.send("Backup-Datei nicht gefunden.", ephemeral=True)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        roles = data.get("roles", [])
        channels = data.get("channels", [])
        await interaction.followup.send(f"Backup geladen: {len(roles)} Rollen, {len(channels)} Kanäle. (Keine automatische Wiederherstellung.)", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Lesen des Backups")
        await interaction.followup.send("Fehler beim Laden des Backups.", ephemeral=True)

@bot.tree.command(name="export_warns", description="Gibt Pfad zur Warn-Datei zurück (Admin).")
@requires_perms(administrator=True)
async def cmd_export_warns(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        if not os.path.exists(WARN_FILE):
            return await interaction.followup.send("Keine Warn-Datei vorhanden.", ephemeral=True)
        await interaction.followup.send(f"Warn-Datei: `{os.path.abspath(WARN_FILE)}`", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Export")
        await interaction.followup.send("Fehler beim Export.", ephemeral=True)

@bot.tree.command(name="import_warns", description="Importiert Warn-JSON aus Backup-Ordner (Admin).")
@requires_perms(administrator=True)
async def cmd_import_warns(interaction: discord.Interaction, filename: str):
    await interaction.response.defer(ephemeral=True)
    path = os.path.join(BACKUP_FOLDER_PATH, filename)
    if not os.path.exists(path):
        return await interaction.followup.send("Datei nicht gefunden.", ephemeral=True)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        save_warns(data)
        await interaction.followup.send("Warns importiert.", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Importieren")
        await interaction.followup.send("Fehler beim Import.", ephemeral=True)

@bot.tree.command(name="shutdown", description="Fährt den Bot herunter (Admin).")
@requires_perms(administrator=True)
async def cmd_shutdown(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        await interaction.followup.send("Bot wird heruntergefahren.", ephemeral=True)
    except Exception:
        pass
    logging.info("Shutdown durch Admin ausgelöst.")
    await bot.close()

# ============================
# Team Commands (join, uprank, downrank, kick_von_team)
# ============================

@bot.tree.command(name="join_team", description="Fügt einen Nutzer einem Team hinzu (Rolle).")
@requires_perms(manage_roles=True)
async def cmd_join_team(interaction: discord.Interaction, member: discord.Member, team_role: discord.Role, ping_role: Optional[discord.Role] = None):
    await interaction.response.defer()
    try:
        if not bot_can_manage_member(interaction.guild, member):
            return await interaction.followup.send("Ich kann die Rolle dieses Nutzers nicht verwalten.", ephemeral=True)
        if team_role in member.roles:
            return await interaction.followup.send(f"{member.mention} hat die Rolle bereits.", ephemeral=True)
        if not invoker_can_modify_target(interaction.user, member):
            return await interaction.followup.send("Du kannst diesen Nutzer nicht dem Team hinzufügen (Rang/Hierarchie).", ephemeral=True)
        await member.add_roles(team_role)
        embed = team_embed_join(member, team_role, ping_role)
        await interaction.followup.send(embed=embed)
        await send_mod_log("Teambeitritt", member, interaction.user, f"Rolle: {team_role.name}")
    except Exception:
        logging.exception("Fehler beim Teambeitritt")
        await interaction.followup.send("Fehler beim Hinzufügen der Rolle.", ephemeral=True)

@bot.tree.command(name="uprank_member", description="Befördert einen Nutzer im Team.")
@requires_perms(manage_roles=True)
async def cmd_uprank_member(interaction: discord.Interaction, member: discord.Member, old_role: discord.Role, new_role: discord.Role, reason: str, ping_role: Optional[discord.Role] = None):
    await interaction.response.defer()
    try:
        if not bot_can_manage_member(interaction.guild, member):
            return await interaction.followup.send("Ich kann die Rollen dieses Nutzers nicht verwalten.", ephemeral=True)
        if not invoker_can_modify_target(interaction.user, member):
            return await interaction.followup.send("Du kannst diesen Nutzer nicht upranken (Rang/Hierarchie).", ephemeral=True)
        if old_role in member.roles:
            await member.remove_roles(old_role)
        await member.add_roles(new_role)
        embed = team_embed_uprank(member, old_role, new_role, reason, ping_role)
        await interaction.followup.send(embed=embed)
        await send_mod_log("Uprank", member, interaction.user, f"{old_role.name} -> {new_role.name}. Grund: {reason}")
    except Exception:
        logging.exception("Fehler beim Uprank")
        await interaction.followup.send("Fehler beim Uprank.", ephemeral=True)

@bot.tree.command(name="downrank_member", description="Degradiert einen Nutzer im Team.")
@requires_perms(manage_roles=True)
async def cmd_downrank_member(interaction: discord.Interaction, member: discord.Member, old_role: discord.Role, new_role: discord.Role, reason: str, ping_role: Optional[discord.Role] = None):
    await interaction.response.defer()
    try:
        if not bot_can_manage_member(interaction.guild, member):
            return await interaction.followup.send("Ich kann die Rollen dieses Nutzers nicht verwalten.", ephemeral=True)
        if not invoker_can_modify_target(interaction.user, member):
            return await interaction.followup.send("Du kannst diesen Nutzer nicht downranken (Rang/Hierarchie).", ephemeral=True)
        if old_role in member.roles:
            await member.remove_roles(old_role)
        await member.add_roles(new_role)
        embed = team_embed_downrank(member, old_role, new_role, reason, ping_role)
        await interaction.followup.send(embed=embed)
        await send_mod_log("Downrank", member, interaction.user, f"{old_role.name} -> {new_role.name}. Grund: {reason}")
    except Exception:
        logging.exception("Fehler beim Downrank")
        await interaction.followup.send("Fehler beim Downrank.", ephemeral=True)

@bot.tree.command(name="kick_from_team", description="Entfernt einen Nutzer aus dem Team (Rolle entfernt).")
@requires_perms(manage_roles=True)
async def cmd_kick_from_team(interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str, ping_role: Optional[discord.Role] = None):
    await interaction.response.defer()
    try:
        if not bot_can_manage_member(interaction.guild, member):
            return await interaction.followup.send("Ich kann die Rolle dieses Nutzers nicht verwalten.", ephemeral=True)
        if not invoker_can_modify_target(interaction.user, member):
            return await interaction.followup.send("Du kannst diesen Nutzer nicht aus dem Team entfernen (Rang/Hierarchie).", ephemeral=True)
        if role in member.roles:
            await member.remove_roles(role)
        embed = team_embed_kick(member, reason, ping_role)
        await interaction.followup.send(embed=embed)
        await send_mod_log("Teamkick", member, interaction.user, f"Rolle: {role.name}. Grund: {reason}")
    except Exception:
        logging.exception("Fehler beim Teamkick")
        await interaction.followup.send("Fehler beim Entfernen aus dem Team.", ephemeral=True)

# ============================
# TeamWarn System (1-3) + Warnlist + Unwarn
# ============================

@bot.tree.command(name="teamwarn", description="Verwarnt ein Teammitglied (Level 1-3).")
@requires_perms(manage_roles=True)
async def cmd_teamwarn(interaction: discord.Interaction, member: discord.Member, warn_level: int, warn_role: discord.Role, dauer: str, reason: str, ping_role: Optional[discord.Role] = None):
    await interaction.response.defer()
    try:
        invoker = interaction.user
        # basic validations
        if warn_level not in [1, 2, 3]:
            return await interaction.followup.send("Warnlevel muss 1, 2 oder 3 sein.", ephemeral=True)
        if invoker == member:
            return await interaction.followup.send("Du kannst dich nicht selbst warnen.", ephemeral=True)
        if not invoker_can_modify_target(invoker, member):
            return await interaction.followup.send("Du kannst diesen Nutzer nicht warnen (Rang/Hierarchie).", ephemeral=True)

        # permission level checks
        max_allowed = invoker_warn_permission_level(invoker)
        if max_allowed == 0:
            return await interaction.followup.send("Du hast keine Berechtigung, Warns zu vergeben.", ephemeral=True)
        if warn_level > max_allowed:
            return await interaction.followup.send(f"Du darfst nur Warn-Level bis {max_allowed} vergeben.", ephemeral=True)

        # cooldown
        now_ts = time.time()
        last = warn_cooldowns.get(str(invoker.id), 0)
        if now_ts - last < WARN_COOLDOWN:
            return await interaction.followup.send(f"Bitte warte {int(WARN_COOLDOWN - (now_ts-last))} Sekunden, bevor du erneut warnst.", ephemeral=True)

        # duration
        if dauer not in DURATION_MAP:
            return await interaction.followup.send("Ungültige Dauer! Wähle: " + ", ".join(DURATION_MAP.keys()), ephemeral=True)
        expires_at = None if DURATION_MAP[dauer] is None else time.time() + DURATION_MAP[dauer]

        warns = load_warns()
        uid = str(member.id)

        # duplicate protection: if same level exists, block
        existing = warns.get(uid)
        if existing and existing.get("warn_level") == warn_level:
            return await interaction.followup.send("Der Nutzer hat bereits diese Warnstufe aktiv.", ephemeral=True)

        warns[uid] = {
            "warn_level": warn_level,
            "expires_at": expires_at,
            "role_id": warn_role.id,
            "set_by": invoker.id,
            "set_at": time.time(),
            "reason": reason
        }
        save_warns(warns)

        # attach role
        try:
            await member.add_roles(warn_role)
        except Exception:
            logging.exception("Fehler beim Hinzufügen der Warnrolle")
            return await interaction.followup.send("Ich habe keine Berechtigung, die Warnrolle zu vergeben.", ephemeral=True)

        warn_cooldowns[str(invoker.id)] = now_ts

        embed = team_embed_warn(member, warn_level, reason, ping_role)
        await interaction.followup.send(embed=embed)
        await send_mod_log("Teamwarn", member, invoker, f"Warn {warn_level}, Dauer {dauer}, Grund: {reason}")
    except Exception:
        logging.exception("Fehler beim Teamwarn")
        await interaction.followup.send("Fehler beim Ausführen des Teamwarns.", ephemeral=True)

@bot.tree.command(name="warnlist", description="Zeigt Warns eines Nutzers an.")
async def cmd_warnlist(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    try:
        warns = load_warns()
        data = warns.get(str(member.id))
        if not data:
            return await interaction.followup.send(f"{member.mention} hat keine aktiven Warnungen.", ephemeral=True)
        role = interaction.guild.get_role(data.get("role_id")) if data.get("role_id") else None
        expires_at = data.get("expires_at")
        expires_str = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(expires_at)) if expires_at else "Unendlich"
        embed = make_embed(f"Warnliste: {member.display_name}", "")
        embed.add_field(name="Warnlevel", value=str(data.get("warn_level")), inline=False)
        embed.add_field(name="Warnrolle", value=role.mention if role else "Nicht gefunden", inline=False)
        embed.add_field(name="Läuft ab am", value=expires_str, inline=False)
        embed.add_field(name="Grund", value=data.get("reason", "Kein Grund angegeben"), inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception:
        logging.exception("Fehler bei warnlist")
        await interaction.followup.send("Fehler beim Abrufen der Warnliste.", ephemeral=True)

@bot.tree.command(name="unwarn", description="Entfernt Warn und Warnrolle von Nutzer.")
@requires_perms(manage_roles=True)
async def cmd_unwarn(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    try:
        warns = load_warns()
        uid = str(member.id)
        if uid not in warns:
            return await interaction.followup.send(f"{member.mention} hat keine Warnen.", ephemeral=True)
        data = warns[uid]
        role_id = data.get("role_id")
        role = interaction.guild.get_role(role_id) if role_id else None
        try:
            if role and role in member.roles:
                await member.remove_roles(role)
        except Exception:
            logging.exception("Fehler beim Entfernen der Warnrolle")
            return await interaction.followup.send("Ich habe nicht die Berechtigung, die Warnrolle zu entfernen.", ephemeral=True)
        del warns[uid]
        save_warns(warns)
        await interaction.followup.send(f"Warn von {member.mention} wurde entfernt.", ephemeral=True)
        await send_mod_log("Unwarn", member, interaction.user, "Warn entfernt")
    except Exception:
        logging.exception("Fehler beim Unwarn")
        await interaction.followup.send("Fehler beim Entfernen der Warn.", ephemeral=True)

# ============================
# Background task: remove expired warns
# ============================
@tasks.loop(minutes=1)
async def check_expired_warns():
    try:
        warns = load_warns()
        changed = False
        now_ts = time.time()
        for uid, data in list(warns.items()):
            expires_at = data.get("expires_at")
            role_id = data.get("role_id")
            if expires_at is None:
                continue
            if now_ts > expires_at:
                # iterate guilds to remove role correctly
                for g in bot.guilds:
                    member = g.get_member(int(uid))
                    role = g.get_role(int(role_id)) if role_id else None
                    if member and role and role in member.roles:
                        try:
                            await member.remove_roles(role)
                        except Exception:
                            logging.exception("Fehler beim Entfernen abgelaufener Warnrolle")
                del warns[uid]
                changed = True
        if changed:
            save_warns(warns)
    except Exception:
        logging.exception("Fehler in check_expired_warns")

# ============================
# App command error handler
# ============================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    try:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Du hast nicht die nötigen Berechtigungen.", ephemeral=True)
        else:
            logging.exception("Fehler bei Slash-Command")
            # use response or followup depending on state
            if interaction.response.is_done():
                await interaction.followup.send(f"Ein Fehler ist aufgetreten: {error}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Ein Fehler ist aufgetreten: {error}", ephemeral=True)
    except Exception:
        logging.exception("Fehler beim Senden der Error-Response")

# ============================
# Start Bot
# ============================
if __name__ == "__main__":
    # quick safety check
    if BOT_TOKEN == "REPLACE_WITH_YOUR_TOKEN" or not BOT_TOKEN:
        print("WARNUNG: Du hast kein gültiges BOT_TOKEN gesetzt. Ersetze BOT_TOKEN in diesem Skript durch dein Token.")
    else:
        logging.info("Starte Bot...")
        bot.run(BOT_TOKEN)
