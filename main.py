# main.py

import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# あなたのサーバーID
GUILD_ID = 1392293394071425054

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.all()
        )

    async def setup_hook(self):
        # cogsのロード処理
        print("-" * 30)
        excluded_files = ["__init__.py", "problem_tracker.py"]
        loaded_extensions = []
        failed_extensions = []
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename not in excluded_files:
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    loaded_extensions.append(filename)
                except Exception as e:
                    failed_extensions.append((filename, e))

        for filename in loaded_extensions:
            print(f'Loaded extension: {filename}')

        if failed_extensions:
            print("-" * 30)
            print("Failed to load the following extensions:")
            for filename, error in failed_extensions:
                print(f'- {filename}: {error}')
        
        # setup_hookではcogsのロードのみ行う
        pass

    async def on_ready(self):
        print(f'{self.user} としてログインしました。')
        print('Bot is ready.')

async def main():
    bot = MyBot()

    @bot.command()
    @commands.is_owner()
    async def sync(ctx: commands.Context):
        """オーナー用の手動コマンド同期"""
        guild = discord.Object(id=GUILD_ID)
        try:
            # コマンドを同期
            synced = await bot.tree.sync(guild=guild)
            
            await ctx.send(f"Synced {len(synced)} commands to the guild.")
            print(f"Synced {len(synced)} commands to the guild.")
            for cmd in synced:
                print(f"- {cmd.name}")
        except Exception as e:
            await ctx.send(f"Failed to sync commands: {e}")
            print(f"Failed to sync commands: {e}")

    await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())