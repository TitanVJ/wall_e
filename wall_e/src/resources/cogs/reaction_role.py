import discord
from discord.ext import commands
import logging
logger = logging.getLogger('wall_e')


class ReactionRole(commands.Cog):

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    def check(self, author: discord.user, channel:discord.channel):
        # makes use of closures
        # will be useful for continuous monitoring of reaction embeds
        def check(m):
            return m.author == author and m.channel == channel

        return check

    @commands.command()
    async def reactrole(self, ctx):
        logger.info("[ReactionRole reactRole()] starting interactive process to create react role embed")
        ch = self.check(ctx.author, ctx.channel)

        '''TODO:
            - array of all prompts for inputs, then foreach them
            - need some way to identify optional prompts
            - special case for content fields
        need:
            - channel to have react embed
            - title w/ call to action prompt            
            - emoji, role, and what to list as in embed
            - optional colour 
            - role and channel can be both the mention or just name
        '''

        # abort at anytime with keyword 'exit' alone
 
        # title = await self.bot.wait_for('message', check=ch)
        # if(title == 'exit'):
        #     await ctx.send('react embed creation aborted')
        #     return

        # description = await self.bot.wait_for('message', check=ch)
        # if(description == 'exit'):
        #     await ctx.send('react embed creation aborted')
        #     return

        # # content => while

        # # colour
        # colour = await self.bot.wait_for('message', check=ch)
        # if(colour == 'exit'):
        #     await ctx.send('react embed creation aborted')
        #     return

        # # thumbnail
        # thumbnail = await self.bot.wait_for('message', check=ch)
        # if(thumbnail == 'exit'):
        #     await ctx.send('react embed creation aborted')
        #     return

        # # footer
        # footer = await self.bot.wait_for('message', check=ch)
        # if(footer == 'exit'):
        #     await ctx.send('react embed creation aborted')
        #     return

        # m = await self.bot.wait_for('message', check=check(ctx.author, ctx.channel))
        # print(m.content)
        # await ctx.send(m.content)
        # await ctx.send(m)

        print(em)
        await ctx.send('done')
