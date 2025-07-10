# main.py

import os
import asyncio
import discord
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
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename != "__init__.py":
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'Loaded extension: {filename}')
                except Exception as e:
                    print(f'Failed to load extension {filename}: {e}')
        
        try:
            guild = discord.Object(id=GUILD_ID)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} command(s) to guild {GUILD_ID}")
            print("-" * 30)
        except Exception as e:
            print(f"Failed to sync commands to guild: {e}")

    async def on_ready(self):
        print(f'{self.user} としてログインしました。')
        print('Bot is ready.')

async def main():
    bot = MyBot()

    @bot.tree.command(name="ping_main", description="main.pyから直接登録した生存確認コマンド", guild=discord.Object(id=GUILD_ID))
    async def ping_main(interaction: discord.Interaction):
        await interaction.response.send_message("Pong from main.py!", ephemeral=True)

    await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())