"""
データベース管理モジュール
パフォーマンス最適化: WALモード、コネクションプール、インデックス最適化
"""

import aiosqlite
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

# デフォルトデータベースパス
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "progress_tracker.db"


class Database:
    """非同期SQLiteデータベース管理クラス（パフォーマンス最適化版）"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """データベース接続を確立（WALモード有効化）"""
        # ディレクトリ作成
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(
            str(self.db_path),
            isolation_level=None  # 自動コミット
        )

        # パフォーマンス最適化設定
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        await self._connection.execute("PRAGMA cache_size=10000")
        await self._connection.execute("PRAGMA temp_store=MEMORY")
        await self._connection.execute("PRAGMA mmap_size=268435456")  # 256MB

        # Row factory設定
        self._connection.row_factory = aiosqlite.Row

        logger.info(f"Database connected: {self.db_path} (WAL mode)")

    async def disconnect(self) -> None:
        """データベース接続を切断"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database disconnected")

    @asynccontextmanager
    async def transaction(self):
        """トランザクションコンテキストマネージャー"""
        async with self._lock:
            await self._connection.execute("BEGIN")
            try:
                yield
                await self._connection.execute("COMMIT")
            except Exception:
                await self._connection.execute("ROLLBACK")
                raise

    async def init_tables(self) -> None:
        """テーブル初期化（インデックス最適化）"""
        async with self._lock:
            # destinations マスターテーブル（納品先）
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS destinations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_order INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

            # tts_engines マスターテーブル（音声変換エンジン）
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS tts_engines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_order INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

            # 初期データ挿入（存在しない場合のみ）
            await self._connection.execute("""
                INSERT OR IGNORE INTO destinations (name, display_order) VALUES ('会社', 1)
            """)
            await self._connection.execute("""
                INSERT OR IGNORE INTO destinations (name, display_order) VALUES ('自分', 2)
            """)
            await self._connection.execute("""
                INSERT OR IGNORE INTO tts_engines (name, display_order) VALUES ('Google Cloud TTS', 1)
            """)
            await self._connection.execute("""
                INSERT OR IGNORE INTO tts_engines (name, display_order) VALUES ('Gemini 2.5 Flash TTS', 2)
            """)

            # projects テーブル
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    path TEXT NOT NULL,
                    wbs_format TEXT CHECK(wbs_format IN ('object', 'array', NULL)),
                    total_topics INTEGER DEFAULT 0,
                    completed_topics INTEGER DEFAULT 0,
                    html_count INTEGER DEFAULT 0,
                    txt_count INTEGER DEFAULT 0,
                    mp3_count INTEGER DEFAULT 0,
                    destination_id INTEGER REFERENCES destinations(id),
                    tts_engine_id INTEGER REFERENCES tts_engines(id),
                    last_scanned_at TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)

            # 既存テーブルにカラム追加（マイグレーション対応）
            await self._migrate_projects_table()

            # topics テーブル
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    chapter TEXT,
                    topic_id TEXT,
                    title TEXT,
                    base_name TEXT NOT NULL,
                    subfolder TEXT,
                    has_html INTEGER DEFAULT 0 CHECK(has_html IN (0, 1)),
                    has_txt INTEGER DEFAULT 0 CHECK(has_txt IN (0, 1)),
                    has_mp3 INTEGER DEFAULT 0 CHECK(has_mp3 IN (0, 1)),
                    html_hash TEXT,
                    txt_hash TEXT,
                    mp3_hash TEXT,
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(project_id, base_name, subfolder)
                )
            """)

            # scan_history テーブル
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id TEXT UNIQUE NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    scan_type TEXT NOT NULL CHECK(scan_type IN ('full', 'diff', 'watch')),
                    project_id INTEGER REFERENCES projects(id),
                    projects_scanned INTEGER DEFAULT 0,
                    files_scanned INTEGER DEFAULT 0,
                    changes_detected INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed')),
                    error_message TEXT
                )
            """)

            # インデックス作成（パフォーマンス最適化）
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_topics_project ON topics(project_id)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_topics_base_name ON topics(project_id, base_name)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_topics_chapter ON topics(project_id, chapter)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_scan_history_started ON scan_history(started_at)"
            )

            logger.info("Database tables initialized with optimized indexes")

    async def _migrate_projects_table(self) -> None:
        """既存のprojectsテーブルにカラムを追加（マイグレーション）"""
        # 既存カラムを取得
        cursor = await self._connection.execute("PRAGMA table_info(projects)")
        columns = [row[1] for row in await cursor.fetchall()]

        # destination_id カラムが存在しない場合は追加
        if 'destination_id' not in columns:
            await self._connection.execute(
                "ALTER TABLE projects ADD COLUMN destination_id INTEGER REFERENCES destinations(id)"
            )
            logger.info("Added destination_id column to projects table")

        # tts_engine_id カラムが存在しない場合は追加
        if 'tts_engine_id' not in columns:
            await self._connection.execute(
                "ALTER TABLE projects ADD COLUMN tts_engine_id INTEGER REFERENCES tts_engines(id)"
            )
            logger.info("Added tts_engine_id column to projects table")

        # topicsテーブルのマイグレーション（UNIQUE制約の変更を含む）
        await self._migrate_topics_table()

    async def _migrate_topics_table(self) -> None:
        """topicsテーブルのマイグレーション（UNIQUE制約変更対応）"""
        # テーブルが存在するか確認
        cursor = await self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='topics'"
        )
        if not await cursor.fetchone():
            return  # テーブルがない場合はスキップ

        # 既存カラムを取得
        cursor = await self._connection.execute("PRAGMA table_info(topics)")
        topic_columns = [row[1] for row in await cursor.fetchall()]

        # subfolderカラムがない場合、テーブルを再作成する必要がある
        if 'subfolder' not in topic_columns:
            logger.info("Migrating topics table: adding subfolder column and updating UNIQUE constraint")

            # 新しいテーブル構造でtopics_newを作成
            await self._connection.execute("""
                CREATE TABLE topics_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    chapter TEXT,
                    topic_id TEXT,
                    title TEXT,
                    base_name TEXT NOT NULL,
                    subfolder TEXT DEFAULT '',
                    has_html INTEGER DEFAULT 0 CHECK(has_html IN (0, 1)),
                    has_txt INTEGER DEFAULT 0 CHECK(has_txt IN (0, 1)),
                    has_mp3 INTEGER DEFAULT 0 CHECK(has_mp3 IN (0, 1)),
                    html_hash TEXT,
                    txt_hash TEXT,
                    mp3_hash TEXT,
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(project_id, base_name, subfolder)
                )
            """)

            # 既存データをコピー
            await self._connection.execute("""
                INSERT INTO topics_new (
                    id, project_id, chapter, topic_id, title, base_name, subfolder,
                    has_html, has_txt, has_mp3, html_hash, txt_hash, mp3_hash, updated_at
                )
                SELECT
                    id, project_id, chapter, topic_id, title, base_name, '',
                    has_html, has_txt, has_mp3, html_hash, txt_hash, mp3_hash, updated_at
                FROM topics
            """)

            # 古いテーブルを削除
            await self._connection.execute("DROP TABLE topics")

            # 新しいテーブルをリネーム
            await self._connection.execute("ALTER TABLE topics_new RENAME TO topics")

            logger.info("Topics table migration completed")

    # ========== 納品先マスター操作 ==========

    async def get_all_destinations(self) -> List[Dict[str, Any]]:
        """全納品先取得"""
        cursor = await self._connection.execute(
            "SELECT * FROM destinations ORDER BY display_order, id"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_destination(self, destination_id: int) -> Optional[Dict[str, Any]]:
        """納品先単体取得"""
        cursor = await self._connection.execute(
            "SELECT * FROM destinations WHERE id = ?",
            (destination_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def create_destination(self, name: str, display_order: int = 0) -> int:
        """納品先作成"""
        async with self._lock:
            cursor = await self._connection.execute("""
                INSERT INTO destinations (name, display_order)
                VALUES (?, ?)
                RETURNING id
            """, (name, display_order))
            row = await cursor.fetchone()
            return row[0]

    async def update_destination(self, destination_id: int, name: str, display_order: Optional[int] = None) -> bool:
        """納品先更新"""
        async with self._lock:
            if display_order is not None:
                await self._connection.execute("""
                    UPDATE destinations SET name = ?, display_order = ? WHERE id = ?
                """, (name, display_order, destination_id))
            else:
                await self._connection.execute("""
                    UPDATE destinations SET name = ? WHERE id = ?
                """, (name, destination_id))
            return True

    async def delete_destination(self, destination_id: int) -> bool:
        """納品先削除"""
        async with self._lock:
            # 関連プロジェクトのdestination_idをNULLに設定
            await self._connection.execute(
                "UPDATE projects SET destination_id = NULL WHERE destination_id = ?",
                (destination_id,)
            )
            await self._connection.execute(
                "DELETE FROM destinations WHERE id = ?",
                (destination_id,)
            )
            return True

    # ========== 音声変換エンジンマスター操作 ==========

    async def get_all_tts_engines(self) -> List[Dict[str, Any]]:
        """全音声変換エンジン取得"""
        cursor = await self._connection.execute(
            "SELECT * FROM tts_engines ORDER BY display_order, id"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_tts_engine(self, tts_engine_id: int) -> Optional[Dict[str, Any]]:
        """音声変換エンジン単体取得"""
        cursor = await self._connection.execute(
            "SELECT * FROM tts_engines WHERE id = ?",
            (tts_engine_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def create_tts_engine(self, name: str, display_order: int = 0) -> int:
        """音声変換エンジン作成"""
        async with self._lock:
            cursor = await self._connection.execute("""
                INSERT INTO tts_engines (name, display_order)
                VALUES (?, ?)
                RETURNING id
            """, (name, display_order))
            row = await cursor.fetchone()
            return row[0]

    async def update_tts_engine(self, tts_engine_id: int, name: str, display_order: Optional[int] = None) -> bool:
        """音声変換エンジン更新"""
        async with self._lock:
            if display_order is not None:
                await self._connection.execute("""
                    UPDATE tts_engines SET name = ?, display_order = ? WHERE id = ?
                """, (name, display_order, tts_engine_id))
            else:
                await self._connection.execute("""
                    UPDATE tts_engines SET name = ? WHERE id = ?
                """, (name, tts_engine_id))
            return True

    async def delete_tts_engine(self, tts_engine_id: int) -> bool:
        """音声変換エンジン削除"""
        async with self._lock:
            # 関連プロジェクトのtts_engine_idをNULLに設定
            await self._connection.execute(
                "UPDATE projects SET tts_engine_id = NULL WHERE tts_engine_id = ?",
                (tts_engine_id,)
            )
            await self._connection.execute(
                "DELETE FROM tts_engines WHERE id = ?",
                (tts_engine_id,)
            )
            return True

    # ========== プロジェクト操作 ==========

    async def get_all_projects(self) -> List[Dict[str, Any]]:
        """全プロジェクト取得（納品先・音声変換エンジン名含む）"""
        cursor = await self._connection.execute("""
            SELECT
                p.*,
                d.name as destination_name,
                t.name as tts_engine_name
            FROM projects p
            LEFT JOIN destinations d ON p.destination_id = d.id
            LEFT JOIN tts_engines t ON p.tts_engine_id = t.id
            ORDER BY p.name
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """プロジェクト単体取得（納品先・音声変換エンジン名含む）"""
        cursor = await self._connection.execute("""
            SELECT
                p.*,
                d.name as destination_name,
                t.name as tts_engine_name
            FROM projects p
            LEFT JOIN destinations d ON p.destination_id = d.id
            LEFT JOIN tts_engines t ON p.tts_engine_id = t.id
            WHERE p.id = ?
        """, (project_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """プロジェクト名で取得"""
        cursor = await self._connection.execute(
            "SELECT * FROM projects WHERE name = ?",
            (name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_project(self, name: str, path: str, wbs_format: Optional[str] = None) -> int:
        """プロジェクトをUPSERT"""
        async with self._lock:
            cursor = await self._connection.execute("""
                INSERT INTO projects (name, path, wbs_format)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    path = excluded.path,
                    wbs_format = COALESCE(excluded.wbs_format, wbs_format),
                    updated_at = datetime('now')
                RETURNING id
            """, (name, path, wbs_format))
            row = await cursor.fetchone()
            return row[0]

    async def update_project_stats(
        self,
        project_id: int,
        total_topics: int,
        completed_topics: int,
        html_count: int,
        txt_count: int,
        mp3_count: int
    ) -> None:
        """プロジェクト統計を更新"""
        async with self._lock:
            await self._connection.execute("""
                UPDATE projects SET
                    total_topics = ?,
                    completed_topics = ?,
                    html_count = ?,
                    txt_count = ?,
                    mp3_count = ?,
                    last_scanned_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ?
            """, (total_topics, completed_topics, html_count, txt_count, mp3_count, project_id))

    async def update_project_settings(
        self,
        project_id: int,
        destination_id: Optional[int] = None,
        tts_engine_id: Optional[int] = None
    ) -> bool:
        """プロジェクトの設定（納品先・音声変換エンジン）を更新"""
        async with self._lock:
            await self._connection.execute("""
                UPDATE projects SET
                    destination_id = ?,
                    tts_engine_id = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """, (destination_id, tts_engine_id, project_id))
            return True

    # ========== トピック操作 ==========

    async def get_topics_by_project(self, project_id: int) -> List[Dict[str, Any]]:
        """プロジェクトのトピック一覧取得"""
        cursor = await self._connection.execute("""
            SELECT * FROM topics
            WHERE project_id = ?
            ORDER BY base_name
        """, (project_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def upsert_topic(
        self,
        project_id: int,
        base_name: str,
        topic_id: Optional[str] = None,
        chapter: Optional[str] = None,
        title: Optional[str] = None,
        subfolder: Optional[str] = None,
        has_html: bool = False,
        has_txt: bool = False,
        has_mp3: bool = False,
        html_hash: Optional[str] = None,
        txt_hash: Optional[str] = None,
        mp3_hash: Optional[str] = None
    ) -> int:
        """トピックをUPSERT"""
        async with self._lock:
            cursor = await self._connection.execute("""
                INSERT INTO topics (
                    project_id, base_name, topic_id, chapter, title, subfolder,
                    has_html, has_txt, has_mp3, html_hash, txt_hash, mp3_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, base_name, subfolder) DO UPDATE SET
                    topic_id = COALESCE(excluded.topic_id, topic_id),
                    chapter = COALESCE(excluded.chapter, chapter),
                    title = COALESCE(excluded.title, title),
                    has_html = excluded.has_html,
                    has_txt = excluded.has_txt,
                    has_mp3 = excluded.has_mp3,
                    html_hash = excluded.html_hash,
                    txt_hash = excluded.txt_hash,
                    mp3_hash = excluded.mp3_hash,
                    updated_at = datetime('now')
                RETURNING id
            """, (
                project_id, base_name, topic_id, chapter, title, subfolder or "",
                int(has_html), int(has_txt), int(has_mp3),
                html_hash, txt_hash, mp3_hash
            ))
            row = await cursor.fetchone()
            return row[0]

    async def get_topic_by_base_name(
        self, project_id: int, base_name: str
    ) -> Optional[Dict[str, Any]]:
        """トピックをbase_nameで取得"""
        cursor = await self._connection.execute("""
            SELECT * FROM topics
            WHERE project_id = ? AND base_name = ?
        """, (project_id, base_name))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def delete_topics_by_project(self, project_id: int) -> int:
        """プロジェクトのトピックを全削除"""
        async with self._lock:
            cursor = await self._connection.execute(
                "DELETE FROM topics WHERE project_id = ?",
                (project_id,)
            )
            return cursor.rowcount

    # ========== スキャン履歴操作 ==========

    async def create_scan_history(
        self,
        scan_id: str,
        scan_type: str,
        project_id: Optional[int] = None
    ) -> int:
        """スキャン履歴作成"""
        async with self._lock:
            cursor = await self._connection.execute("""
                INSERT INTO scan_history (scan_id, started_at, scan_type, project_id)
                VALUES (?, datetime('now'), ?, ?)
                RETURNING id
            """, (scan_id, scan_type, project_id))
            row = await cursor.fetchone()
            return row[0]

    async def update_scan_history(
        self,
        scan_id: str,
        status: str,
        projects_scanned: int = 0,
        files_scanned: int = 0,
        changes_detected: int = 0,
        error_message: Optional[str] = None
    ) -> None:
        """スキャン履歴更新"""
        async with self._lock:
            await self._connection.execute("""
                UPDATE scan_history SET
                    completed_at = datetime('now'),
                    status = ?,
                    projects_scanned = ?,
                    files_scanned = ?,
                    changes_detected = ?,
                    error_message = ?
                WHERE scan_id = ?
            """, (status, projects_scanned, files_scanned, changes_detected, error_message, scan_id))

    # ========== 統計操作 ==========

    async def get_stats(self) -> Dict[str, Any]:
        """全体統計取得"""
        cursor = await self._connection.execute("""
            SELECT
                COUNT(*) as total_projects,
                COALESCE(SUM(total_topics), 0) as total_topics,
                COALESCE(SUM(completed_topics), 0) as completed_topics,
                COALESCE(SUM(html_count), 0) as html_total,
                COALESCE(SUM(txt_count), 0) as txt_total,
                COALESCE(SUM(mp3_count), 0) as mp3_total
            FROM projects
        """)
        row = await cursor.fetchone()
        data = dict(row)

        # 進捗率計算
        total = data["total_topics"]
        if total > 0:
            weighted = (
                (data["html_total"] * 0.4) +
                (data["txt_total"] * 0.3) +
                (data["mp3_total"] * 0.3)
            ) / total * 100
            data["overall_progress"] = round(weighted, 1)
        else:
            data["overall_progress"] = 0.0

        return data


# シングルトンインスタンス
_database: Optional[Database] = None


async def get_database() -> Database:
    """データベースインスタンスを取得"""
    global _database
    if _database is None:
        _database = Database()
        await _database.connect()
        await _database.init_tables()
    return _database


async def close_database() -> None:
    """データベース接続をクローズ"""
    global _database
    if _database:
        await _database.disconnect()
        _database = None
