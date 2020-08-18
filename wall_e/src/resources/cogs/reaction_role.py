from discord.ext import commands
import logging
logger = logging.getLogger('wall_e')

class ReactionRole(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @commands.command()
    async def reactrole(self, ctx, *args):
        logger.info("[ReactionRole reactRole()] testing")
        await ctx.send("```it's working.........```")