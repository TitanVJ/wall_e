import discord
from discord.ext import commands
import logging
import json
import asyncio
from resources.utilities.embed import embed
import psycopg2
logger = logging.getLogger('wall_e')


class ReactionRole(commands.Cog):

    def __init__(self, bot: discord.Client, config):
        self.bot = bot
        self.config = config
        emoji_file = open('resources/locales/emoji-compact.json')
        self.emojis = json.load(emoji_file)
        emoji_file.close()
        self.react_msgs = {}

        # establish connection to db
        try:
            if self.config.get_config_value('basic_config', 'ENVIRONMENT') == 'LOCALHOST':
                host = 'localhost'
            else:
                host = '{}_wall_e_db'.format(self.config.get_config_value('basic_config', 'COMPOSE_PROJECT_NAME'))

            db_connection_string = (
                f"dbname='{self.config.get_config_value('database', 'WALL_E_DB_DBNAME')}'"
                f"user='{self.config.get_config_value('database', 'WALL_E_DB_USER')}' host='{host}'"
            )
            logger.info("[ReactionRole __init__] db_connection_string=[{}]".format(db_connection_string))

            conn = psycopg2.connect(
                "{}  password='{}'".format(
                    db_connection_string, self.config.get_config_value('database', 'WALL_E_DB_PASSWORD')
                )
            )
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            self.curs = conn.cursor()
            self.curs.execute('CREATE TABLE IF NOT EXISTS Reaction_role ('
                              'message_id bigserial PRIMARY KEY, '
                              'binders jsonb,'
                              'author_name varchar(500),'
                              'author_id bigserial'
                              ');')
            logger.info("[ReactionRole __init__] PostgreSQL connection established")
        except Exception as e:
            logger.error("[Reminders __init__] enountered following exception when setting up PostgreSQL "
                         f"connection\n{e}")

        # load from db

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
        return react_msg

    async def watch_react_msg(self, ctx, react_msg: discord.Message, data):
        # add msg_id and data as a {msg_id: {emoji_id:role_id, ...}}\
        emoji_role = {}
        for key in data:
            emoji_role.update({key: data[key][0].id})

        react_dict = {react_msg.id: emoji_role}
        self.react_msgs.update(react_dict)

        # add to db
        await self.update_database(react_dict, ctx.author)

    async def update_database(self, react_dict, author: discord.Member):
        # add row for the new

        # covert any partial emoji keys to use it's id instead
        react_list = list(map(list, list(list(react_dict.values())[0].items())))
        for emoji in react_list:
            emoji[0] = emoji[0].id if emoji[0] not in self.emojis else emoji[0]

        key = list(react_dict.keys())[0]
        try:
            react_json = json.dumps(react_list)
        except Exception as e:
            print(f'json error: {e}')

        sql_command = ('INSERT INTO Reaction_role (message_id, binders, author_name, author_id) VALUES '
                       '(%s, %s, %s, %s);')

        try:
            self.curs.execute(sql_command, (key, react_json, author.name, author.id))
        except Exception as e:
            print(f'sql error {e}')

    @commands.command(aliases=['rr'])
    async def reactrole(self, ctx):
        logger.info("[ReactionRole reactRole()] starting interactive process to create react role embed")
        try:
            # get channel
            status, channel = await self.request(
                ctx,
                prompt='What channel do you want the message in?',
                converter=commands.TextChannelConverter()
            )

            # check if channel found or not
            if not status:
                await ctx.send(f'Channel "{channel}" not found. Redo command to try again.')
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
                    await ctx.send('Using default colour.')
                else:
                    await ctx.send(f'"{colour}" is not a valid hex value. Using default.')
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

            role_binding = {}
            while True:
                msg = await self.bot.wait_for('message', check=self.check(ctx.author, ctx.channel), timeout=60.0)
                if msg.content == 'done':
                    break

                info = await self.parse(ctx, msg)

                if info is None:
                    await msg.add_reaction('\N{CROSS MARK}')
                    continue

                # check if emoji or is already bound
                roles = [role[0] for role in list(role_binding.values())]
                if info[0] in list(role_binding.keys()) or info[1] in roles:
                    await msg.add_reaction('\N{BLACK QUESTION MARK ORNAMENT}')
                    await ctx.send(f'{info[0]} and/or {info[1].mention} is already bound')
                    continue

                role_binding.update({info[0]: info[1:]})
                await msg.add_reaction('\N{WHITE HEAVY CHECK MARK}')

        except asyncio.TimeoutError:
            await ctx.send('You took too long.\nBye \N{WAVING HAND SIGN}')
            return

        # make and send the reaction role
        react_msg = await self.send_react_message(ctx, channel, title, colour, role_binding)
        await self.watch_react_msg(ctx, react_msg, role_binding)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # checks for user reactions and if they're using a reaction message
        if self.bot.user.id == payload.user_id:
            return

        msg = payload.message_id
        if msg in self.react_msgs:
            user = payload.member
            try:
                role_id = self.react_msgs[msg][payload.emoji]
            except KeyError:
                try:
                    role_id = self.react_msgs[msg][payload.emoji.name]
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
                role_id = self.react_msgs[msg][payload.emoji]
            except KeyError:
                try:
                    role_id = self.react_msgs[msg][payload.emoji.name]
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
