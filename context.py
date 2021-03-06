from discord.ext import commands, menus
import asyncpg
import config
import random

class Confirmation(menus.Menu):
    def __init__(self, content, recipient, timeout):
        super().__init__(timeout=timeout)
        self._author_id = recipient.id
        self.content = content

    async def send_initial_message(self, ctx, channel):
        return await ctx.send(self.content)

    @menus.button('✅')
    async def confirm(self, payload):
        self.result = True
        self.stop()
    
    @menus.button('❌')
    async def deny(self, payload):
        self.result = False
        self.stop()
    
    async def begin(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

class Context(commands.Context):
    'A commands.Context subclass to store extra functions'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def prompt(self, content, recipient, timeout):
        return await Confirmation(content, recipient, timeout).begin(self)

    @property
    def cyan(self):
        return 0x00eeff

    # SQL functions

    @staticmethod
    async def fetch(query, *args):
        async with asyncpg.create_pool(config.postgres) as pool:
            try:
                return await pool.fetch(query, *args)
            finally:
                await pool.close()
    
    @staticmethod
    async def fetchrow(query, *args):
        async with asyncpg.create_pool(config.postgres) as pool:
            try:
                return await pool.fetchrow(query, *args)
            finally:
                await pool.close()

    @staticmethod
    async def fetchval(query, *args):
        async with asyncpg.create_pool(config.postgres) as pool:
            try:
                return await pool.fetchval(query, *args)
            finally:
                await pool.close()

    @staticmethod
    async def execute(query, *args):
        async with asyncpg.create_pool(config.postgres) as pool:
            try:
                return await pool.execute(query, *args)
            finally:
                await pool.close()