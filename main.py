import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.all() # 開発中は全て有効にすると便利
        )

    async def setup_hook(self):
        # cogsディレクトリ内のすべての.pyファイルを拡張機能としてロード
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename != "__init__.py":
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'Loaded extension: {filename}')
                except Exception as e:
                    print(f'Failed to load extension {filename}: {e}')

        # スラッシュコマンドを同期
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def on_ready(self):
        print(f'{self.user} としてログインしました。')
        print('Bot is ready.')

async def main():
    bot = MyBot()
    await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())