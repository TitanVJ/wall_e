from discord.ext import commands
import discord
import asyncio
# import json
from resources.utilities.embed import embed as em
from resources.utilities.log_channel import write_to_bot_log_channel
from resources.utilities.setup_logger import Loggers


class Mod(commands.Cog):

    async def rekt(self, ctx):
        self.logger.info('[Mod rekt()] sending troll to unauthorized user')
        lol = '[secret](https://www.youtube.com/watch?v=dQw4w9WgXcQ)'
        e_obj = await em(
            self.logger,
            ctx=ctx,
            title='Minion Things',
            author=self.config.get_config_value('bot_profile', 'BOT_NAME'),
            avatar=self.config.get_config_value('bot_profile', 'BOT_AVATAR'),
            description=lol
        )
        if e_obj is not False:
            msg = await ctx.send(embed=e_obj)
            await asyncio.sleep(5)
            await msg.delete()
            self.logger.info('[Mod rekt()] troll message deleted')

    def __init__(self, bot, config, bot_loop_manager):
        self.bot = bot
        self.config = config
        self.bot_loop_manager = bot_loop_manager
        self.logger, self.debug_log_file_absolute_path, self.sys_stream_error_log_file_absolute_path \
            = Loggers.get_logger(logger_name="Mod")

    @commands.Cog.listener(name="on_ready")
    async def upload_debug_logs(self):
        chan_id = await self.bot_loop_manager.create_or_get_channel_id_for_service(
            self.config,
            "mod_debug"
        )
        await write_to_bot_log_channel(
            self.bot, self.debug_log_file_absolute_path, chan_id
        )

    @commands.Cog.listener(name="on_ready")
    async def upload_error_logs(self):
        chan_id = await self.bot_loop_manager.create_or_get_channel_id_for_service(
            self.config,
            "mod_error"
        )
        await write_to_bot_log_channel(
            self.bot, self.sys_stream_error_log_file_absolute_path, chan_id
        )

    @commands.command(aliases=['em'])
    async def embed(self, ctx, *arg):
        self.logger.info('[Mod embed()] embed function detected by user {}'.format(ctx.message.author))
        await ctx.message.delete()
        self.logger.info('[Mod embed()] invoking message deleted')

        if not arg:
            self.logger.info("[Mod embed()] no args, so command ended")
            return

        if ctx.message.author not in discord.utils.get(ctx.guild.roles, name="Minions").members:
            self.logger.info('[Mod embed()] unathorized command attempt detected. Being handled.')
            await self.rekt(ctx)
            return

        self.logger.info('[Mod embed()] minion confirmed')
        fields = []
        desc = ''
        arg = list(arg)
        arg_len = len(arg)
        # odd number of args means description plus fields
        if not arg_len % 2 == 0:
            desc = arg[0]
            arg.pop(0)
            arg_len = len(arg)

        i = 0
        while i < arg_len:
            fields.append([arg[i], arg[i + 1]])
            i += 2

        name = ctx.author.nick or ctx.author.name
        e_obj = await em(
            self.logger, ctx=ctx, description=desc, author=name, avatar=ctx.author.avatar.url, colour=0xffc61d,
            content=fields
        )
        if e_obj is not False:
            await ctx.send(embed=e_obj)

    @commands.command(aliases=['warn'])
    async def modspeak(self, ctx, *arg):
        self.logger.info('[Mod modspeak()] modspeack function detected by minion {}'.format(ctx.message.author))
        await ctx.message.delete()
        self.logger.info('[Mod modspeak()] invoking message deleted')

        if not arg:
            self.logger.info("[Mod modspeak()] no args, so command ended")
            return

        if ctx.message.author not in discord.utils.get(ctx.guild.roles, name="Minions").members:
            self.logger.info('[Mod modspeak()] unathorized command attempt detected. Being handled.')
            await self.rekt(ctx)
            return

        msg = ''
        for wrd in arg:
            msg += '{} '.format(wrd)

        e_obj = await em(self.logger, ctx=ctx, title='ATTENTION:', colour=0xff0000, author=ctx.author.display_name,
                         avatar=ctx.author.avatar.url, description=msg, footer='Moderator Warning')
        if e_obj is not False:
            await ctx.send(embed=e_obj)
