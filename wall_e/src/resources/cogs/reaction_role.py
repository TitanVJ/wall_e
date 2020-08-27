import discord
from discord.ext import commands
import logging
from resources.utilities.embed import embed
logger = logging.getLogger('wall_e')


class ReactionRole(commands.Cog):

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    def check(self, author: discord.user, channel: discord.channel):
        # makes use of closures
        # will be useful for continuous monitoring of reaction embeds
        def check(m):
            return m.author == author and m.channel == channel

        return check

    async def request(self, ctx, prompt, converter=None, timeout=60.0):
        input_check = self.check(ctx.author, ctx.channel)

        await ctx.send(prompt)
        msg = await self.bot.wait_for('message', check=input_check, timeout=timeout)
        ret = msg.content

        if converter:
            try:
                ret = await converter.convert(ctx, ret)
            except Exception:
                print('excepted')
                return False, ret
        return True, ret

    async def parse(self, ctx, msg: discord.Message):
        # parse out the role, emoji, and optional message
        print(msg.content)
        info = list(map(lambda str: str.strip(), msg.content.split(',')))
        print(str(info[0]))
        # try:
        #     info[0] = await commands.EmojiConverter().convert(ctx, info[0])
        # except Exception as e:
        #     print('emoji exception')
        #     print(e)
        #     await ctx.send(f'Could not find emoji: {info[0]}')
        #     return None

        try:
            info[1] = await commands.RoleConverter().convert(ctx, info[1])
        except Exception:
            await ctx.send(f'Cound not find role: {info[1]}')
            return None
        return info

    @commands.command(aliases=['rr'])
    async def reactrole(self, ctx):
        logger.info("[ReactionRole reactRole()] starting interactive process to create react role embed")

        channel = ''
        title = ''
        roles = []
        colour = discord.Colour.blurple()

        try:
            # get channel
            status, channel = await self.request(
                ctx,
                prompt='What channel do you want the message in?',
                converter=commands.TextChannelConverter()
            )

            # check if channel found or not
            if not status:
                e_obj = await embed(
                    ctx,
                    title='Bad Argument',
                    author=self.config.get_config_value('bot_profile', 'BOT_NAME'),
                    avatar=self.config.get_config_value('bot_profile', 'BOT_AVATAR'),
                    colour=0xA6192E,
                    content=[('Error', f'Couldn\'t find channel `{channel}`\nCommand terminated.')],
                    footer='ReactRole Error'
                )
                await ctx.send(embed=e_obj)
                logger.info(f'[ReactionRole reactrole()] channel "{channel}" not found. Command exection terminated.')
                return
            logger.info(f'[ReactionRole reactrole()] channel to send react role confirmed: {channel}')

            # get title for
            _, title = await self.request(
                ctx,
                'What do you want the title to say?'
            )
            logger.info(f'[ReactionRole reactrole()] react role title set to: {title}')

            # get colour
            status, colour = await self.request(
                ctx,
                'Enter a colour for the embed message. Enter `none` to skip this and use the default colour.\n' +
                '**Need help picking a colour?** Check out: <https://htmlcolorcodes.com/>\n' +
                '**Hexcode Format**: \n\t**0x**<hex> OR **#**<hex>',
                commands.ColourConverter()
            )

            # check if valid otherwise set to default
            if not status:
                if colour == 'none':
                    await ctx.send('using default colour')
                else:
                    e_obj = await embed(
                        ctx,
                        title='Bad Argument',
                        author=self.config.get_config_value('bot_profile', 'BOT_NAME'),
                        avatar=self.config.get_config_value('bot_profile', 'BOT_AVATAR'),
                        colour=0xA6192E,
                        content=[('Error', f'{colour} isn\'t a real hex value. So we\' go with a default.')],
                        footer='ReactRole Error'
                    )
                    await ctx.send(embed=e_obj)
                colour = 0x900C3F
                logger.info(f'[ReactionRole reactrole()] react role colour set to default value: 0x{colour:x}')
            else:
                logger.info(f'[ReactionRole reactrole()] react role colour is: {colour}')

            # emoji, role, optional message
            await ctx.send(
                'Time to add roles. Keep adding them one at a time, when you\'re done type `done`.\n' +
                'Heres the format for adding roles:\n' +
                '```<emoji>, <role>, [<description of some sort>]```' +
                'Ensure the list arguments are **comma** seperated\n'
                'The 3rd argument is *optional*, it puts a message next to the emoji instead of the role.\n' +
                '**Example**:\n:smiling_imp:, Froshee\n :snake:,Tab-Life, React if ur python gang'
                )
            while True:
                msg = await self.bot.wait_for('message', check=self.check(ctx.author, ctx.channel))#, timeout=60.0)
                if msg.content == 'done':
                    await ctx.send('aight thanks dawg')
                    break

                info = await self.parse(ctx, msg)
                if info is not None:
                    # add to roles
                    roles.append(info)
                    # add checkmark reaction to msg
                else:
                    # add red x reaction to msg
                    pass
                print(info)
                # parse msg for emoji, role, and the optional message
                # also emote to each message to indicate it's added.

        except Exception as e:
            print(e)
            o_obj = await embed(
                ctx,
                title='Bad Argument',
                author=self.config.get_config_value('bot_profile', 'BOT_NAME'),
                avatar=self.config.get_config_value('bot_profile', 'BOT_AVATAR'),
                colour=0xA6192E,
                content=[('Error', 'Command timed out.')],
                footer='ReactRole Error'
            )
            await ctx.send(embed=o_obj)
            return

        print(channel)
        print(title)
        print(colour)
        print(roles)
        await ctx.send('Done')
