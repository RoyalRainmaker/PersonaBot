import discord
from discord.ext import commands


class Moderation(commands.Cog):
    'Commands made by mods, for mods'
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_check(self, ctx):
        return ctx.channel.permissions_for(ctx.author).manage_guild
    
    @commands.group(invoke_without_command=True, description='The server mute role')
    async def muterole(self, ctx):
        role = await ctx.fetch('SELECT * FROM mod')
        
        if not role:
            return await ctx.send('Your server has not set a mute role, so I will to default to the first role named Muted')
        
        exists = ctx.guild.get_role(role[0]['mute_role'])
        
        if not exists:
            return await ctx.send(f'The mute role has not been found, please update this with {ctx.prefix}muterole set <role>')
        
        await ctx.send(f'The server mute role is: {exists}')

    @muterole.command(name='set', description='Set a custom mute role')
    async def muterole_set(self, ctx, *, role: discord.Role):
        exists = await ctx.fetch('SELECT * FROM mod')
        
        if exists:
            await ctx.execute(f"UPDATE mod SET guild_name = '{ctx.guild.name}', mute_role = {role.id} WHERE guild_id = {ctx.guild.id}")
            return await ctx.send(f'Changed the server mute role to {role}')
        
        await ctx.execute(f"INSERT INTO mod(guild_name, guild_id, mute_role) VALUES('{ctx.guild.name}', {ctx.guild.id}, {role.id})")
        await ctx.send(f'The new server mute role is now {role}')

    @commands.command(aliases=['silence'], description='Strip someone of all their roles and mute them')
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx, *, member: discord.Member):
        "The target's highest role must be lower than the bot's highest role"       
        if ctx.me.roles[-1] < member.roles[-1]:
            return await ctx.send(f'The {member.roles[-1]} role is higher than my highest role, so I cannot remove their roles')
        
        mute_role = await ctx.fetch('SELECT * FROM mod')
        
        if mute_role:
            mute_role = ctx.guild.get_role(mute_role[0]['mute_role'])
            
            if not mute_role:
                return await ctx.send('Your server has most likely deleted the custom mute role, so I cannot continue')
        
        else:
            mute_role = discord.utils.get(ctx.guild.roles, name='Muted')
            if not mute_role:
                return await ctx.send('Your server has not set a mute role yet, nor has a role named Muted')
        
        for role in member.roles[1:]:
            await member.remove_roles(role, reason='Stripped roles for muted')
        
        await member.add_roles(mute_role, reason=f'Muted by {ctx.author}')
        await ctx.send(f'Successfully muted {member.mention}')

def setup(bot):
    bot.add_cog(Moderation(bot))