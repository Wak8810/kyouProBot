import discord
from discord import app_commands
from discord.ext import commands
import datetime
import re
import sqlite3 # IntegrityErrorのために必要
from database import get_db_connection


class ProblemSelect(discord.ui.Select):
    """削除する問題を選択するためのドロップダウンメニュー"""
    def __init__(self, user_id: int, platform_value: str, problems: list):
        self.user_id = user_id
        self.platform_value = platform_value
        
        options = []
        jst = datetime.timezone(datetime.timedelta(hours=9))
        for problem in problems:
            # DBから取得した日時文字列をdatetimeオブジェクトに変換
            solved_at_dt = datetime.datetime.fromisoformat(problem['solved_at'])
            # 日本時間 (JST) に変換して分かりやすく表示
            solved_at_jst_str = solved_at_dt.astimezone(jst).strftime("%Y-%m-%d %H:%M")
            
            options.append(discord.SelectOption(
                label=problem['problem_id'],
                value=problem['problem_id'], # 削除時にこの値を使用
                description=f"記録日: {solved_at_jst_str}"
            ))

        super().__init__(
            placeholder="削除したい問題を選択してください...",
            min_values=1,
            max_values=len(options), # 複数選択を可能にする
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # 選択された問題のIDリスト
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
            await interaction.response.send_message(f"以下の問題を削除しました:\n{deleted_list_str}", ephemeral=True)

            # 選択後はドロップダウンを無効化する
            self.disabled = True
            await interaction.message.edit(view=self.view)

        except Exception as e:
            await interaction.response.send_message(f"エラーが発生しました: {e}", ephemeral=True)
        finally:
            conn.close()


class DeleteView(discord.ui.View):
    """ProblemSelectを含むView"""
    def __init__(self, user_id: int, platform_value: str, problems: list):
        # タイムアウトを180秒に設定
        super().__init__(timeout=180.0)
        self.add_item(ProblemSelect(user_id, platform_value, problems))

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

    @app_commands.command(name="delete", description="記録した問題を削除します。")
    @app_commands.describe(platform="削除対象のプラットフォーム")
    @app_commands.choices(platform=[
        app_commands.Choice(name="AtCoder", value="atcoder"),
        app_commands.Choice(name="Paiza", value="paiza"),
    ])
    async def delete(self, interaction: discord.Interaction, platform: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        conn = get_db_connection()
        # Discordのセレクトメニューの選択肢は25個までのため、最新25件に絞る
        problems = conn.execute(
            "SELECT problem_id, solved_at FROM solved_problems WHERE user_id = ? AND platform = ? ORDER BY solved_at DESC LIMIT 25",
            (user_id, platform.value)
        ).fetchall()
        conn.close()

        if not problems:
            await interaction.followup.send(f"{platform.name}の解答記録は見つかりませんでした。", ephemeral=True)
            return

        # 選択メニューを持つViewを作成して送信
        view = DeleteView(user_id, platform.value, problems)
        await interaction.followup.send(
            f"**{platform.name}**の記録から削除したい問題を選択してください（直近25件まで表示）。",
            view=view,
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(ProblemTracker(bot))