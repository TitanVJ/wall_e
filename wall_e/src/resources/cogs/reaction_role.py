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

    async def request(self, ctx, prompt, converter=None, failAllowed=False, timeout=60.0):
        input_check = self.check(ctx.author, ctx.channel)
        msg = await ctx.send(prompt)
        try:
            user_input = await self.bot.wait_for('message', check=input_check, timeout=timeout)
        except Exception:
            await ctx.send('you ghosting me?\nbye I guess')
            return 'exit'
        else:
            if user_input.content == 'exit':
                await ctx.send('react role embed creation end')
                return

            ret = user_input.content
            if converter:
                try:
                    ret = await converter.convert(ctx, ret)
                except Exception:
                    pass
                    # if the conversion doesn't pass have to end command execution
            return ret

    @commands.command(aliases=['rr'])
    async def reactrole(self, ctx):
        logger.info("[ReactionRole reactRole()] starting interactive process to create react role embed")
        input_check = self.check(ctx.author, ctx.channel)

        '''Required:
            - channel to have react embed
            - title w/ call to action prompt
            - emoji, role, and what to list as in embed
            - optional colour

            - role and channel can be both the mention or just name <= handled by converters
        '''
        channel = ''
        title = ''
        roles = []
        colour = discord.Colour.blurple

        # get channel to send the react embed
        channel = await self.request(
            ctx,
            prompt='What channel do you want the message in?',
            converter=commands.TextChannelConverter()
            )

        title = await self.request(
            ctx,
            'What do you want the title to say?'
        )

        colour = await self.request(
            ctx,
            'Enter a colour for the embed message. Enter `none` to skip this and use the default colour.\n' +
            '**Need help picking a colour?** Check out: <https://htmlcolorcodes.com/>\n' +
            '**Hexcode Format**: \n\t**0x**<hex> OR **#**<hex>',
            commands.ColourConverter()
        )

        # check value of colour and then set to default
        if colour == 'none':
            colour = 0x900C3F

        # # emoji, role, optional message
        # await ctx.send(
        #     'Time to add roles. Just keep typing them out one at a time, when you\'re done type `done`.\n' +
        #     'Heres the format for adding roles:\n' +
        #     '```<emoji>, <role>, [<description of some sort>]```' +
        #     'The 3rd argument is *optional*, it puts a message next to the emoji instead of the role.\n' +
        #     '**Example**:\n:smiling_imp:, Froshee\n :snake:,Tab-Life, React if ur python gang'
        #     )
        # while True:
        #     # await ctx.send('What do you want the react message to be?')
        #     user_input = await self.bot.wait_for('message', check=input_check)
        #     if user_input.content == 'exit':
        #         await ctx.send('react embed creation aborted')
        #         return
        #     elif user_input.content == 'done':
        #         break
        #     roles.append(user_input.content)
            # todo: parse input for emoji, role, and leftover message

        print(channel)
        # print(title)
        # print(colour)
        # print(roles)
        await ctx.send('Done')
