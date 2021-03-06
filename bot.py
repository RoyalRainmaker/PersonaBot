import discord
from discord.ext import commands
import config
import os
import datetime
from context import Context

class Cyalm(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=self.prefix, case_insensitive=True, intents=discord.Intents.all())
        self.loop.create_task(self.create_tables())
        self.cooldown = commands.CooldownMapping.from_cooldown(7, 10, commands.BucketType.user)
        self.spam_strikes = {}

    async def on_ready(self):
        self.start_time = datetime.datetime.now()
        print(f'{self.user} is online and ready')
        await self.change_presence(activity=discord.Activity(name=f'{len(self.guilds)} servers for c.', type=discord.ActivityType.watching))

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)
        
        if ctx.valid:
            if await self.is_owner(ctx.author):
                return await self.invoke(ctx)

            blacklist = []
            for member in await ctx.fetch('SELECT * FROM blacklist;'):
                blacklist.append(member['id'])
        
            if ctx.author.id in blacklist or ctx.author.bot:
                return
        
            if self.cooldown.update_rate_limit(message, message.created_at.timestamp()):
                authorid = ctx.author.id
                
                if authorid not in self.spam_strikes.keys():
                    self.spam_strikes[authorid] = 1
                else:
                    self.spam_strikes[authorid] += 1
                    if self.spam_strikes[authorid] >= 5:
                        del self.spam_strikes[authorid]
                        await ctx.execute(f"INSERT INTO blacklist (name, id, reason) VALUES('{ctx.author}', {authorid}, 'Excessive command spamming');")
                        return await ctx.send(f'{ctx.author.mention}, you are now blacklisted for excessive command spamming')
            
            await self.invoke(ctx)

    async def prefix(self, bot, message):
        initial_prefixes = ['c.', 'c!', 'C.', 'C!']
        
        if message.guild:
            data = await Context.fetchrow(f'SELECT * FROM prefix WHERE guild_id = {message.guild.id}')
            if not data:
                pass
            else:
                if not data['no_default']:
                    initial_prefixes = data['prefixes'][::-1]
                elif data['prefixes']:
                    initial_prefixes.extend(data['prefixes'][::-1])
        
        initial_prefixes.append(self.mention + ' ')
        
        return initial_prefixes

    async def on_member_join(self, member):
        guild_data = await Context.fetchrow(f'SELECT * FROM muted WHERE guild_id = {member.guild.id}')
        
        if guild_data and guild_data['muted_members']:
            mute_role = member.guild.get_role(guild_data['mute_role'])
            
            if mute_role and discord.utils.find(lambda m: m[1] == str(member.id), guild_data['muted_members']):
                await member.remove_roles(*member.roles[1:], reason='Previously muted')
                await member.add_roles(mute_role, reason='Previously muted')

    async def on_guild_join(self, guild):
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return await channel.send(f'Hello, I am Cyalm, and I was made by {self.get_user(self.owner_id)}\nThank you for having me, I hope we can build a great friendship\nMy current prefix is c.')
                
    async def on_user_update(self, before, after):
        # this is to update the blacklist in case they change their name/discrim
        if await Context.fetch(f'SELECT * FROM blacklist WHERE id = {before.id}'):
            await Context.execute(f"UPDATE blacklist SET name = '{after}' WHERE id = {after.id}")

    async def on_guild_update(self, before, after):
        # update the tables with the new guild name
        if await Context.fetch(f'SELECT * FROM muted WHERE guild_id = {before.id}'):
            await Context.execute(f"UPDATE muted SET guild_name = '{after}' WHERE guild_id = {after.id}")
            
        if await Context.fetch(f'SELECT * FROM prefix WHERE guild_id = {before.id}'):
            await Context.execute(f"UPDATE prefix SET guild_name = '{after}' WHERE guild_id = {after.id}")

    async def on_guild_role_delete(self, role):
        guild_data = await Context.fetchrow(f'SELECT * FROM muted WHERE guild_id = {role.guild.id}')
        if guild_data and guild_data['mute_role'] == role.id:
            await Context.execute(f'UPDATE muted SET mute_role = 0 WHERE guild_id = {role.guild.id}')

            if role.guild.system_channel:
                # let them know the mute role is gone and use @name as there is no way to check for a server prefix
                await role.guild.system_channel.send(f'The custom mute role has been deleted, please update this with @{self.user.name} muterole set <new role>')

    async def create_tables(self):
        # create postgres tables before anything
        await Context.execute('CREATE TABLE IF NOT EXISTS compendium(name text, id bigint, personas text [], level bigint, money bigint)')
        await Context.execute('CREATE TABLE IF NOT EXISTS blacklist(name text, id bigint, reason text)')
        await Context.execute('CREATE TABLE IF NOT EXISTS prefix(guild_name text, guild_id bigint, prefixes text [], no_default bool)')
        await Context.execute('CREATE TABLE IF NOT EXISTS muted(guild_name text, guild_id bigint, mute_role bigint, muted_members text [][])')
        await Context.execute('CREATE TABLE IF NOT EXISTS quotes(guild_name text, guild_id bigint, quoted_members text [][])')

    def run(self):
        for cog in os.listdir('./cogs'):
            if cog.endswith('.py'):
                self.load_extension(f'cogs.{cog[:-3]}')
        self.load_extension('jishaku')
        super().run(config.bot_token)

    @property
    def config(self):
        return __import__('config')
    
    # the default mention returns <@!id> only if the member has a nickname
    # otherwise, it returns <@id>
    # so i make my own here which always returns <@!id>
    @property
    def mention(self):
        return f'<@!{self.user.id}>'

Cyalm().run()