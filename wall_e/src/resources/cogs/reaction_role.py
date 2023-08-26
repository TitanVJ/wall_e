import re
import discord
from discord.ext import tasks, commands
import logging
import json
import asyncio
from resources.utilities.embed import embed
import psycopg2
import datetime
import pytz
from WalleModels.models import ReactRoles
import json
from emoji import is_emoji
logger = logging.getLogger('wall_e')


class ExitException(Exception):
    """Better semantics using this class for user exit."""
    pass

class ReactionRole(commands.Cog):

    def __init__(self, bot: discord.Client, config):
        self.bot = bot
        self.config = config
        emoji_file = open('resources/locales/emoji-compact.json')
        self.emojis = json.load(emoji_file)
        emoji_file.close()
        self.react_msgs = {}
        self.CHANNEL_PROMPT = "## Which channel do you want the message in?"
        self.TITLE_PROMPT = "## Provide a title for the message. You can use Discord markup in the title."
        self.COLOUR_PROMPT = ("## Enter a colour for the embed in hex format. Enter `none` to use default colour.\n"
                              "**Need helping picking a color?** Check out: <https://htmlcolorcodes.com/>")
        self.ROLES_PROMPT = ("## Add emojis and roles one at a time, when done type `done`.\n"
                             "Enter in this format:\n```emoji, @role, optional description```"
                             "Comma seperate the args. Description can include Discord markup.\n"
                             "**Example**:\n:smiling_imp:, @Froshee\n :snake:, @Tab-Life, React for **python** gang")

    @commands.Cog.listener(name='on_ready')
    async def load(self):
        mod_channel_name = self.config.get_config_value('basic_config', 'MOD_CHANNEL')
        self.mod_channel = discord.utils.get(self.bot.guilds[0].channels, name=mod_channel_name)
        logger.info('[ReactionRole load()] mod channel loaded')
        logger.info('[ReactionRole load()] loading react role messages')
        react_roles = await ReactRoles.get_all_react_roles()

        for react_role in react_roles:
            self.react_msgs.update( { react_role[0]: json.loads(react_role[1]) } )
        logger.info(f'[ReactionRole load()] done loading. {len(react_roles)} messages loaded.')

    async def request(self, ctx, prompt='', case_s=False, converter=None, timeout=60.0):
        def check(author: discord.user, channel: discord.channel):
            return lambda m: m.author == author and m.channel == channel
        input_check = check(ctx.author, ctx.channel)

        if prompt: await ctx.send(prompt)
        msg = await self.bot.wait_for('message', check=input_check, timeout=timeout)
        ret = msg.content
        if ret.lower() == 'exit': raise ExitException
        if not case_s: ret = ret.lower()

        if converter:
            try:
                ret = await converter.convert(ctx, ret)
            except Exception:
                return None, msg
        return ret, msg

    async def make(self, ctx):
        logger.info("[ReactionRole make()] starting interactive process to create react role embed")

        await ctx.send("## To terminate process at any point type `exit`")
        try:
            # Get channel
            channel, _ = await self.request(ctx, self.CHANNEL_PROMPT, converter=commands.TextChannelConverter())
            if not channel:
                await ctx.send(f'Channel not found. Redo command to try again.')
                logger.info('[ReactionRole make()] channel not found. Command terminated.')
                return
            if not self.bot.guilds[0].me.permissions_in(channel).send_messages:
                await ctx.send(f'I do not have send permission in {channel.mention}. Command terminated.')
                logger.info(f'[ReactionRole make()] No send permission in {channel}. Command terminated')
                return

            logger.info(f'[ReactionRole make()] channel to send react role confirmed: {channel}')

            # Get title for
            title, _ = await self.request(ctx, self.TITLE_PROMPT, case_s=True)
            logger.info(f'[ReactionRole make()] react role title set to: {title}')

            # Get colour
            colour, _ = await self.request(ctx, self.COLOUR_PROMPT, converter=commands.ColourConverter(), timeout=120)
            if not colour:
                colour = discord.Color.blurple()
            logger.info(f'[ReactionRole make()] react role colour is: {colour}')
            await ctx.send('Using default colour:' if colour==discord.Color.blurple() else 'Colour set to:')
            await ctx.send(f'https://singlecolorimage.com/get/{colour.value:x}/50x50')

            # Get emoji, role, optional message
            await ctx.send(self.ROLES_PROMPT)

            emojis = {}
            role_ids = []
            em_desc = []
            descs = []
            while True:
                content, msg = await self.request(ctx, case_s=True)
                if content == 'done': break

                # parse message into parts
                erd = list(map(lambda s: s.strip(), content.split(',')))
                emoji, role = erd[0], erd[1]
                desc = None if len(erd) < 3 else erd[2]
                try:
                    if not is_emoji(emoji):
                        emoji = await commands.PartialEmojiConverter().convert(ctx, emoji)
                    role = await commands.RoleConverter().convert(ctx, role)
                except Exception as e:
                    await msg.add_reaction('\N{CROSS MARK}')
                    await ctx.send(f'{"Role"if isinstance(e, commands.RoleNotFound) else "Emoji"} not found')
                    continue

                if emoji in emojis.keys() or role.id in role_ids:
                    await msg.add_reaction('\N{BLACK QUESTION MARK ORNAMENT}')
                    await ctx.send(f'{emoji} and/or {role.mention} is already bound')
                    continue

                em_desc.append(f'{emoji} {role.mention} {f"- {desc}" if desc else ""}')
                descs.append(desc if desc else "")
                emojis.update({ emoji : emoji if is_emoji(emoji) else str(emoji.id)})
                role_ids.append(role.id)
                await msg.add_reaction('\N{WHITE HEAVY CHECK MARK}')
                logger.info(f'[ReactionRole make()] emoji role pair added: {emoji} - {role}')
        except asyncio.TimeoutError:
            await ctx.send('You took too long.\nBye \N{WAVING HAND SIGN}')
            logger.info("[ReactionRole make()] Timeout. Process terminated.")
            return
        except ExitException:
            logger.info("[ReactionRole make()] Caller involked exit. Process terminated.")
            return
        except Exception as e:
            logger.info("[ReactionRole make()] Unknown exception: {e}")
            return

        # Create, send react message, and add reactions
        rr_embed = await embed(
            ctx,
            title=title,
            colour=colour,
            description='\n'.join(em_desc)
        )
        if not rr_embed: return

        react_msg = await channel.send(embed=rr_embed)
        for emoji in emojis.keys():
            await react_msg.add_reaction(emoji)
        logger.info("[ReactionRole make()] React role message created and sent.")

        # Update local and database
        emoji_roles = dict(zip(emojis.values(), role_ids))
        self.react_msgs.update({react_msg.id : emoji_roles})

        rr = ReactRoles(
            message_id=react_msg.id,
            channel_id=channel.id,
            title=title,
            colour=f"{colour.value:x}",
            emoji_roles=json.dumps(emoji_roles),
            descriptions=json.dumps(descs),
            author=ctx.author.name+'#'+ctx.author.discriminator,
            author_id=ctx.author.id,
            created_on=datetime.datetime.now(pytz.utc).timestamp()
        )
        await ReactRoles.insert(rr)
        logger.info("[ReactionRole make()] Database and local watchlist updated with react role.")

        # Clean up
        def check(msg: discord.Message):
            return msg.author in [ctx.author, self.bot.user] and msg.created_at >= ctx.message.created_at
        await ctx.channel.purge(check=check)
        logger.info("[ReactionRole make()] purged all message part of the creation process")

        # Send rr link to user
        await ctx.send(f'Here\'s your reaction role message: {react_msg.jump_url}')

    @commands.command(aliases=['rr'])
    async def reactrole(self, ctx, *cmd):
        if not cmd:
            err = ("## Error \N{LARGE RED CIRCLE}\nUsage: `.rr/reactrole <cmd>`\n### Commands:\n"
                   "- `make/create`: Create new react message\n"
                   "- `list`: List all react messages\n"
                   "- `add message_id`: Add emoji-role pair to existing react message w/ id=`message_id`\n"
                   "- `remove message_id`: Remove emoji-role pair from existing react message w/ id=`message_id`")
            await ctx.send(err)
            return

        cmd = cmd[0].lower()
        if cmd in ['make', 'create']:
            logger.info("[ReactionRole reactrole()] make")
            await self.make(ctx)

    @commands.Cog.listener(name='on_raw_reaction_add')
    @commands.Cog.listener(name='on_raw_reaction_remove')
    async def react(self, payload: discord.RawReactionActionEvent):
        if self.bot.user.id == payload.user_id: return
        msg = payload.message_id
        user = None
        action = None
        action_str = ''
        guild = self.bot.get_guild(payload.guild_id)
        emoji = payload.emoji
        emoji = str(emoji.id) if emoji.id else emoji.name

        if payload.event_type == 'REACTION_ADD':
            user = payload.member
            action = user.add_roles
            action_str = 'given to'
        else:
            user = guild.get_member(payload.user_id)
            action = user.remove_roles
            action_str = 'removed from'

        try:
            role_id = self.react_msgs[msg][emoji]
            role: discord.Role = discord.utils.get(guild.roles, id=role_id)
            await action(role)
            logger.info(f"[ReactionRole on_raw_reaction_add()] role @{role} {action_str} {user} via react")
        except KeyError:
            return
        except discord.Forbidden:
            await self.mod_channel.send("I don't have role management permission? Figure it out.")
            logger.info("[ReactionRole react()] Permissions error. Mods notified.")

    # @tasks.loop(hours=24.0)
    # async def cleanup():
    #     # check if all reaction roles still exist otherwise

    #     sql_get_all = 'SELECT message_id FROM Reaction_role;'

    #     try:
    #         self.curs.execute(sql_get_all)
    #     except Exception as e:
    #         print(f'Cleanup get all error: {e}')

    #     msg_ids = self.curs.fetchall()
    #     for row in msg_ids:
    #         self.bot.get_channel()