import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
from zoneinfo import ZoneInfo, available_timezones
from database import get_db_connection

class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_reminder_check.start() # Cogのロード時にタスクを開始

    def cog_unload(self):
        self.daily_reminder_check.cancel() # Cogのアンロード時にタスクを停止

    # 1分ごとに実行されるループタスク
    @tasks.loop(minutes=1)
    async def daily_reminder_check(self):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        
        conn = get_db_connection()
        try:
            # リマインダーを設定している全ユーザーを取得
            users_with_reminders = conn.execute("SELECT user_id, reminder_time, reminder_tz FROM users WHERE reminder_time IS NOT NULL AND reminder_tz IS NOT NULL").fetchall()

            for user_row in users_with_reminders:
                user_id = user_row['user_id']
                reminder_time_str = user_row['reminder_time'] # "HH:MM"形式
                tz_str = user_row['reminder_tz']

                try:
                    user_tz = ZoneInfo(tz_str)
                    reminder_hour, reminder_minute = map(int, reminder_time_str.split(':'))
                    
                    # ユーザーのタイムゾーンでの現在時刻
                    now_local = now_utc.astimezone(user_tz)

                    # リマインダー時刻と現在時刻が一致するかチェック
                    if now_local.hour == reminder_hour and now_local.minute == reminder_minute:
                        await self.check_and_send_reminder(user_id)

                except Exception as e:
                    print(f"Error processing reminder for user {user_id}: {e}")
        finally:
            conn.close()

    @daily_reminder_check.before_loop
    async def before_daily_reminder_check(self):
        await self.bot.wait_until_ready() # Botの準備が完了するまで待機
        print("Reminder loop is waiting for the bot to be ready...")

    async def check_and_send_reminder(self, user_id: int):
        conn = get_db_connection()
        try:
            # 過去24時間以内のAC記録が存在するかチェック
            # SELECT EXISTSは存在チェックに最も効率的なクエリ [19, 30]
            res = conn.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM solved_problems 
                    WHERE user_id =? AND solved_at >=?
                )
                """,
                (user_id, datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
            ).fetchone()

            has_solved_today = res == 1

            if not has_solved_today:
                try:
                    user = await self.bot.fetch_user(user_id)
                    await user.send("【リマインダー】\nこんにちは！今日はまだ問題を解いていないようです。少しでもコードに触れてみませんか？💪")
                    print(f"Sent reminder to user {user_id}")
                except discord.Forbidden:
                    print(f"Could not send DM to user {user_id}. They may have DMs disabled.")
                except Exception as e:
                    print(f"Failed to send reminder to {user_id}: {e}")
        finally:
            conn.close()

    #... (Reminderクラス内)
    @app_commands.command(name="set_reminder", description="毎日のリマインダー時刻とタイムゾーンを設定します。")
    @app_commands.describe(time="リマインダー時刻 (HH:MM形式, 例: 21:00)", timezone="あなたのタイムゾーン (例: Asia/Tokyo)")
    async def set_reminder(self, interaction: discord.Interaction, time: str, timezone: str):
        # 時刻形式のバリデーション
        try:
            datetime.datetime.strptime(time, "%H:%M")
        except ValueError:
            await interaction.response.send_message("時刻の形式が正しくありません。`HH:MM`形式で入力してください。", ephemeral=True)
            return

        # タイムゾーンのバリデーション
        if timezone not in available_timezones():
            await interaction.response.send_message("無効なタイムゾーンです。有効なタイムゾーン名を入力してください。", ephemeral=True)
            return

        user_id = interaction.user.id
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            cursor.execute("UPDATE users SET reminder_time =?, reminder_tz =? WHERE user_id =?", (time, timezone, user_id))
            conn.commit()
            await interaction.response.send_message(f"リマインダーを毎日 {time} ({timezone}) に設定しました。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"設定中にエラーが発生しました: {e}", ephemeral=True)
        finally:
            conn.close()

    # タイムゾーン入力のオートコンプリート機能
    @set_reminder.autocomplete('timezone')
    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        all_tzs = available_timezones()
        return [
            app_commands.Choice(name=tz, value=tz)
            for tz in all_tzs if current.lower() in tz.lower()
        ][:25] # 選択肢は最大25個まで

async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))