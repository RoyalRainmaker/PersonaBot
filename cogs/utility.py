import random
import discord
from discord.ext import commands
import os
import re
import asyncio
import itertools
import datetime, humanize
import math

class HelpPages:
    'A paginator class to paginate the help command'
    def __init__(self, ctx, entries, per_page=6, preset_header=False):
        self.ctx = ctx
        self.entries = entries
        self.per_page = per_page
        self.preset = preset_header
        
        # makeshift clean prefix
        if re.match(r'<@!?[0-9]+>', ctx.prefix):
            self.ctx.prefix = f'@{ctx.bot.user.name} '
        
        self.max_pages = math.ceil(len(self.entries) / self.per_page)
        self.embed = discord.Embed(colour=ctx.cyan)
        self.buttons = [['⏮️', self.first],
                        ['◀️', self.previous],
                        ['⏹️', self.stop],
                        ['▶️', self.next],
                        ['⏭️', self.last],
                        ['ℹ️', self.signature_help]]

    def command_header(self, page):
        cog, description, commands = self.entries[page - 1]
        self.title = f'{cog} Commands'
        self.description = description
        return commands

    def get_page(self, page):
        base = (page - 1) * self.per_page
        return self.entries[base:base + self.per_page]

    async def show_page(self, page, initial=False):
        self.current_page = page
        
        if self.preset:
            entries = self.command_header(page)
        else:
            entries = self.get_page(page)
        
        self.embed.clear_fields()
        self.embed.title = self.title
        self.embed.description = self.description
        for entry in entries:
            signature = getattr(entry, 'old_signature', entry.signature)
            self.embed.add_field(name=f'{str(entry)} {signature}', value=entry.description or entry.short_doc or 'No description', inline=False)
        self.embed.set_footer(text=f'Page {page}/{self.max_pages}   Use {self.ctx.prefix}help [command] for help on a command or cog')

        perms = self.ctx.channel.permissions_for(self.ctx.me)

        if not perms.send_messages:
            # trying to tell them wont do anything
            return

        if not perms.embed_links:
            return await self.ctx.send('I cannot continue the command as I lack the permission to embed')

        if not initial:
            return await self.message.edit(embed=self.embed)
        
        self.message = await self.ctx.send(embed=self.embed)
        
        for reaction, _ in self.buttons:
            if self.max_pages <= 2 and reaction in ['⏮️', '⏭️']:
                continue
            # put it here during adding reactions
            # this ensures that if the reaction permission is removed, the user knows immediately
            # however, once theyre added, they are still usable
            try:
                await self.message.add_reaction(reaction)
            except discord.Forbidden:
                return await self.ctx.send('I cannot continue the command as I lack the permission to add reactions')
            
    async def first(self):
        await self.show_page(1)

    async def last(self):
        await self.show_page(self.max_pages)

    async def previous(self):
        # this is to check if we are on the last page
        # if so, switch to it
        if self.current_page == 1:
            await self.show_page(1)
        
        previous_page = self.current_page - 1
        if previous_page > 0:
            await self.show_page(previous_page)

    async def next(self):
        if self.current_page == self.max_pages:
            await self.show_page(self.max_pages)
        
        next_page = self.current_page + 1
        if next_page <= self.max_pages:
            await self.show_page(next_page)

    async def stop(self):
        await self.message.delete()

    async def signature_help(self):
        self.embed.clear_fields()
        self.embed.title = 'Reading the bot commands'
        self.embed.description = '**Do not type in the brackets when providing inputs**'
        self.embed.add_field(name='<text>', value='This means that the input is required')
        self.embed.add_field(name='[text] or [text=value]', value='This means that the input is optional, and the equal sign means the value it will default to', inline=False)
        self.embed.add_field(name='[text...] or [text]...', value='This means that you can provide as many inputs as you want', inline=False)
        self.embed.add_field(name='Aliases', value='This means the command can be invoked with the provided aliases', inline=False)
        self.embed.set_footer(text=f'Special Page   Use {self.ctx.prefix}help [command] for help on a command or cog')
        await self.message.edit(embed=self.embed)

    async def start(self):
        # using a task means the buttons can be used even before theyre all loaded
        asyncio.create_task(self.show_page(1, initial=True))

        def check(payload):
            if payload.user_id != self.ctx.author.id or payload.message_id != self.message.id:
                return False

            for button, effect in self.buttons:
                if str(payload.emoji) == button:
                    self.effect = effect
                    return True

        while True:
            try:
                payload = await self.ctx.bot.wait_for('raw_reaction_add', check=check, timeout=180)
            except asyncio.TimeoutError:
                try:
                    return await self.message.delete()
                except:
                    return

            try:
                await self.message.remove_reaction(payload.emoji, discord.Object(payload.user_id))
            except:
                pass

            await self.effect()

class HelpCommand(commands.HelpCommand):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.key = lambda c: str(c)
    
    async def send_bot_help(self):
        key = lambda c: c.cog_name or 'Miscellaneous'
        command_list = []
        per_page = 7

        for cog, commands in itertools.groupby(await self.filter_commands(self.context.bot.commands, sort=True, key=key), key):
            # alphabetizes the commands
            commands = sorted(sorted(commands, key=key), key=self.key)
            
            if len(commands) == 0: 
                continue
            
            cog_desc = self.context.bot.get_cog(cog)
            command_list.extend((cog, (cog_desc and cog_desc.description) or discord.Embed.Empty, commands[i:i + per_page]) for i in range(0, len(commands), per_page))

        pages = HelpPages(self.context, command_list, per_page=1, preset_header=True)
        await pages.start()

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True, key=self.key)
        
        # gatekeeping
        if len(entries) == 0:
            return await self.context.send('There does not seem to be any commands for this cog, or it is locked to you')
        
        pages = HelpPages(self.context, entries)
        pages.title = f'{cog.qualified_name} Commands'
        pages.description = cog.description
        await pages.start()

    async def send_group_help(self, group):
        commands = await self.filter_commands(group.commands, sort=True, key=self.key)
        
        if len(commands) == 0:
            return await self.send_command_help(group)

        pages = HelpPages(self.context, commands)
        pages.title = f'{str(group)} {group.signature}'
        aliases = ' | '.join(group.aliases)
        desc = ''
        
        if aliases:
            desc += f'**Aliases:** {aliases}\n'
        if group.description:
            desc += f'{group.description}\n'
        if group.help:
            desc += f'{group.help}'
        
        if desc:
            pages.description = desc
        
        await pages.start()
    
    async def send_command_help(self, command):
        aliases = ' | '.join(command.aliases)
        signature = getattr(command, 'old_signature', command.signature)
        embed = discord.Embed(title=f'{str(command)} {signature}', colour=self.context.cyan, description=f'**Aliases:** {aliases}' if aliases else discord.Embed.Empty)
        desc = ''

        if command.description:
            desc += f'{command.description}\n'
        if command.help:
            desc += f'{command.help}'
        
        if desc:
            embed.add_field(name='Description', value=desc)
        
        await self.context.send(embed=embed)

    async def command_callback(self, ctx, *, command=None):
        # the only reason i do this is to capitalize the cog name
        # normally, cogs are case sensitive
        # there was no better alternitive of doing this 

        if not command:
            return await self.send_bot_help()

        cog = ctx.bot.get_cog(command.capitalize())
        
        if cog:
            return await self.send_cog_help(cog)

        keys = command.split(' ')
        cmd = ctx.bot.all_commands.get(keys[0])
        
        if not cmd:
            return await self.context.send(f'I could not find a command called `{keys[0]}`')

        for key in keys[1:]:
            found = cmd.all_commands.get(key)
            
            if not found:
                if len(cmd.all_commands) > 0:
                    return await self.context.send(f'I could not find a subcommand called `{key}`')
                return await self.context.send(f'The `{cmd}` command has no subcommands')
            
            cmd = found

        if isinstance(cmd, commands.Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)

class Utility(commands.Cog):
    'General commands for everyday Discord'
    def __init__(self, bot):
        self.bot = bot
        bot.help_command = HelpCommand()
        bot.help_command.cog = self

    @commands.Cog.listener()
    async def on_message(self, message):
        # for my suggesstions channel
        if message.channel.id == 765409273433686057:
            await message.add_reaction('✅')
            await message.add_reaction('❌')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id == 765421743573434428:
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            emoji_correlation = {'<:CK_RedGem:765424509770924033>': guild.get_role(765421836208439316), 
                                 '<:CK_OrangeGem:765424586119577610>': guild.get_role(765421981524688896),
                                 '<:CK_YellowGem:765424631992680479>': guild.get_role(765422057231089674),
                                 '<:CK_GreenGem:765425324296765471>': guild.get_role(765422145224048650),
                                 '<:CK_BlueGem:765425378008891424>': guild.get_role(765422184452587530),
                                 '<:CK_PurpleGem:765424416552124508>': guild.get_role(765422225175216139),
                                 '👍': guild.get_role(690738886565036084)}
            
            role = emoji_correlation.get(str(payload.emoji))
            
            if role:
                await member.add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.channel_id == 765421743573434428:
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            emoji_correlation = {'<:CK_RedGem:765424509770924033>': guild.get_role(765421836208439316), 
                                 '<:CK_OrangeGem:765424586119577610>': guild.get_role(765421981524688896),
                                 '<:CK_YellowGem:765424631992680479>': guild.get_role(765422057231089674),
                                 '<:CK_GreenGem:765425324296765471>': guild.get_role(765422145224048650),
                                 '<:CK_BlueGem:765425378008891424>': guild.get_role(765422184452587530),
                                 '<:CK_PurpleGem:765424416552124508>': guild.get_role(765422225175216139)}
            
            role = emoji_correlation.get(str(payload.emoji))
            
            if role:
                await member.add_roles(role)

    @commands.command(description="Check the bot's ping")
    async def ping(self, ctx):
        await ctx.send(f'{(self.bot.latency * 1000):.2f} milliseconds')

    @commands.command(description='Invite the bot to your server')
    async def invite(self, ctx):
        await ctx.send(f'<https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=271665216&scope=bot>')

    @commands.command(description='How long the bot has been up for')
    async def uptime(self, ctx):
        await ctx.send(humanize.precisedelta(datetime.datetime.now() - self.bot.start_time, format='%0.0f'))
    
    @commands.command(description='The source code for the bot')
    async def source(self, ctx):
        await ctx.send('https://github.com/RRainmaker/Cyalm')

    @commands.command(aliases=['lc', 'lines'], description='The amount of lines and files that make up the bot')
    async def linecount(self, ctx):
        lines = filecount = 0
        
        for path, _, files in os.walk('./cogs'):
            for name in files:
                if name.endswith('.py'):
                    filecount += 1
                    lines += len([line for line in open(f'{path}/{name}') if not line.strip().startswith(('#', "'", '"')) and len(line.strip()) > 0])

        for path, _, files in os.walk('.'):
            for name in files:
                if name == os.sys.argv[0]:
                    filecount += 1
                    lines += len([line for line in open(f'{path}/{name}') if not line.strip().startswith(('#', "'", '"')) and len(line.strip()) > 0])
        
        await ctx.send(f'{lines} lines across {filecount} files')

    @commands.group(invoke_without_command=True, description='Show the prefix the bot uses on the current server', aliases=['prefixes'])
    async def prefix(self, ctx):
        await ctx.send(embed=discord.Embed(title='Current Prefixes', description='**' + '\n'.join(sorted(await self.bot.get_prefix(ctx.message))) + '**', color=ctx.cyan))

    @prefix.command(description='Change the prefix of the bot for the server')
    @commands.has_guild_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild) # make sure other people arent also trying to change the prefix
    async def add(self, ctx, *prefixes):
        '''Use the command like so: 
        `p!prefix add prefix1 prefix2`
        Make sure to seperate each prefix with space'''
        if not prefixes:
            return await ctx.send('You need to provide prefixes for me to use')

        prefixes = [prefix for prefix in set(prefixes) if prefix != self.bot.mention][::-1]

        if not prefixes:
            # this means all prefixes removed were mentions
            return await ctx.send('You cannot add another mention prefix')

        guild_data = await ctx.fetchrow(f'SELECT * FROM prefix WHERE guild_id = {ctx.guild.id}')
        keep_default_prefix = True

        # the person hasnt done this before, so prompt the user if they want the original prefixes
        # this only prompts once, however
        if not guild_data:
            if not await ctx.prompt('Would you like to keep my initial prefixes? (p! persona! P!)', ctx.author, timeout=30):
                await ctx.send(f'My original prefixes will be overrided\nYou can still manually add them later with {ctx.prefix}prefix add')
                keep_default_prefix = False
            else:
                await ctx.send(f'I will be using both my original prefixes and the new ones\nYou can remove existing ones with {ctx.prefix}prefix remove')

        if not guild_data:                                                                                                                              
            await ctx.execute(f"INSERT INTO prefix (guild_name, guild_id, prefixes, no_default) VALUES('{ctx.guild.name}', {ctx.guild.id}, ARRAY{prefixes}, {keep_default_prefix})")
        else:
            await ctx.execute(f"UPDATE prefix SET guild_name = '{ctx.guild.name}', prefixes = array_cat(ARRAY{guild_data['prefixes']}::text[], ARRAY{prefixes}) WHERE guild_id = {ctx.guild.id}")
        
        await ctx.send('The new server prefixes are: \n' + '\n'.join(prefixes))
    
    @prefix.command(description='Remove a prefix from the list')
    @commands.has_guild_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild) 
    async def remove(self, ctx, *prefixes):
        '''Similarly to prefix add, use the command like so:
           p!prefix remove prefix1 prefix2 etc
           Make sure to seperate prefixes with space'''
        if not prefixes:
            return await ctx.send('You need to provide prefixes for me to remove')

        guild_prefix = await ctx.fetchrow(f'SELECT * FROM prefix WHERE guild_id = {ctx.guild.id}')

        if not guild_prefix:
            return await ctx.send('It seems your server has not set any prefixes yet')

        for prefix in prefixes:
            if prefix not in guild_prefix['prefixes']:
                return await ctx.send(f'{prefix} is not a prefix your server has')
        
        if self.bot.mention in prefixes:
            return await ctx.send('You cannot remove a mention prefix')
        
        new_prefixes = [prefix for prefix in guild_prefix['prefixes'] if prefix not in prefixes and prefix != self.bot.mention]
        
        await ctx.execute(f"UPDATE prefix SET prefixes = ARRAY{new_prefixes}::text[] WHERE guild_id = {ctx.guild.id}")
        
        await ctx.send('Removed these prefixes: \n' + '\n'.join(prefixes))
    
def setup(bot): 
    bot.add_cog(Utility(bot))