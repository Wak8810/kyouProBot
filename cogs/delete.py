import discord
from discord import app_commands, ui
from discord.ext import commands
import datetime
from database import get_db_connection

class ProblemSelect(discord.ui.Select):
    """削除する問題を選択するためのドロップダウンメニュー"""
    def __init__(self, user_id: int, platform_value: str, problems: list):
        self.user_id = user_id
        self.platform_value = platform_value
        
        options = []
        jst = datetime.timezone(datetime.timedelta(hours=9))
        for problem in problems:
            solved_at_dt = datetime.datetime.fromisoformat(problem['solved_at'])
            solved_at_jst_str = solved_at_dt.astimezone(jst).strftime("%Y-%m-%d %H:%M")
            
            options.append(discord.SelectOption(
                label=problem['problem_id'],
                value=problem['problem_id'],
                description=f"記録日: {solved_at_jst_str}"
            ))

        super().__init__(
            placeholder="削除する問題を選択",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        problems_to_delete = self.values
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            for problem_id in problems_to_delete:
                cursor.execute(
                    "DELETE FROM solved_problems WHERE user_id = ? AND platform = ? AND problem_id = ?",
                    (self.user_id, self.platform_value, problem_id)
                )
            conn.commit()
            
            deleted_list_str = "\n".join(f"• {pid}" for pid in problems_to_delete)
            await interaction.followup.send(f"ほら、削除しておいたよ。:\n{deleted_list_str}", ephemeral=True)

            self.view.stop()
            for item in self.view.children:
                item.disabled = True
            await interaction.edit_original_response(view=self.view)
        except Exception as e:
            await interaction.followup.send(f"何かおかしいね。こんなエラーが出たようだ: {e}", ephemeral=True)
        finally:
            conn.close()

class DeleteView(discord.ui.View):
    """ProblemSelectを含むView"""
    def __init__(self, user_id: int, platform_value: str, problems: list):
        super().__init__(timeout=180.0)
        self.add_item(ProblemSelect(user_id, platform_value, problems))

class Delete(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="delete", description="記録した問題を削除します。")
    @app_commands.choices(platform=[
        app_commands.Choice(name="AtCoder", value="atcoder"),
        app_commands.Choice(name="Paiza", value="paiza"),
    ])
    async def delete(self, interaction: discord.Interaction, platform: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        conn = get_db_connection()
        problems = conn.execute(
            "SELECT problem_id, solved_at FROM solved_problems WHERE user_id = ? AND platform = ? ORDER BY solved_at DESC LIMIT 25",
            (user_id, platform.value)
        ).fetchall()
        conn.close()

        if not problems:
            await interaction.followup.send("ん？記録がないじゃないか。実験に記録はつきものだよ。", ephemeral=True)
            return

        view = DeleteView(user_id, platform.value, problems)
        await interaction.followup.send(
            f"{interaction.user.display_name}くん、**{platform.name}**の削除したい問題を選択したまえ（直近25件まで表示）。",
            view=view,
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Delete(bot))