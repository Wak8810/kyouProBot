import discord
from discord import app_commands
from discord.ext import commands
import datetime
import re
import sqlite3 # IntegrityErrorのために必要
from database import get_db_connection

class ProblemTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="log", description="解いた問題を記録します。")
    @app_commands.describe(
        platform="問題のプラットフォーム",
        identifier="AtCoderの場合は問題のURL、Paizaの場合は問題ID" # 変更点: 説明を具体的に
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="AtCoder", value="atcoder"),
        app_commands.Choice(name="Paiza", value="paiza"),
    ])
    async def log_problem(self, interaction: discord.Interaction, platform: app_commands.Choice[str], identifier: str):
        """スラッシュコマンドで問題を記録する"""
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        
        # URLまたは問題IDをパースして検証
        problem_id = self.parse_identifier(platform.value, identifier)
        if not problem_id:
            # 変更点: プラットフォームに応じた具体的なエラーメッセージを送信
            error_message = ""
            if platform.value == "atcoder":
                error_message = "無効なURLです。AtCoderの問題URL（例: https://atcoder.jp/contests/abc123/tasks/abc123_a）を入力してください。"
            elif platform.value == "paiza":
                error_message = "無効な問題IDです。Paizaの問題IDは難易度(S,A,B,C,D)と3桁の数字で入力してください（例: C012, s123）。"
            await interaction.followup.send(error_message)
            return
        
        # 変更点: AtCoderの場合のみURLを保存し、Paizaの場合はNone（NULL）を保存
        url_to_save = identifier if platform.value == "atcoder" else None

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            
            cursor.execute(
                """
                INSERT INTO solved_problems (user_id, platform, problem_id, url, solved_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, platform.value, problem_id, url_to_save, datetime.datetime.now(datetime.timezone.utc))
            )
            conn.commit()
            await interaction.followup.send(f"記録しました！\nプラットフォーム: {platform.name}\n問題ID: {problem_id}")
        except sqlite3.IntegrityError:
            await interaction.followup.send("この問題は既に記録されています。")
        except Exception as e:
            await interaction.followup.send(f"エラーが発生しました: {e}")
        finally:
            conn.close()

    def parse_identifier(self, platform: str, identifier: str) -> str | None:
        """
        プラットフォームに応じて、URLやIDから正規化された問題IDを抽出・検証する。
        AtCoderはURLのみ、PaizaはIDのみを受け付ける。
        """
        # 変更点: AtCoderはURL形式のみを許可
        if platform == "atcoder":
            # 例: https://atcoder.jp/contests/abc123/tasks/abc123_a
            match = re.search(r'atcoder\.jp/contests/[^/]+/tasks/([^/]+)', identifier)
            if match:
                return match.group(1) # 'abc123_a' を返す
        # 変更点: Paizaは問題ID形式のみを許可
        elif platform == "paiza":
            match = re.match(r'^([sabcd])(\d{3})$', identifier, re.IGNORECASE)
            if match:
                rank = match.group(1).upper()
                number = match.group(2)
                return f"{rank}{number}"
        return None

    @app_commands.command(name="summary", description="あなたの解答記録のサマリーを表示します。")
    async def summary(self, interaction: discord.Interaction):
        await interaction.response.defer()
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
                await interaction.followup.send("まだ解答記録がありません。`/log`コマンドで記録を始めましょう！")
                return

            embed = discord.Embed(
                title=f"{interaction.user.display_name}さんの解答サマリー",
                color=discord.Color.blue()
            )
            
            count_text = "\n".join([f"**{row['platform'].capitalize()}**: {row['count']}問" for row in solve_counts])
            if count_text:
                embed.add_field(name="プラットフォーム別解答数", value=count_text, inline=False)

            # 変更点: URLの有無で表示形式を切り替え
            solve_list = []
            for solve in recent_solves:
                solved_at_dt = datetime.datetime.fromisoformat(solve['solved_at']) 
                timestamp = int(solved_at_dt.timestamp())
                # URLがDBに保存されていれば（AtCoderの場合）、リンク付きで表示
                if solve['url']:
                    solve_list.append(f"• [{solve['problem_id']}]({solve['url']}) - <t:{timestamp}:R>")
                # URLがなければ（Paizaの場合）、プラットフォーム名と問題IDを表示
                else:
                    platform_name = solve['platform'].capitalize()
                    solve_list.append(f"• **{platform_name}**: {solve['problem_id']} - <t:{timestamp}:R>")
            
            if solve_list:
                embed.add_field(name="直近の解答", value="\n".join(solve_list), inline=False)

            embed.set_footer(text=f"最終更新: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            await interaction.followup.send(embed=embed)

        finally:
            conn.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(ProblemTracker(bot))