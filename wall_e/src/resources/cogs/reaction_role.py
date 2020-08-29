import discord
from discord.ext import commands
import logging
import json
import asyncio
from resources.utilities.embed import embed
logger = logging.getLogger('wall_e')


class ReactionRole(commands.Cog):

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        emoji_file = open('resources/locales/emoji-compact.json')
        self.emojis = json.load(emoji_file)
        emoji_file.close()
        self.react_msgs = {}

    def check(self, author: discord.user, channel: discord.channel):
        return lambda m: m.author == author and m.channel == channel

    async def request(self, ctx, prompt, converter=None, timeout=60.0):
        input_check = self.check(ctx.author, ctx.channel)

        await ctx.send(prompt)
        msg = await self.bot.wait_for('message', check=input_check, timeout=timeout)
        ret = msg.content

        if converter:
            try:
                ret = await converter.convert(ctx, ret)
            except Exception:
                return False, ret
        return True, ret

    async def parse(self, ctx, msg: discord.Message):
        # parse out the role, emoji, and optional message
        info = list(map(lambda str: str.strip(), msg.content.split(',')))
        if info[0] not in self.emojis:
            # check for custom emoji
            try:
                info[0] = await commands.PartialEmojiConverter().convert(ctx, info[0])
            except Exception:
                await ctx.send(f'Can\'t find this `{info[0]}` emoji')
                return

        try:
            info[1] = await commands.RoleConverter().convert(ctx, info[1])
        except Exception:
            await ctx.send(f'Cound not find role: {info[1]}')
            return

        return info

    async def send_react_message(self, ctx, channel: discord.TextChannel, title, colour, role_bindings):
        def extract(key):
            emojis.append(key)
            role_msg = role_bindings[key]
            try:
                return f'{key} `{role_msg[1]}`'
            except IndexError:
                return f'{key} {role_msg[0].mention}'
        emojis = []

        # make the embed
        react_embed = await embed(
            ctx,
            title=title,
            colour=colour,
            description='\n'.join(map(extract, role_bindings))
        )
        # send the react message to the destination channel
        react_msg = await channel.send(embed=react_embed)

        # add the reactions
        for emoji in emojis:
            await react_msg.add_reaction(emoji)

        # send acknowledgement message to user with link to react embed
        await ctx.send(f'Done\nHeres your reaction role message: {react_msg.jump_url}')

    @commands.command(aliases=['rr'])
    async def reactrole(self, ctx):
        logger.info("[ReactionRole reactRole()] starting interactive process to create react role embed")

        channel = ''
        title = ''
        role_binding = {}
        colour = None

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
                colour = 0x12FFD8
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
                msg = await self.bot.wait_for('message', check=self.check(ctx.author, ctx.channel), timeout=60.0)
                if msg.content == 'done':
                    break

                info = await self.parse(ctx, msg)
                if info is not None:
                    role_binding.update({info[0]: info[1:]})
                    await msg.add_reaction('\N{WHITE HEAVY CHECK MARK}')
                else:
                    await msg.add_reaction('\N{CROSS MARK}')

        except asyncio.TimeoutError:
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

        # make and send the reaction role
        await self.send_react_message(ctx, channel, title, colour, role_binding)