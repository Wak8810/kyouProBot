import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# ボットの起動時の設定
client = discord.Client(intents=discord.Intents.all())

# ボットの起動時の処理
@client.event
async def on_ready():
    print('ログインしました')

# メッセージ受信時の処理
@client.event
async def on_message(message):
    # メッセージ送信者がボットの場合は無視する
    if message.author.bot:
        return

    # メッセージの内容をオウム返しする
    received_message = message.content # 受信したメッセージ
    print(received_message) # 受信したメッセージを出力
    await message.channel.send(received_message) # 受信したメッセージを送信
    return

client.run(DISCORD_TOKEN)
