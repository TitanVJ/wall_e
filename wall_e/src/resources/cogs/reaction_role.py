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
        self.CHANNEL_PROMPT = "## Which channel do you want the message in?"
        self.TITLE_PROMPT = "## Provide a title for the message. You can use Discord markup in the title."
        self.COLOUR_PROMPT = ("## Enter a colour for the embed in hex format. Enter `none` to use default colour.\n"
                              "**Need helping picking a color?** Check out: <https://htmlcolorcodes.com/>")
        self.ROLES_PROMPT = ("## Add emojis and roles one at a time, when done type `done`.\n"
                             "Enter in this format:\n```emoji, @role, optional description```"
                             "Comma seperate the args. Description can include Discord markup.\n"
                             "**Example**:\n:smiling_imp:, @Froshee\n :snake:, @Tab-Life, React for **python** gang")

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

    async def request(self, ctx, prompt='', case_s=False, converter=None, timeout=60.0):
        input_check = self.check(ctx.author, ctx.channel)

        if prompt: await ctx.send(prompt)
        msg = await self.bot.wait_for('message', check=input_check, timeout=timeout)
        ret = msg.content
        if ret.lower() == 'exit': raise Exception
        if not case_s: ret = ret.lower()

        if converter:
            try:
                ret = await converter.convert(ctx, ret)
            except Exception:
                return None, msg
        return ret, msg

    @commands.command(aliases=['rr'])
    async def reactrole(self, ctx):
        logger.info("[ReactionRole reactRole()] starting interactive process to create react role embed")

        await ctx.send("## To terminate process at any point type `exit`")
        try:
            # Get channel
            channel, _ = await self.request(ctx, self.CHANNEL_PROMPT, converter=commands.TextChannelConverter())
            if not channel:
                await ctx.send(f'Channel not found. Redo command to try again.')
                logger.info(f'[ReactionRole reactrole()] channel not found. Command exection terminated.')
                return
            logger.info(f'[ReactionRole reactrole()] channel to send react role confirmed: {channel}')

            # Get title for
            title, _ = await self.request(ctx, self.TITLE_PROMPT, case_s=True)
            logger.info(f'[ReactionRole reactrole()] react role title set to: {title}')

            # Get colour
            colour, _ = await self.request(ctx, self.COLOUR_PROMPT, converter=commands.ColourConverter(), timeout=120)
            if not colour:
                colour = discord.Color.blurple()
            logger.info(f'[ReactionRole reactrole()] react role colour is: {colour}')
            await ctx.send('Using default colour:' if colour==discord.Color.blurple() else 'Colour set to:')
            await ctx.send(f'https://singlecolorimage.com/get/{colour.value:x}/50x50')

            # Get emoji, role, optional message
            await ctx.send(self.ROLES_PROMPT)

            emojis = {}
            role_ids = []
            desc_lst = []
            while True:
                content, msg = await self.request(ctx, case_s=True)
                if content == 'done': break

                # parse message into parts
                erd = list(map(lambda s: s.strip(), content.split(',')))
                emoji, role = erd[0], erd[1]
                desc = None if len(erd) < 3 else erd[2]
                print(f'e:{emoji} r:{role} d:{desc}')
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

                desc_lst.append(f'{emoji} {role.mention} {f"- {desc}" if desc else ""}')
                emojis.update({ emoji : emoji if is_emoji(emoji) else str(emoji.id)})
                role_ids.append(role.id)
                await msg.add_reaction('\N{WHITE HEAVY CHECK MARK}')

        except asyncio.TimeoutError:
            await ctx.send('You took too long.\nBye \N{WAVING HAND SIGN}')
            return
        except Exception:
            logger.info("[ReactionRole reactRole()] Caller involked exit. Process terminated.")
            return

        # Create, send react message, and add reactions
        rr_embed = await embed(
            ctx,
            title=title,
            colour=colour,
            description='\n'.join(desc_lst)
        )
        if not rr_embed: return

        react_msg = await channel.send(embed=rr_embed)
        for emoji in emojis.keys():
            await react_msg.add_reaction(emoji)

        # Update local and database
        emoji_roles = dict(zip(emojis.values(), role_ids))
        self.react_msgs.update({react_msg.id : emoji_roles})

        rr = ReactRoles(
            message_id=react_msg.id,
            channel_id=channel.id,
            emoji_role_binding=json.dumps(emoji_roles),
            author_id=ctx.author.id,
            author_name=ctx.author.name+'#'+ctx.author.discriminator,
            created_on=datetime.datetime.now(pytz.utc).timestamp()
        )
        await ReactRoles.insert(rr)

        # Send rr link to user
        await ctx.send(f'Here\'s your reaction role message: {react_msg.jump_url}')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # checks for user reactions and if they're using a reaction message
        if self.bot.user.id == payload.user_id: return
        print(f"payload emoji: {payload.emoji}", f"emoji id: {payload.emoji.id}", f"emoji name: {payload.emoji.name}")
        print(f"emoji id type: {type(payload.emoji.id)}")
        msg = payload.message_id
        print(self.react_msgs[msg])
        if msg in self.react_msgs:
            guild = self.bot.get_guild(payload.guild_id)
            user = payload.member
            emoji = payload.emoji
            emoji = str(emoji.id) if emoji.id else emoji.name
            try:
                role_id = self.react_msgs[msg][emoji]
                role: discord.Role = discord.utils.get(guild.roles, id=role_id)
                await user.add_roles(role)
            except KeyError:
                print('non binding emoji')
                return
            except discord.Forbidden:
                logger.info("[ReactionRole on_raw_reaction_add()] @Minions I don't have role management perms.")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        # removes roles on unreacting on a reaction message
        if self.bot.user.id == payload.user_id: return
        print(payload)

        msg = payload.message_id
        if msg in self.react_msgs:
            guild = self.bot.get_guild(payload.guild_id)
            user = guild.get_member(payload.user_id)
            emoji = payload.emoji
            emoji = str(emoji.id) if emoji.id else emoji.name
            print(user)
            try:
                role_id = self.react_msgs[msg][emoji]
                role: discord.Role = discord.utils.get(guild.roles, id=role_id)
                await user.remove_roles(role)
            except KeyError:
                print('non binding emoji')
                return
            except discord.Forbidden:
                logger.info("[ReactionRole on_raw_reaction_remove()] @Minions I don't have role management perms.")

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