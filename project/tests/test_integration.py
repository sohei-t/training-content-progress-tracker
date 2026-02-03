"""
統合テスト
スキャン→DB保存→API取得、WebSocket通知など複数コンポーネント連携のテスト
"""

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock


# ========== スキャン→DB フローテスト ==========

class TestScanToDatabaseFlow:
    """スキャンからDB保存までのテスト"""

    @pytest.fixture
    def simple_project(self, tmp_path):
        """シンプルなテスト用プロジェクト"""
        project_dir = tmp_path / "SimpleProject"
        project_dir.mkdir()

        wbs_data = {
            "project": {"name": "SimpleProject"},
            "phases": {
                "phase_2": {
                    "chapters": {
                        "ch1": {
                            "name": "Chapter 1",
                            "topics": [
                                {"id": "01-01", "title": "Topic1", "base_name": "01-01_Topic1"}
                            ]
                        }
                    }
                }
            }
        }
        (project_dir / "WBS.json").write_text(json.dumps(wbs_data))

        content_dir = project_dir / "content"
        content_dir.mkdir()
        (content_dir / "01-01_Topic1.html").write_text("<html></html>")
        (content_dir / "01-01_Topic1.txt").write_text("text")
        (content_dir / "01-01_Topic1.mp3").write_bytes(b'\x00')

        return project_dir

    @pytest.mark.asyncio
    async def test_INT001_scan_stores_to_database(self, simple_project, db):
        """INT001: スキャン結果がデータベースに保存される"""
        from backend.scanner import AsyncScanner

        scanner = AsyncScanner(db, simple_project.parent)
        result = await scanner.scan_project(simple_project)

        assert result is not None
        assert result.project_name == "SimpleProject"
        assert result.total_topics == 1
        assert result.completed_topics == 1

    @pytest.mark.asyncio
    async def test_INT002_database_query(self, simple_project, db):
        """INT002: データベースからデータを取得できる"""
        from backend.scanner import AsyncScanner

        scanner = AsyncScanner(db, simple_project.parent)
        await scanner.scan_project(simple_project)

        project = await db.get_project_by_name("SimpleProject")
        assert project is not None
        assert project["total_topics"] == 1


class TestWebSocketFlow:
    """WebSocket通知フローのテスト"""

    @pytest.mark.asyncio
    async def test_INT003_broadcast_message(self):
        """INT003: ブロードキャストメッセージが送信される"""
        from backend.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await manager.connect(mock_ws)
        await manager.broadcast("test", {"data": "value"})

        mock_ws.send_text.assert_called_once()
        await manager.disconnect(mock_ws)


class TestStatsFlow:
    """統計集計フローのテスト"""

    @pytest.mark.asyncio
    async def test_INT004_stats_aggregation(self, db):
        """INT004: 統計が正しく集計される"""
        # プロジェクト追加
        await db.upsert_project(
            name="StatsProject",
            path="/test",
            wbs_format="object"
        )

        stats = await db.get_stats()
        assert stats["total_projects"] >= 1
