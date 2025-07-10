import discord
from discord import app_commands
from discord.ext import commands

class LogPast(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="logpast", description="過去に解いた問題を一括登録します")
    async def logpast(self, interaction: discord.Interaction):
        await interaction.response.send_message("logpastコマンドが実行されました", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(LogPast(bot))
