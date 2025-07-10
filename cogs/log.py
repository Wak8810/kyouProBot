import discord
from discord import app_commands
from discord.ext import commands
import datetime
import re
import sqlite3
from database import get_db_connection

class Log(commands.Cog):
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

async def setup(bot: commands.Bot):
    await bot.add_cog(Log(bot))
