import sqlite3
import datetime

DATABASE_FILE = "solved_problems.db"

def get_db_connection():
    """データベース接続を取得し、Rowファクトリを設定する"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """データベースを初期化し、必要なテーブルを作成する"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # ユーザー設定テーブル
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        atcoder_id TEXT,
        reminder_time TEXT,
        reminder_tz TEXT
    )
    """)

    # 解いた問題の記録テーブル
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS solved_problems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        platform TEXT NOT NULL,
        problem_id TEXT NOT NULL,
        url TEXT,
        solved_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """)
    
    # user_idとproblem_idの組み合わせが一意であることを保証する
    cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_problem ON solved_problems (user_id, problem_id)
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

# main.pyで呼び出すために、このスクリプトが直接実行されたときにも初期化する
if __name__ == '__main__':
    initialize_database()