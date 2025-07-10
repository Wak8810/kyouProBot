import discord
from discord import app_commands, ui
from discord.ext import commands
import datetime
import re
import sqlite3
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

class ProblemTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def parse_identifier(self, platform: str, identifier: str) -> str | None:
        if platform == "atcoder":
            match = re.search(r'atcoder\.jp/contests/[^/]+/tasks/([^/]+)', identifier)
            if match:
                return match.group(1)
        elif platform == "paiza":
            match = re.match(r'^([sabcd])(\d{3})$', identifier, re.IGNORECASE)
            if match:
                rank = match.group(1).upper()
                number = match.group(2)
                return f"{rank}{number}"
        return None

    @app_commands.command(name="log", description="解いた問題を記録します。")
    @app_commands.describe(
        platform="問題のプラットフォーム",
        identifier="AtCoderの場合は問題のURL、Paizaの場合は問題ID"
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="AtCoder", value="atcoder"),
        app_commands.Choice(name="Paiza", value="paiza"),
    ])
    async def log_problem(self, interaction: discord.Interaction, platform: app_commands.Choice[str], identifier: str):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        problem_id = self.parse_identifier(platform.value, identifier)
        if not problem_id:
            error_message = ""
            if platform.value == "atcoder":
                error_message = "ん？なんだいそれ。AtCoderなら問題URL（例: https://atcoder.jp/contests/abc123/tasks/abc123_a）を入れるべきだ。"
            elif platform.value == "paiza":
                error_message = "ん？なんだいそれ。Paizaなら、難易度(S,A,B,C,D)と3桁の数字を入力してくれ（例: C012, s123）。"
            await interaction.followup.send(error_message, ephemeral=True)
            return
        
        url_to_save = identifier if platform.value == "atcoder" else None
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            cursor.execute(
                "INSERT INTO solved_problems (user_id, platform, problem_id, url, solved_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, platform.value, problem_id, url_to_save, datetime.datetime.now(datetime.timezone.utc))
            )
            conn.commit()
            await interaction.followup.send(f"記録できたよ。\nプラットフォーム: {platform.name}\n問題ID: {problem_id}", ephemeral=True)
        except sqlite3.IntegrityError:
            await interaction.followup.send("うん？もう登録したことがあるみたいだが...", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"何かおかしいね。こんなエラーが出たようだ: {e}", ephemeral=True)
        finally:
            conn.close()

    @app_commands.command(name="log_bulk", description="（引数なしテストバージョン）")
    async def log_bulk(self, interaction: discord.Interaction):
        await interaction.response.send_message("引数なしのlog_bulkコマンドが表示されました！", ephemeral=True)

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

    @app_commands.command(name="delete", description="記録した問題を削除します。")
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
    await bot.add_cog(ProblemTracker(bot))