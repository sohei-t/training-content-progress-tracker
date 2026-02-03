"""
データベーステスト
テスト対象: backend/database.py
"""

import pytest
import asyncio
from pathlib import Path

from backend.database import Database


class TestDatabaseConnection:
    """データベース接続テスト"""

    @pytest.mark.asyncio
    async def test_connect_creates_directory(self, tmp_path):
        """接続時にディレクトリを作成"""
        db_path = tmp_path / "subdir" / "test.db"
        db = Database(db_path)

        await db.connect()

        assert db_path.parent.exists()

        await db.disconnect()

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, tmp_path):
        """接続と切断"""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        await db.connect()
        assert db._connection is not None

        await db.disconnect()
        assert db._connection is None

    @pytest.mark.asyncio
    async def test_init_tables(self, db):
        """テーブル初期化"""
        # テーブルが作成されていることを確認
        cursor = await db._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in await cursor.fetchall()]

        assert "projects" in tables
        assert "topics" in tables
        assert "scan_history" in tables


class TestProjectCRUD:
    """プロジェクトCRUD操作テスト"""

    @pytest.mark.asyncio
    async def test_upsert_project_insert(self, db):
        """プロジェクト挿入"""
        project_id = await db.upsert_project(
            name="テストプロジェクト",
            path="/test/path",
            wbs_format="object"
        )

        assert project_id > 0

        project = await db.get_project(project_id)
        assert project["name"] == "テストプロジェクト"
        assert project["path"] == "/test/path"
        assert project["wbs_format"] == "object"

    @pytest.mark.asyncio
    async def test_upsert_project_update(self, db):
        """プロジェクト更新（UPSERT）"""
        # 初回挿入
        project_id1 = await db.upsert_project(
            name="テストプロジェクト",
            path="/test/path",
            wbs_format="object"
        )

        # 同名で更新
        project_id2 = await db.upsert_project(
            name="テストプロジェクト",
            path="/new/path",
            wbs_format="array"
        )

        assert project_id1 == project_id2

        project = await db.get_project(project_id1)
        assert project["path"] == "/new/path"
        assert project["wbs_format"] == "array"

    @pytest.mark.asyncio
    async def test_get_all_projects(self, db):
        """全プロジェクト取得"""
        await db.upsert_project(name="Project A", path="/a", wbs_format="object")
        await db.upsert_project(name="Project B", path="/b", wbs_format="array")

        projects = await db.get_all_projects()

        assert len(projects) == 2
        names = [p["name"] for p in projects]
        assert "Project A" in names
        assert "Project B" in names

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, db):
        """存在しないプロジェクト取得"""
        project = await db.get_project(999)
        assert project is None

    @pytest.mark.asyncio
    async def test_get_project_by_name(self, db):
        """プロジェクト名で取得"""
        await db.upsert_project(name="テストプロジェクト", path="/test", wbs_format="object")

        project = await db.get_project_by_name("テストプロジェクト")
        assert project is not None
        assert project["name"] == "テストプロジェクト"

    @pytest.mark.asyncio
    async def test_get_project_by_name_not_found(self, db):
        """存在しない名前で取得"""
        project = await db.get_project_by_name("存在しないプロジェクト")
        assert project is None

    @pytest.mark.asyncio
    async def test_update_project_stats(self, db):
        """プロジェクト統計更新"""
        project_id = await db.upsert_project(name="Test", path="/test", wbs_format="object")

        await db.update_project_stats(
            project_id=project_id,
            total_topics=100,
            completed_topics=50,
            html_count=80,
            txt_count=60,
            mp3_count=40
        )

        project = await db.get_project(project_id)
        assert project["total_topics"] == 100
        assert project["completed_topics"] == 50
        assert project["html_count"] == 80
        assert project["txt_count"] == 60
        assert project["mp3_count"] == 40


class TestTopicCRUD:
    """トピックCRUD操作テスト"""

    @pytest.mark.asyncio
    async def test_upsert_topic_insert(self, db):
        """トピック挿入"""
        project_id = await db.upsert_project(name="Test", path="/test", wbs_format="object")

        topic_id = await db.upsert_topic(
            project_id=project_id,
            base_name="01-01_test",
            topic_id="01-01",
            chapter="Chapter 1",
            title="Test Topic",
            has_html=True,
            has_txt=False,
            has_mp3=False
        )

        assert topic_id > 0

        topics = await db.get_topics_by_project(project_id)
        assert len(topics) == 1
        assert topics[0]["base_name"] == "01-01_test"
        assert topics[0]["has_html"] == 1

    @pytest.mark.asyncio
    async def test_upsert_topic_update(self, db):
        """トピック更新（UPSERT）"""
        project_id = await db.upsert_project(name="Test", path="/test", wbs_format="object")

        # 初回挿入
        await db.upsert_topic(
            project_id=project_id,
            base_name="01-01_test",
            has_html=False,
            has_txt=False,
            has_mp3=False
        )

        # 更新
        await db.upsert_topic(
            project_id=project_id,
            base_name="01-01_test",
            has_html=True,
            has_txt=True,
            has_mp3=False
        )

        topics = await db.get_topics_by_project(project_id)
        assert len(topics) == 1
        assert topics[0]["has_html"] == 1
        assert topics[0]["has_txt"] == 1

    @pytest.mark.asyncio
    async def test_get_topics_by_project(self, db):
        """プロジェクトのトピック一覧取得"""
        project_id = await db.upsert_project(name="Test", path="/test", wbs_format="object")

        await db.upsert_topic(project_id=project_id, base_name="01-01_a")
        await db.upsert_topic(project_id=project_id, base_name="01-02_b")
        await db.upsert_topic(project_id=project_id, base_name="01-03_c")

        topics = await db.get_topics_by_project(project_id)

        assert len(topics) == 3
        # ソート順を確認
        assert topics[0]["base_name"] == "01-01_a"
        assert topics[1]["base_name"] == "01-02_b"
        assert topics[2]["base_name"] == "01-03_c"

    @pytest.mark.asyncio
    async def test_get_topic_by_base_name(self, db):
        """base_nameでトピック取得"""
        project_id = await db.upsert_project(name="Test", path="/test", wbs_format="object")

        await db.upsert_topic(
            project_id=project_id,
            base_name="01-01_test",
            title="Test Topic"
        )

        topic = await db.get_topic_by_base_name(project_id, "01-01_test")

        assert topic is not None
        assert topic["title"] == "Test Topic"

    @pytest.mark.asyncio
    async def test_delete_topics_by_project(self, db):
        """プロジェクトのトピック全削除"""
        project_id = await db.upsert_project(name="Test", path="/test", wbs_format="object")

        await db.upsert_topic(project_id=project_id, base_name="01-01_a")
        await db.upsert_topic(project_id=project_id, base_name="01-02_b")

        deleted_count = await db.delete_topics_by_project(project_id)

        assert deleted_count == 2

        topics = await db.get_topics_by_project(project_id)
        assert len(topics) == 0


class TestScanHistory:
    """スキャン履歴テスト"""

    @pytest.mark.asyncio
    async def test_create_scan_history(self, db):
        """スキャン履歴作成"""
        scan_db_id = await db.create_scan_history(
            scan_id="scan_123",
            scan_type="full",
            project_id=None
        )

        assert scan_db_id > 0

    @pytest.mark.asyncio
    async def test_update_scan_history(self, db):
        """スキャン履歴更新"""
        await db.create_scan_history(
            scan_id="scan_123",
            scan_type="full"
        )

        await db.update_scan_history(
            scan_id="scan_123",
            status="completed",
            projects_scanned=5,
            files_scanned=100,
            changes_detected=10
        )

        # 更新されていることを確認
        cursor = await db._connection.execute(
            "SELECT * FROM scan_history WHERE scan_id = ?",
            ("scan_123",)
        )
        row = await cursor.fetchone()

        assert row["status"] == "completed"
        assert row["projects_scanned"] == 5
        assert row["files_scanned"] == 100
        assert row["changes_detected"] == 10

    @pytest.mark.asyncio
    async def test_scan_history_with_error(self, db):
        """エラー付きスキャン履歴"""
        await db.create_scan_history(scan_id="scan_error", scan_type="full")

        await db.update_scan_history(
            scan_id="scan_error",
            status="failed",
            error_message="Something went wrong"
        )

        cursor = await db._connection.execute(
            "SELECT * FROM scan_history WHERE scan_id = ?",
            ("scan_error",)
        )
        row = await cursor.fetchone()

        assert row["status"] == "failed"
        assert row["error_message"] == "Something went wrong"


class TestStatistics:
    """統計テスト"""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, db):
        """空のデータベースの統計"""
        stats = await db.get_stats()

        assert stats["total_projects"] == 0
        assert stats["total_topics"] == 0
        assert stats["overall_progress"] == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, db_with_data):
        """データありの統計"""
        db, project_id = db_with_data

        stats = await db.get_stats()

        assert stats["total_projects"] == 1
        assert stats["total_topics"] == 3
        assert stats["html_total"] == 3
        assert stats["txt_total"] == 2
        assert stats["mp3_total"] == 1
        # 重み付け進捗: (3*0.4 + 2*0.3 + 1*0.3) / 3 * 100 = 70%
        assert stats["overall_progress"] == pytest.approx(70.0, 0.1)


class TestTransaction:
    """トランザクションテスト"""

    @pytest.mark.asyncio
    async def test_transaction_commit(self, db):
        """トランザクションコミット"""
        async with db.transaction():
            await db._connection.execute(
                "INSERT INTO projects (name, path) VALUES (?, ?)",
                ("Transaction Test", "/test")
            )

        # コミットされていることを確認
        cursor = await db._connection.execute(
            "SELECT * FROM projects WHERE name = ?",
            ("Transaction Test",)
        )
        row = await cursor.fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, db):
        """トランザクションロールバック"""
        try:
            async with db.transaction():
                await db._connection.execute(
                    "INSERT INTO projects (name, path) VALUES (?, ?)",
                    ("Rollback Test", "/test")
                )
                raise Exception("Force rollback")
        except Exception:
            pass

        # ロールバックされていることを確認
        cursor = await db._connection.execute(
            "SELECT * FROM projects WHERE name = ?",
            ("Rollback Test",)
        )
        row = await cursor.fetchone()
        assert row is None


class TestIndexes:
    """インデックステスト"""

    @pytest.mark.asyncio
    async def test_indexes_created(self, db):
        """インデックスが作成されていることを確認"""
        cursor = await db._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = [row[0] for row in await cursor.fetchall()]

        expected_indexes = [
            "idx_projects_name",
            "idx_projects_updated",
            "idx_topics_project",
            "idx_topics_base_name",
            "idx_topics_chapter",
            "idx_scan_history_started"
        ]

        for idx_name in expected_indexes:
            assert idx_name in indexes, f"Index {idx_name} not found"
