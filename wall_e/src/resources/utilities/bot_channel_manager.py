import asyncio

import discord

log_positioning = {
    "sys_debug": 0,
    "sys_error": 1,
    "wall_e_debug": 2,
    "wall_e_error": 3,
    "administration_debug": 4,
    "administration_error": 5,
    "ban_debug": 6,
    "ban_error": 7,
    "frosh_debug": 8,
    "frosh_error": 9,
    "health_checks_debug": 10,
    "health_checks_error": 11,
    "here_debug": 12,
    "here_error": 13,
    "leveling_debug": 14,
    "leveling_error": 15,
    "manage_cog_debug": 16,
    "manage_cog_error": 17,
    "misc_debug": 18,
    "misc_error": 19,
    "mod_debug": 20,
    "mod_error": 21,
    "reminders_debug": 22,
    "reminders_error": 23,
    "role_commands_debug": 25,
    "role_commands_error": 26,
    "sfu_debug": 27,
    "sfu_error": 28
}
wall_e_category_name = "WALL-E LOGS"


class BotChannelManager:

    def __init__(self, config, bot):
        """
        Initialized the BotChannelManager service which is responsible for creating any discord text channels
        or category channels need by wall_e
        :param config: an instance of WALLEConfig that is used to determine what name to assign to the channels
        since the channel names in the TEST environment are BRANCH_NAME dependent.
        :param bot: Used by the methods to make sure the service only tries to interact with discord API when
        bot.wait_until_ready() indicates the bot is ready
        """
        self.bot = bot
        self.channel_names = {
            "general_channel": {
                "TEST": config.get_config_value('basic_config', 'BRANCH_NAME').lower(),
            },
            "role_commands": {
                "PRODUCTION": config.get_config_value('channel_names', 'BOT_GENERAL_CHANNEL'),
                "TEST": f"{config.get_config_value('basic_config', 'BRANCH_NAME').lower()}_bot_channel",
                "LOCALHOST": config.get_config_value('channel_names', 'BOT_GENERAL_CHANNEL')
            },
            "reminders": {
                "PRODUCTION": config.get_config_value('channel_names', 'BOT_GENERAL_CHANNEL'),
                "TEST": f"{config.get_config_value('basic_config', 'BRANCH_NAME').lower()}_bot_channel",
                "LOCALHOST": config.get_config_value('channel_names', 'BOT_GENERAL_CHANNEL')
            },
            "log_channel": {
                "PRODUCTION": config.get_config_value('channel_names', 'BOT_LOG_CHANNEL'),
                "TEST": f"{config.get_config_value('basic_config', 'BRANCH_NAME').lower()}_logs",
                "LOCALHOST": config.get_config_value('channel_names', 'BOT_LOG_CHANNEL')
            },
            "ban": {
                "PRODUCTION": config.get_config_value('channel_names', 'MOD_CHANNEL'),
                "TEST": f"{config.get_config_value('basic_config', 'BRANCH_NAME').lower()}_mod_channel",
                "LOCALHOST": config.get_config_value('channel_names', 'MOD_CHANNEL')
            },
            "council": {
                "PRODUCTION": config.get_config_value('channel_names', 'MOD_CHANNEL'),
                "TEST": f"{config.get_config_value('basic_config', 'BRANCH_NAME').lower()}_mod_channel",
                "LOCALHOST": config.get_config_value('channel_names', 'MOD_CHANNEL')
            },
            "leveling": {
                "PRODUCTION": config.get_config_value('channel_names', 'LEVELLING_CHANNEL'),
                "TEST": f"{config.get_config_value('basic_config', 'BRANCH_NAME').lower()}_council",
                "LOCALHOST": config.get_config_value('channel_names', 'LEVELLING_CHANNEL')
            }
        }
        self.channel_obtained = {
        }

    async def create_or_get_channel_id_for_service(self, logger, guild, config, service):
        """
        used to create or get the text channels where log files entries will be uploaded to
        :param logger: the service's instant of logger
        :param guild: the guild on which to create or get the text channel
        :param config: used to determine the name of the text channels if the environment is TEST
        :param service: the service that is calling this method to get the necessary channel id
        :return: the ID of the channel
        """
        await self.bot.wait_until_ready()
        service = service.lower()
        environment = config.get_config_value("basic_config", "ENVIRONMENT")
        text_channel_position = log_positioning[service]
        if environment == 'TEST':
            service = f"{service}_{config.get_config_value('basic_config', 'BRANCH_NAME')}"
        logger.info("[BotChannelManager create_or_get_channel_id_for_service()] "
              f"getting channel {service} for {environment}")
        logger.info("[BotChannelManager create_or_get_channel_id_for_service()] attempting to get "
              f" channel '{service}' for {environment} ")
        bot_chan = discord.utils.get(guild.channels, name=service)
        if wall_e_category_name not in self.channel_obtained:
            self.channel_obtained[wall_e_category_name] = None
            logs_category = discord.utils.get(guild.channels, name=wall_e_category_name)
            if logs_category is None:
                logs_category = await guild.create_category(name=wall_e_category_name)
            self.channel_obtained[wall_e_category_name] = logs_category.id
        else:
            while self.channel_obtained[wall_e_category_name] is None:
                logger.info(
                    f"[BotChannelManager create_or_get_channel_id_for_service()] waiting to get category "
                    f"WALL-E Logs for in {environment}."
                )
                await asyncio.sleep(8)
        logs_category = discord.utils.get(guild.channels, id=int(self.channel_obtained[wall_e_category_name]))
        if bot_chan is None:
            logger.info("[BotChannelManager create_or_get_channel_id_for_service()] "
                  f"channel \"{service}\" for {environment} does not exist "
                  f"will attempt to create it now.")
        number_of_retries_to_attempt = 10
        number_of_retries = 0
        while bot_chan is None and number_of_retries < number_of_retries_to_attempt:
            bot_chan = await guild.create_text_channel(
                service, category=logs_category, position=text_channel_position
            )
            logger.info("[BotChannelManager create_or_get_channel_id_for_service()] "
                  f"got channel \"{bot_chan}\" for {environment}")
            logger.info("[BotChannelManager create_or_get_channel_id_for_service()] attempt "
                  f"({number_of_retries}/{number_of_retries_to_attempt}) for getting {service} ")
            await asyncio.sleep(10)
            number_of_retries += 1
        if bot_chan is None:
            logger.info(
                f"[BotChannelManager create_or_get_channel_id_for_service()] the channel {service} "
                f"in {environment}  does not exist and I was unable to create it, exiting now...."
            )
            await asyncio.sleep(20)  # this is just here so that the above log line
            # gets a chance to get printed to discord
            exit(1)
        logger.info(
            f"[BotChannelManager create_or_get_channel_id_for_service()] the channel {service} for "
            f"in {environment} acquired."
        )
        logger.info("[BotChannelManager create_or_get_channel_id_for_service()] "
              f"returning channel id for {service} "
              f"for {environment}")
        return bot_chan.id

    async def create_or_get_channel_id(self, logger, guild, environment, channel_purpose):
        """
        used to create or get the text channels where things like reminders or mod-related messages
         need to be sent to
        :param logger: the service's instance of logger
        :param guild: the guild on which to create or get the text channel
        :param environment: the environment that wall_e is running in
        :param channel_purpose: the purpose the channel wil be used for, the options are keys in the
         self.channel_names dict instantiated in the constructor
        :return: the ID of the channel
        """
        await self.bot.wait_until_ready()
        channel_name = self.channel_names[channel_purpose][environment]
        logger.info("[BotChannelManager create_or_get_channel_id()] "
              f"getting channel {channel_name} for {environment} {channel_purpose}")
        if channel_name not in self.channel_obtained:
            self.channel_obtained[channel_name] = None
            logger.info("[BotChannelManager create_or_get_channel_id()] attempting to get "
                  f" channel '{channel_name}' for {environment} {channel_purpose} ")
            bot_chan = discord.utils.get(guild.channels, name=channel_name)
            if bot_chan is None:
                logger.info("[BotChannelManager create_or_get_channel_id()] "
                      f"channel \"{channel_name}\" for {environment} {channel_purpose} does not exist "
                      f"will attempt to create it now.")
            number_of_retries_to_attempt = 10
            number_of_retries = 0
            while bot_chan is None and number_of_retries < number_of_retries_to_attempt:
                bot_chan = await guild.create_text_channel(channel_name)
                logger.info("[BotChannelManager create_or_get_channel_id()] "
                      f"got channel \"{bot_chan}\" for {environment} {channel_purpose}")
                logger.info("[BotChannelManager get_bot_general_channel()] attempt "
                      f"({number_of_retries}/{number_of_retries_to_attempt}) for getting {channel_name} ")
                await asyncio.sleep(10)
                number_of_retries += 1
            if bot_chan is None:
                logger.info(
                    f"[BotChannelManager create_or_get_channel_id()] the channel {channel_name} for "
                    f"{channel_purpose} "
                    f"in {environment}  does not exist and I was unable to create it, exiting now...."
                )
                await asyncio.sleep(20)  # this is just here so that the above log line
                # gets a chance to get printed to discord
                exit(1)
            logger.info(
                f"[BotChannelManager create_or_get_channel_id()] the channel {channel_name} for {channel_purpose} "
                f"in {environment} acquired."
            )
            self.channel_obtained[channel_name] = bot_chan.id
        else:
            while self.channel_obtained[channel_name] is None:
                logger.info(
                    f"[BotChannelManager create_or_get_channel_id()] waiting to get channel "
                    f"{channel_name} for {channel_purpose} "
                    f"in {environment}."
                )
                await asyncio.sleep(8)
        logger.info("[BotChannelManager get_bot_general_channel()] "
              f"returning channel id for {channel_name} "
              f"for {environment} {channel_purpose}")
        return self.channel_obtained[channel_name]

    @classmethod
    async def delete_log_channels(cls, interaction: discord.Interaction):
        """
        Used to delete all the log text and category channels. Useful when doing local devving and want to clean up
        channels that are not needed after done devving
        :param interaction: the interaction object that can be traversed to contain the current list of
         channels in the guild
        :return:
        """
        def text_log_channel(channel): return (
            type(channel) == discord.channel.TextChannel and
            channel.name in list(log_positioning.keys())
        )

        def log_category(channel): return (
            type(channel) == discord.channel.CategoryChannel and
            channel.name == wall_e_category_name
        )

        log_channels = [
            channel for channel in list(interaction.guild.channels)
            if text_log_channel(channel) or log_category(channel)
        ]
        for log_channel in log_channels:
            await log_channel.delete()
