import discord
from discord import app_commands
from discord.ext import commands
import datetime
from database import get_db_connection

class Summary(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="summary", description="あなたの解答記録のサマリーを表示します。")
    async def summary(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        
        conn = get_db_connection()
        try:
            recent_solves = conn.execute(
                "SELECT platform, problem_id, url, solved_at FROM solved_problems WHERE user_id = ? ORDER BY solved_at DESC LIMIT 10",
                (user_id,)
            ).fetchall()

            solve_counts = conn.execute(
                "SELECT platform, COUNT(*) as count FROM solved_problems WHERE user_id = ? GROUP BY platform",
                (user_id,)
            ).fetchall()

            if not recent_solves:
                await interaction.followup.send("ん？記録がないじゃないか。実験に記録はつきものだよ。", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"君({interaction.user.display_name})の解いた問題だよ",
                color=discord.Color.blue()
            )
            
            count_text = "\n".join([f"**{row['platform'].capitalize()}**: {row['count']}問" for row in solve_counts])
            if count_text:
                embed.add_field(name="プラットフォーム別解答数", value=count_text, inline=False)

            solve_list = []
            for solve in recent_solves:
                solved_at_dt = datetime.datetime.fromisoformat(solve['solved_at']) 
                timestamp = int(solved_at_dt.timestamp())
                if solve['url']:
                    solve_list.append(f"• [{solve['problem_id']}]({solve['url']}) - <t:{timestamp}:R>")
                else:
                    platform_name = solve['platform'].capitalize()
                    solve_list.append(f"• **{platform_name}**: {solve['problem_id']} - <t:{timestamp}:R>")
            
            if solve_list:
                embed.add_field(name="こっちは最新10件だ", value="\n".join(solve_list), inline=False)

            embed.set_footer(text=f"最終更新: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await interaction.followup.send(embed=embed)
        finally:
            conn.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Summary(bot))
