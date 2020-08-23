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
        await ctx.send('What channel do you want the message in?')
        user_input = await self.bot.wait_for('message', check=input_check)
        if user_input.content == 'exit':
            await ctx.send('react embed creation aborted')
            return
        channel = await commands.TextChannelConverter().convert(ctx, user_input.content)

        # get embed title
        await ctx.send('What do you want the react message to be?')
        user_input = await self.bot.wait_for('message', check=input_check)
        if user_input.content == 'exit':
            await ctx.send('react embed creation aborted')
            return
        title = user_input.content

        # get colour for embed or use default
        await ctx.send(
            'Enter a colour for the embed message. Enter `none` to skip this and use the default colour.\n' +
            '**Need help picking a colour?** Check out: <https://htmlcolorcodes.com/>\n' +
            '**Hexcode Format**: \n\t**0x**<hex> OR **#**<hex>'
            )
        user_input = await self.bot.wait_for('message', check=input_check)
        if user_input.content == 'exit':
            await ctx.send('react embed creation aborted')
            return
        if user_input:
            try:
                colour = commands.ColourConverter().convert(ctx, user_input.content)
            except Exception:
                await ctx.send('That doesn\'t seem to legit hex code, so we\'ll just go with a default colour.')

        # emoji, role, optional message
        await ctx.send(
            'Time to add roles. Just keep typing them out one at a time, when you\'re done type `done`.\n' +
            'Heres the format for adding roles:\n' +
            '```<emoji>, <role>, [<description of some sort>]```' +
            'The 3rd argument is *optional*, it puts a message next to the emoji instead of the role.\n' +
            '**Example**:\n:smiling_imp:, Froshee\n :snake:,Tab-Life, React if ur python gang'
            )
        while True:
            # await ctx.send('What do you want the react message to be?')
            user_input = await self.bot.wait_for('message', check=input_check)
            if user_input.content == 'exit':
                await ctx.send('react embed creation aborted')
                return
            elif user_input.content == 'done':
                break
            roles.append(user_input.content)
            # todo: parse input for emoji, role, and leftover message

        # em = await embed(
        #     ctx,
        #     title=title,
        #     author=ctx.author.display_name,
        #     avatar=ctx.author.avatar_url,
        #     content=roles,
        #     colour=colour,
        #     footer='*Yeeeeeet!!*'
        # )
        # react_embed = await channel.send(embed=em)
        print(channel)
        print(title)
        print(colour)
        print(roles)
        await ctx.send('Done')
