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


class ReactionRole(commands.Cog):

    def __init__(self, bot: discord.Client, config):
        self.bot = bot
        emoji_file = open('resources/locales/emoji-compact.json')
        self.emojis = json.load(emoji_file)
        emoji_file.close()
        self.react_msgs = {}
        self.CHANNEL_PROMPT = "Which channel do you want the message in? `#` mention the channel."
        self.TITLE_PROMPT = "Provide a title for the message. You can use Discord markup in the title."
        self.COLOUR_PROMPT = ("Enter a colour for the embed, in hex format. Enter `none` to use default colour.\n"
                              "**Need helping picking a color?** Check out: <https://htmlcolorcodes.com/>")
        self.ROLES_PROMPT = ("Add emojis and roles. Add then one at a time, when done type `done`.\n"
                             "Enter in this format:\n```<emoji>, <@role>, [optional description]```"
                             "Make sure the args are comma seperated.\n"
                             "**Example**:\n:smiling_imp:, Froshee\n :snake:,Tab-Life, React if ur python gang")


    @commands.Cog.listener(name='on_ready')
    async def load_from_db(self):
        print('loading react messages')
        react_roles = await ReactRoles.get_all_react_roles()

        for react_role in react_roles:
            print(f'\tloading: {react_role}')
            self.react_msgs.update( { react_role[0]: json.loads(react_role[1]) } )
        print(self.react_msgs)

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
                return None
        return ret

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
        return react_msg

    async def watch_react_msg(self, ctx, react_msg: discord.Message, data):
        # add msg_id and data as a {msg_id: {emoji_id:role_id, ...}}\
        emoji_role = {}
        for key in data:
            emoji = key.id if key not in self.emojis else key
            emoji_role.update({str(emoji): data[key][0].id})

        react_dict = {react_msg.id: emoji_role}
        self.react_msgs.update(react_dict)

        # add to db
        await self.update_database(react_msg.id, emoji_role, react_msg.channel, ctx.author)

    async def update_database(self, msg_id, react_bindings, channel: discord.ChannelType, author: discord.Member):

        react_role = ReactRoles(
                                message_id=msg_id,
                                channel_id=channel.id,
                                emoji_role_binding=json.dumps(react_bindings),
                                author_id=author.id,
                                author_name=author.name+'#'+author.discriminator,
                                created_on=datetime.datetime.now(pytz.utc).timestamp()
                                )
        await ReactRoles.insert(react_role)

    @commands.command(aliases=['rr'])
    async def reactrole(self, ctx):
        logger.info("[ReactionRole reactRole()] starting interactive process to create react role embed")
        try:
            # get channel
            channel = await self.request(ctx,self.CHANNEL_PROMPT, converter=commands.TextChannelConverter())

            # check if channel found or not
            if type(channel) != discord.TextChannel:
                await ctx.send(f'Channel "{channel}" not found. Redo command to try again.')
                logger.info(f'[ReactionRole reactrole()] channel "{channel}" not found. Command exection terminated.')
                return
            logger.info(f'[ReactionRole reactrole()] channel to send react role confirmed: {channel}')

            # get title for
            title = await self.request(ctx, self.TITLE_PROMPT)
            logger.info(f'[ReactionRole reactrole()] react role title set to: {title}')

            # get colour
            colour = await self.request(ctx, self.COLOUR_PROMPT, commands.ColourConverter(), 120)

            # check if valid otherwise set to default
            if not colour:
                colour = discord.Color.blurple()
            await ctx.send('Using default colour:' if colour==discord.Color.blurple() else 'Colour set to:')
            await ctx.send(f'https://singlecolorimage.com/get/{colour.value:x}/50x50')
            logger.info(f'[ReactionRole reactrole()] react role colour is: {colour}')

            # emoji, role, optional message
            await ctx.send(self.ROLES_PROMPT)

            role_binding = {}
            roles = []
            while True:
                msg = await self.bot.wait_for('message', check=self.check(ctx.author, ctx.channel), timeout=60.0)
                if msg.content == 'done':
                    break

                # parse message into parts
                erd = dict(zip(['emoji', 'role', 'desc'], map(lambda s: s.strip(), msg.content.split(','))))
                try:
                    if not is_emoji(erd['emoji']):
                        erd['emoji'] = await commands.PartialEmojiConverter().convert(ctx, erd['emoji'])
                    erd['role'] = await commands.RoleConverter().convert(ctx, erd['role'])
                except Exception as e:
                    await msg.add_reaction('\N{CROSS MARK}')
                    await ctx.send(f'{"Role"if isinstance(e, commands.RoleNotFound) else "Emoji"} not found.')
                    continue

                if erd['emoji'] in role_binding.keys() or erd['role'] in roles:
                    await msg.add_reaction('\N{BLACK QUESTION MARK ORNAMENT}')
                    await ctx.send(f'{erd["emoji"]} and/or {erd["role"].mention} is already bound')
                    continue

                roles.append(erd['role'])
                role_binding.update( {erd['emoji']: [ erd['role'], erd.get('desc') ]} )
                await msg.add_reaction('\N{WHITE HEAVY CHECK MARK}')

        except asyncio.TimeoutError:
            await ctx.send('You took too long.\nBye \N{WAVING HAND SIGN}')
            return

        # make and send the reaction role
        react_msg = await self.send_react_message(ctx, channel, title, colour, role_binding)
        await self.watch_react_msg(ctx, react_msg, role_binding)
        # call add to db here and provide channel id as well

    @commands.Cog.listener() # TODO: emoji payload can be 1 line with ternery op on emoji.id
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # checks for user reactions and if they're using a reaction message
        if self.bot.user.id == payload.user_id:
            return
        print(f"payload emoji: {payload.emoji}", f"emoji id: {payload.emoji.id}", f"emoji name: {payload.emoji.name}")
        print(f"emoji id type: {type(payload.emoji.id)}")
        msg = payload.message_id
        print(self.react_msgs[msg])
        if msg in self.react_msgs:
            user = payload.member
            try:
                role_id = self.react_msgs[msg][ str(payload.emoji.id)]
            except KeyError:
                try:
                    role_id = self.react_msgs[msg][ str(payload.emoji.name)]
                except KeyError:
                    # most like another emoji was added to the message but its not part of the role bindings
                    print('non binding emoji reaction detected')
                    return
            guild = self.bot.get_guild(payload.guild_id)
            role: discord.Role = discord.utils.get(guild.roles, id=role_id)

            try:
                await user.add_roles(role)
            except discord.Forbidden:
                channel = self.bot.get_channel(payload.channel_id)
                await channel.send(f'What the *#%& is this ^@%)!!\nI don\'t have permission to give {user.mention}'
                                   f'the \"{role.name}\" role')

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        # removes roles on unreacting on a reaction message
        if self.bot.user.id == payload.user_id:
            return
        print(payload)

        msg = payload.message_id
        if msg in self.react_msgs:
            guild = self.bot.get_guild(payload.guild_id)
            user = guild.get_member(payload.user_id)
            print(user)
            try:
                role_id = self.react_msgs[msg][str(payload.emoji.id)]
            except KeyError:
                try:
                    role_id = self.react_msgs[msg][str(payload.emoji.name)]
                except KeyError:
                    print('non binding emoji reaction detected')
                    return
            role: discord.Role = discord.utils.get(guild.roles, id=role_id)

            try:
                await user.remove_roles(role)
            except discord.Forbidden:
                channel = self.bot.get_channel(payload.channel_id)
                await channel.send(f'What the *#%& is this ^@%)!!\nI don\'t have permission to remove "{role.name}" '
                                   f'role from{user.mention}')

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