import asyncio
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

from utilities.autocomplete.banned_users_choices import get_banned_users
from utilities.global_vars import bot, wall_e_config
from utilities.paginate import paginate_embed
from wall_e_models.customFields import pstdatetime

from wall_e_models.models import BanRecord

from utilities.embed import embed, WallEColour
from utilities.file_uploading import start_file_uploading
from utilities.setup_logger import Loggers

BanAction = discord.AuditLogAction.ban
DEFAULT_REASON = "Broke the rules."


class Ban(commands.Cog):

    ban_list = {}

    def __init__(self):
        log_info = Loggers.get_logger(logger_name="Ban")
        self.logger = log_info[0]
        self.debug_log_file_absolute_path = log_info[1]
        self.warn_log_file_absolute_path = log_info[2]
        self.error_log_file_absolute_path = log_info[3]
        self.logger.info("[Ban __init__()] initializing Ban")
        self.mod_channel = None
        self.bot_management_channel = None
        self.guild: discord.Guild | None = None
        self.processing = []

    @commands.Cog.listener(name="on_ready")
    async def get_guild(self):
        self.guild = bot.guilds[0]

    @commands.Cog.listener(name="on_ready")
    async def upload_debug_logs(self):
        while self.guild is None:
            await asyncio.sleep(2)
        await start_file_uploading(
            self.logger, self.guild, bot, wall_e_config, self.debug_log_file_absolute_path, "ban_debug"
        )

    @commands.Cog.listener(name="on_ready")
    async def upload_warn_logs(self):
        while self.guild is None:
            await asyncio.sleep(2)
        await start_file_uploading(
            self.logger, self.guild, bot, wall_e_config, self.warn_log_file_absolute_path, "ban_warn"
        )

    @commands.Cog.listener(name="on_ready")
    async def upload_error_logs(self):
        while self.guild is None:
            await asyncio.sleep(2)
        await start_file_uploading(
            self.logger, self.guild, bot, wall_e_config, self.error_log_file_absolute_path, "ban_error"
        )

    @commands.Cog.listener(name='on_ready')
    async def load(self):
        while self.guild is None:
            await asyncio.sleep(2)
        self.logger.info('[Ban load()] loading mod_channel and ban_list')
        mod_channel_id = await bot.bot_channel_manager.create_or_get_channel_id(
            self.logger, self.guild, wall_e_config.get_config_value('basic_config', 'ENVIRONMENT'),
            "ban"
        )
        self.mod_channel = discord.utils.get(
            self.guild.channels, id=mod_channel_id
        )

        bot_management_channel_id = await bot.bot_channel_manager.create_or_get_channel_id(
            self.logger, self.guild, wall_e_config.get_config_value('basic_config', 'ENVIRONMENT'),
            "bot_management_channel"
        )
        self.bot_management_channel = discord.utils.get(
            self.guild.channels, id=bot_management_channel_id
        )

        # read in ban_list of banned users
        self.logger.debug('[Ban load()] loading ban list from the database')
        Ban.ban_list = await BanRecord.get_all_active_ban_user_ids()
        count = await BanRecord.get_active_bans_count()
        self.logger.debug(f"[Ban load()] loaded {count} banned users from database")

    @commands.Cog.listener(name='on_member_join')
    async def watchdog(self, member: discord.Member):
        """Watches for users joining the guild and kicks and bans a user if they are banned"""
        while self.guild is None and self.bot_management_channel is None:
            await asyncio.sleep(2)

        if member.id in Ban.ban_list:
            self.logger.info("[Ban watchdog()] banned member detected. Promptly will notify and kick them.")

            e_obj = await embed(
                self.logger,
                validate=False,
                title='Ban Notification',
                colour=WallEColour.BAN,
                content=[
                        ("Notice", f"**You are PERMANENTLY BANNED from\n{self.guild}\n\n"
                                   f"You may NOT rejoin the guild!**", False)
                ],
                channels=self.guild.channels,
                bot_management_channel=self.bot_management_channel,
                ban_related_message=True,
                footer_text=f"{self.guild}",
                footer_icon=self.guild.icon,
                timestamp=pstdatetime.now().pst
            )
            if e_obj:
                try:
                    await member.send(embed=e_obj)
                except (discord.HTTPException, discord.Forbidden):
                    self.logger.debug(
                        '[Ban watchdog()] unable to send warning dm to banned user due to user dm settings.'
                    )
            await member.kick(reason="Not allowed back on server.")

    @commands.Cog.listener(name='on_member_ban')
    async def intercept(self, guild: discord.Guild, member: Union[discord.User, discord.Member]):
        """Watches for a guild ban. The guild ban is undone and the user is banned via this ban system"""
        while self.guild is None and self.bot_management_channel is None:
            await asyncio.sleep(2)

        # don't intercept when Wall-E does a guild.ban()
        if member.id in self.processing:
            return

        if not await self.already_banned(member):
            self.logger.info("[Ban intercept()] guild ban detected and intercepted for a user")

            # need to read the audit log to grab mod, date, and reason
            # use halt problem with sleep to ensure getting audit log data
            audit_ban = None
            count = 0
            while audit_ban is None:
                await asyncio.sleep(1)
                if count > 60:
                    break
                try:
                    def get_audit_log(ban: discord.AuditLogEntry):
                        return member.id == ban.target.id
                    audit_ban = await discord.utils.find(
                        get_audit_log, self.guild.audit_logs(action=BanAction, oldest_first=False)
                    )
                except Exception as e:
                    self.logger.debug(f'[Ban intercept()] error encountered: {e}')
                    e_obj = await embed(
                        self.logger,
                        validate=False,
                        title='Intercept Ban Error',
                        colour=WallEColour.BAN,
                        description="Error while getting audit log data\n**Most likely need view audit log perms.**",
                        channels=self.guild.channels,
                        bot_management_channel=self.bot_management_channel,
                        ban_related_message=True
                    )
                    if e_obj:
                        await self.mod_channel.send(embed=e_obj)
                    return
                count += 1

            if audit_ban is None:
                self.logger.debug("[Ban intercept()] No audit data, aborting and notifying mod channel")
                e_obj = await embed(
                    self.logger,
                    validate=False,
                    title='Intercept Ban Error',
                    colour=WallEColour.BAN,
                    description=(
                        f"Unable to get guild ban for {member} to convert to wall_e ban. "
                        f"Please use `.convertbans` then `.purgebans` to try and manually convert ban."
                    ),
                    channels=self.guild.channels,
                    bot_management_channel=self.bot_management_channel,
                    ban_related_message=True
                )
                if e_obj:
                    await self.mod_channel.send(embed=e_obj)
                return
            self.logger.debug(f"[Ban intercept()] audit log data retrieved for intercepted ban: {audit_ban}")
            reason = audit_ban.reason if audit_ban.reason else DEFAULT_REASON

            # create ban
            ban = await self.create_ban(member, audit_ban.user, reason, audit_ban.created_at)
            self.logger.debug("[Ban intercept()] ban for member moved into db")

            # report to council
            await self.mod_report(ban, False, audit_ban.created_at, True)
        # unban the user
        self.logger.debug("[Ban intercept()] guild ban removed")
        await guild.unban(member)

    async def already_banned(self, banned_user):
        if banned_user.id in Ban.ban_list:
            e_obj = await embed(
                self.logger,
                validate=False,
                title='Duplicate Ban Error',
                description=f"{banned_user} is already banned",
                colour=WallEColour.BAN,
                channels=self.guild.channels,
                bot_management_channel=self.bot_management_channel,
                ban_related_message=True
            )
            if e_obj:
                await self.mod_channel.send(embed=e_obj)
            self.logger.debug(f"[Ban already_banned()] user={banned_user} is already in ban system")
            return True
        return False

    async def create_ban(self, banned_user, mod, reason, ban_date):
        Ban.ban_list[banned_user.id] = banned_user.name
        ban = BanRecord(
            username=banned_user.name,
            user_id=banned_user.id,
            mod=mod.name,
            mod_id=mod.id,
            reason=reason,
            ban_date=ban_date.timestamp()
        )
        await BanRecord.insert_record(ban)
        self.logger.debug("[Ban create_ban()] Created BanRecord")
        return ban

    async def mod_report(self, ban: BanRecord, dm_sent, ban_date, intercept_ban):
        # report to council
        if intercept_ban:
            dm_status = "NO"
        else:
            dm_status = "YES" if dm_sent else "NO\nUSER HAS DM's DISABLED or NO COMMON GUILD"

        e_obj = await embed(
            self.logger,
            title='Ban Hammer Deployed',
            colour=WallEColour.BAN,
            content=[
                ("Banned User", f"**{ban.username}**"),
                ("Moderator", f"**{ban.mod}**",),
                ("Reason", f"```{ban.reason}```", False),
                ("User Notified via DM", dm_status, False),
            ],
            footer_text="Intercepted Moderator Action" if intercept_ban else "Moderator Action",
            channels=self.guild.channels,
            bot_management_channel=self.bot_management_channel,
            ban_related_message=True,
            timestamp=ban_date
        )
        if e_obj:
            await self.mod_channel.send(embed=e_obj)
        self.logger.debug(f"[Ban mod_report()] Message sent to mod channel,{self.mod_channel}, of the ban.")

    @app_commands.command(name="ban", description="Bans a user from the guild")
    @app_commands.describe(user="user to unban")
    @app_commands.checks.has_any_role("Minions", "Moderator")
    async def ban(self, interaction: discord.Interaction, user: discord.Member, delete_message_days: int = 1,
                  reason: str = DEFAULT_REASON):
        self.logger.info(
            f"[Ban ban()] Ban command detected from {interaction.user} with args: "
            f"delete_message_days={delete_message_days}, reason={reason}"
        )
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            await interaction.channel.send(
                "Feeling a bit overloaded at the moment...Please try again in a few minutes"
            )
            return

        if await self.already_banned(user):
            return

        mod = interaction.user
        if delete_message_days <= 0 or delete_message_days > 7:
            delete_message_days = 1
        self.logger.debug(f"[Ban ban()] Delete message set to {delete_message_days} day(s)")

        # determine if bot is able to ban the user
        bot_member = await self.guild.fetch_member(bot.user.id)
        if bot_member.top_role <= user.top_role:
            e_obj = await embed(
                self.logger,
                validate=False,
                title='Ban Error',
                description=f"{user}'s permissions are higher than WALL_E, so WALL-E cannot kick them.",
                colour=WallEColour.BAN,
                channels=self.guild.channels,
                bot_management_channel=self.bot_management_channel,
                ban_related_message=True
            )
            if e_obj:
                await self.mod_channel.send(embed=e_obj)
            return
        self.logger.debug(f"[Ban ban()] Banning user {user} with id={user.id}")

        self.processing.append(user.id)
        ban_date = pstdatetime.now()
        ban = await self.create_ban(user, mod, reason, ban_date)

        # dm banned user
        dm_sent = True
        e_obj = await embed(
            self.logger,
            title='Ban Notification',
            description=f"You have been **PERMANENTLY BANNED** from **{self.guild.name.upper()}**",
            colour=WallEColour.BAN,
            content=[
                ('Reason',
                 f"```{reason}```\n**Please refrain from this kind of behaviour in the future. Thank you.**")
            ],
            channels=self.guild.channels,
            bot_management_channel=self.bot_management_channel,
            ban_related_message=True,
            timestamp=pstdatetime.now().pst,
            footer_text=f"{self.guild}",
            footer_icon=self.guild.icon
        )
        if e_obj:
            try:
                await user.send(embed=e_obj)
                self.logger.debug("[Ban ban()] User notified via dm of their ban")
            except (discord.HTTPException, discord.Forbidden, discord.errors.Forbidden):
                dm_sent = False
                self.logger.debug("[Ban ban()] Notification dm to user failed due to user preferences")

        # Ban to remove messages and remove them from guild
        await self.guild.ban(user, reason=reason, delete_message_days=delete_message_days)

        # Unbanning too fast can cause issues
        await asyncio.sleep(2)
        await self.guild.unban(user)
        self.processing.remove(user.id)
        self.logger.debug(f"[Ban ban()] member removed from guild at {pstdatetime.now()}")

        # report to council
        await self.mod_report(ban, dm_sent, ban_date, False)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    @app_commands.command(name="unban", description="Unbans the specified user")
    @app_commands.describe(user_id="user to unban")
    @app_commands.autocomplete(user_id=get_banned_users)
    @app_commands.checks.has_any_role("Minions", "Moderator")
    async def unban(self, interaction: discord.Interaction, user_id: str):
        self.logger.info(f"[Ban unban()] unban command detected from {interaction.user} with args=[ {user_id} ]")
        if user_id == "-1" or not user_id.isdigit():
            e_obj = await embed(
                self.logger,
                validate=False,
                interaction=interaction,
                title='Unban Error',
                description="Invalid input detected. Please try again.",
                colour=WallEColour.BAN
            )
            if e_obj:
                await interaction.response.send_message(embed=e_obj, )
                await asyncio.sleep(10)
            await interaction.delete_original_response()
            return
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            await interaction.channel.send(
                "Feeling a bit overloaded at the moment...Please try again in a few minutes"
            )
            return
        user_id = int(user_id)
        if user_id not in Ban.ban_list:
            self.logger.debug(f"[Ban unban()] Provided id: {user_id}, does not belong to a banned member.")
            e_obj = await embed(
                self.logger, validate=False, interaction=interaction, title='Unban Error',
                description=f"`{user_id}` is either not a valid Discord ID **OR** is not a banned user",
                colour=WallEColour.BAN
            )
            if e_obj:
                await interaction.followup.send(embed=e_obj)
            return

        del Ban.ban_list[user_id]
        name = await BanRecord.unban_by_id(user_id)
        if name:
            self.logger.debug(f"[Ban unban()] User: {name} with id: {user_id} was unbanned.")
            mod_channel_e_obj = await embed(
                self.logger, validate=False, interaction=interaction, title='User Unbanned', colour=WallEColour.BAN,
                content=[('Unbanned User', name), ("Moderator", interaction.user.name)]
            )
            if mod_channel_e_obj:
                await self.mod_channel.send(embed=mod_channel_e_obj)
        else:
            self.logger.debug(f"[Ban unban()] No user with id: {user_id} found.")
            e_obj = await embed(
                self.logger, validate=False, interaction=interaction, title='Unban Error',
                description=f"No user with id: **`{user_id}`** found.",
                colour=WallEColour.BAN
            )
            if e_obj:
                await interaction.followup.send(embed=e_obj)
                await asyncio.sleep(10)

        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    @app_commands.command(name="bans", description="Gets all banned users")
    @app_commands.describe(search_query="username to search for")
    @app_commands.checks.has_any_role("Bot_manager", "Minions", "Moderator")
    @app_commands.autocomplete(search_query=get_banned_users)
    async def bans(self, interaction: discord.Interaction, search_query: str = None):
        self.logger.info(f"[Ban bans()] bans command detected from {interaction.user}")
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            await interaction.channel.send(
                "Feeling a bit overloaded at the moment...Please try again in a few minutes"
            )
            return

        bans = await BanRecord.get_all_active_bans(search_query)
        self.logger.debug("[Ban bans()] retrieved all banned users")

        names = ""
        user_ids = ""
        ban_dates = ""
        content_to_embed = []
        number_of_members_per_page = 20
        number_of_members = 0
        for ban in bans:
            name = ban['username']
            user_id = ban['user_id']
            ban_date = ban['ban_date']
            names += f"\n{name}"
            user_ids += f"\n{user_id}"
            ban_dates += f'\n{ban_date.pst.strftime("%Y-%m-%d %I:%M:%S %p")}' if ban_date else f"\n{ban_date}"
            number_of_members += 1
            if number_of_members % number_of_members_per_page == 0 or number_of_members == len(bans):
                number_of_members = 0
                content_to_embed.append(
                    [["Names", names], ["User IDs", user_ids], ["Ban Date [PST]", ban_dates]]
                )
                names = ""
                user_ids = ""
                ban_dates = ""
        if len(content_to_embed) == 0:
            e_obj = await embed(
                self.logger, interaction=interaction, title='Bans Error',
                description=f"Could not find a banned user whose username contains `{search_query}`",
                colour=WallEColour.BAN
            )
            if e_obj:
                msg = await interaction.followup.send(embed=e_obj)
                await asyncio.sleep(10)
                await msg.delete()
        else:
            await paginate_embed(
                self.logger, bot, content_to_embed=content_to_embed,
                title=f"{len(bans)} Banned members",
                interaction=interaction
            )

        self.logger.debug("[Ban bans()] done sending embeds with banned user lists and total ban count")

    @app_commands.command(name="convertbans", description="Reads in all guild bans into WALL_E ban system")
    @app_commands.checks.has_any_role("Minions", "Moderator")
    async def convertbans(self, interaction: discord.Interaction):
        self.logger.info(f"[Ban convertbans()] convertbans command detected from {interaction.user}")
        await interaction.response.defer()

        try:
            # audit logs contains info about user who did the banning, the timestamp of the ban, and the reason
            # however audit logs only go back 3 months, so have to read older bans from the bans list
            ban_logs = {
                ban_log.target.id: ban_log
                for ban_log in [ban async for ban in self.guild.audit_logs(action=BanAction)]
            }
            guild_ban_list = [ban async for ban in self.guild.bans()]
        except Exception as e:
            self.logger.debug(f'[Ban convertbans()] error while fetching ban data: {e}')
            e_obj = await embed(
                self.logger,
                author=bot.user,
                colour=WallEColour.BAN,
                description=f"Encountered the following errors: {e}\n**Most likely need view audit log perms.**",
                interaction=interaction
            )
            if e_obj:
                await interaction.followup.send(embed=e_obj)
            return

        if not guild_ban_list:
            self.logger.debug("[Ban convertbans()] No bans to migrate into the ban system from guild. "
                              "Sening message and ending command.")
            await interaction.followup.send("There are no bans to migrate from the guild to the wall_e ban system.")
            return

        self.logger.debug("[Ban convertbans()] retrieved audit log data for ban actions")
        self.logger.debug("[Ban convertbans()] retrieved ban list from guild")

        self.logger.debug("[Ban convertbans()] Starting process to move all guild bans into db")

        # update Ban.ban_list
        ban_records = []
        for ban in guild_ban_list:
            # NOTE: In the unlikely case there are >1 bans for the same user only 1 will be recorded
            if ban.user.id not in Ban.ban_list:
                Ban.ban_list[ban.user.id] = ban.user.name

                mod = None
                mod_id = None
                ban_date = None
                reason = DEFAULT_REASON

                if ban.user.id in ban_logs:
                    banned = ban_logs[ban.user.id]
                    username = banned.name
                    user_id = banned.target.id
                    mod = banned.user.name
                    mod_id = banned.user.id
                    ban_date = banned.created_at
                    reason = banned.reason if banned.reason else DEFAULT_REASON

                else:
                    username = ban.user.name
                    user_id = ban.user.id

                ban_records.append(BanRecord(
                    username=username,
                    user_id=user_id,
                    mod=mod,
                    mod_id=mod_id,
                    ban_date=ban_date,
                    reason=reason
                ))

        await BanRecord.insert_records(ban_records)

        e_obj = await embed(
            self.logger,
            author=bot.user,
            description=f"Moved `{len(ban_records)}` active bans from guild bans to wall_e bans.",
            interaction=interaction
        )
        if e_obj:
            await interaction.followup.send(embed=e_obj)
        self.logger.debug(f"[Ban convertbans()] total of {len(ban_records)} bans moved into wall_e ban system")

    @app_commands.command(name="purgebans", description="Clears the discord ban list.")
    @app_commands.checks.has_any_role("Minions", "Moderator")
    async def purgebans(self, interaction: discord.Interaction):
        self.logger.info(f"[Ban purgebans()] purgebans command detected from {interaction.user}")
        await interaction.response.defer()

        bans = [ban async for ban in self.guild.bans()]
        self.logger.debug("[Ban purgebans()] Retrieved list of banned users from guild")

        if not bans:
            self.logger.debug("[Ban purgebans()] Ban list is empty. Sending message and ending command.")
            e_obj = await embed(
                self.logger, interaction=interaction, title=f'{bot.user.name} Ban',
                description="Ban list is empty. Nothing to purge.",
            )
            if e_obj:
                msg = await interaction.followup.send(embed=e_obj)
                await asyncio.sleep(10)
                await msg.delete()
            return

        for ban in bans:
            self.logger.debug("[Ban purgebans()] Unbanning user")
            await self.guild.unban(ban.user)

        e_obj = await embed(
            self.logger, interaction=interaction,
            description=f"**GUILD BAN LIST PURGED**\nTotal # of users unbanned: {len(bans)}",
        )
        if e_obj:
            msg = await interaction.followup.send(embed=e_obj)
            await asyncio.sleep(10)
            await msg.delete()

    def cog_unload(self):
        self.logger.info('[Ban cog_unload()] Removing listeners for ban cog: on_ready, on_member_join, on_member_ban')
        bot.remove_listener(self.load, 'on_ready')
        bot.remove_listener(self.watchdog, 'on_member_join')
        bot.remove_listener(self.intercept, 'on_member_ban')


async def setup(bot):
    await bot.add_cog(Ban())
