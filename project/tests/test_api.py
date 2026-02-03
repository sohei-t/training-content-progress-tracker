"""
APIテスト
テスト対象: backend/api.py
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json

# テスト用のシンプルなアプリを作成
from backend.api import router
from backend.database import Database


# テスト用FastAPIアプリ
test_app = FastAPI()
test_app.include_router(router)


@pytest.fixture
def client():
    """TestClient フィクスチャ"""
    return TestClient(test_app)


@pytest.fixture
async def mock_db():
    """モックデータベース"""
    db = AsyncMock(spec=Database)

    # デフォルトの戻り値を設定
    db.get_all_projects = AsyncMock(return_value=[])
    db.get_project = AsyncMock(return_value=None)
    db.get_topics_by_project = AsyncMock(return_value=[])
    db.get_stats = AsyncMock(return_value={
        "total_projects": 0,
        "total_topics": 0,
        "completed_topics": 0,
        "overall_progress": 0.0,
        "html_total": 0,
        "txt_total": 0,
        "mp3_total": 0
    })

    return db


class TestProjectsAPI:
    """プロジェクトAPI テスト"""

    def test_API001_get_projects_empty(self, client):
        """API-001: プロジェクト一覧取得（空）"""
        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_all_projects = AsyncMock(return_value=[])
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects")

        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "total" in data
        assert isinstance(data["projects"], list)
        assert data["total"] == 0

    def test_API001_get_projects_with_data(self, client):
        """API-001: プロジェクト一覧取得（データあり）"""
        mock_projects = [
            {
                "id": 1,
                "name": "Project A",
                "path": "/path/a",
                "total_topics": 10,
                "completed_topics": 5,
                "html_count": 8,
                "txt_count": 6,
                "mp3_count": 4,
                "last_scanned_at": "2024-01-01T00:00:00"
            },
            {
                "id": 2,
                "name": "Project B",
                "path": "/path/b",
                "total_topics": 20,
                "completed_topics": 10,
                "html_count": 15,
                "txt_count": 12,
                "mp3_count": 8,
                "last_scanned_at": "2024-01-02T00:00:00"
            }
        ]

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_all_projects = AsyncMock(return_value=mock_projects)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects")

        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 2
        assert data["total"] == 2
        assert data["projects"][0]["name"] == "Project A"

    def test_API002_get_project_detail(self, client):
        """API-002: プロジェクト詳細取得"""
        mock_project = {
            "id": 1,
            "name": "Test Project",
            "path": "/test",
            "total_topics": 10,
            "completed_topics": 5,
            "html_count": 8,
            "txt_count": 6,
            "mp3_count": 4
        }

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_project = AsyncMock(return_value=mock_project)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Test Project"
        assert "progress" in data

    def test_API003_get_nonexistent_project(self, client):
        """API-003: 存在しないプロジェクト"""
        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_project = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects/999")

        assert response.status_code == 404

    def test_API004_get_topics(self, client):
        """API-004: トピック一覧取得"""
        mock_project = {
            "id": 1,
            "name": "Test Project",
            "path": "/test"
        }
        mock_topics = [
            {"id": 1, "base_name": "01-01_test", "has_html": 1, "has_txt": 1, "has_mp3": 1},
            {"id": 2, "base_name": "01-02_test", "has_html": 1, "has_txt": 1, "has_mp3": 0},
            {"id": 3, "base_name": "01-03_test", "has_html": 1, "has_txt": 0, "has_mp3": 0},
            {"id": 4, "base_name": "01-04_test", "has_html": 0, "has_txt": 0, "has_mp3": 0},
        ]

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_project = AsyncMock(return_value=mock_project)
            mock_db.get_topics_by_project = AsyncMock(return_value=mock_topics)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects/1/topics")

        assert response.status_code == 200
        data = response.json()
        assert "topics" in data
        assert "summary" in data
        assert len(data["topics"]) == 4
        assert data["summary"]["total"] == 4
        assert data["summary"]["completed"] == 1
        assert data["summary"]["in_progress"] == 2
        assert data["summary"]["not_started"] == 1

    def test_API004_get_topics_nonexistent_project(self, client):
        """API-004: 存在しないプロジェクトのトピック"""
        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_project = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects/999/topics")

        assert response.status_code == 404


class TestScanAPI:
    """スキャンAPI テスト"""

    def test_API006_trigger_scan(self, client):
        """API-006: 手動スキャン実行"""
        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.create_scan_history = AsyncMock(return_value=1)
            mock_get_db.return_value = mock_db

            response = client.post(
                "/api/scan",
                json={"scan_type": "full"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "scan_id" in data

    def test_trigger_scan_diff(self, client):
        """差分スキャン実行"""
        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.create_scan_history = AsyncMock(return_value=1)
            mock_get_db.return_value = mock_db

            response = client.post(
                "/api/scan",
                json={"scan_type": "diff", "project_id": 1}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"


class TestStatsAPI:
    """統計API テスト"""

    def test_API005_get_stats(self, client):
        """API-005: 全体統計取得"""
        mock_stats = {
            "total_projects": 5,
            "total_topics": 100,
            "completed_topics": 50,
            "overall_progress": 65.5,
            "html_total": 80,
            "txt_total": 60,
            "mp3_total": 40
        }

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_stats = AsyncMock(return_value=mock_stats)
            mock_get_db.return_value = mock_db

            response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_projects"] == 5
        assert data["total_topics"] == 100
        assert data["overall_progress"] == 65.5


class TestHealthAPI:
    """ヘルスチェックAPI テスト"""

    def test_health_check(self, client):
        """ヘルスチェック"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestResponseSchema:
    """レスポンススキーマ テスト"""

    def test_API008_projects_response_schema(self, client):
        """API-008: プロジェクトレスポンス形式検証"""
        mock_projects = [
            {
                "id": 1,
                "name": "Test Project",
                "path": "/test",
                "total_topics": 10,
                "completed_topics": 5,
                "html_count": 8,
                "txt_count": 6,
                "mp3_count": 4,
                "last_scanned_at": "2024-01-01T00:00:00"
            }
        ]

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_all_projects = AsyncMock(return_value=mock_projects)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects")

        assert response.status_code == 200
        data = response.json()

        # 必須フィールド検証
        for project in data["projects"]:
            assert "id" in project
            assert "name" in project
            assert "total_topics" in project
            assert "progress" in project
            assert "progress_detail" in project
            assert 0 <= project["progress"] <= 100
            assert "html" in project["progress_detail"]
            assert "txt" in project["progress_detail"]
            assert "mp3" in project["progress_detail"]


class TestProgressCalculation:
    """進捗計算テスト"""

    def test_progress_calculation_full(self, client):
        """全ファイル完了時の進捗率"""
        mock_projects = [
            {
                "id": 1,
                "name": "Complete Project",
                "path": "/test",
                "total_topics": 10,
                "completed_topics": 10,
                "html_count": 10,
                "txt_count": 10,
                "mp3_count": 10,
                "last_scanned_at": None
            }
        ]

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_all_projects = AsyncMock(return_value=mock_projects)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects")

        data = response.json()
        project = data["projects"][0]
        assert project["progress"] == 100.0
        assert project["progress_detail"]["html"] == 100.0
        assert project["progress_detail"]["txt"] == 100.0
        assert project["progress_detail"]["mp3"] == 100.0

    def test_progress_calculation_partial(self, client):
        """部分完了時の進捗率"""
        mock_projects = [
            {
                "id": 1,
                "name": "Partial Project",
                "path": "/test",
                "total_topics": 10,
                "completed_topics": 0,
                "html_count": 10,  # 100% HTML
                "txt_count": 5,   # 50% TXT
                "mp3_count": 0,   # 0% MP3
                "last_scanned_at": None
            }
        ]

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_all_projects = AsyncMock(return_value=mock_projects)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects")

        data = response.json()
        project = data["projects"][0]

        # 重み付け進捗: (10*0.4 + 5*0.3 + 0*0.3) / 10 * 100 = 55%
        assert project["progress"] == pytest.approx(55.0, 0.1)

    def test_progress_calculation_zero_topics(self, client):
        """トピックなしの進捗率"""
        mock_projects = [
            {
                "id": 1,
                "name": "Empty Project",
                "path": "/test",
                "total_topics": 0,
                "completed_topics": 0,
                "html_count": 0,
                "txt_count": 0,
                "mp3_count": 0,
                "last_scanned_at": None
            }
        ]

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_all_projects = AsyncMock(return_value=mock_projects)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects")

        data = response.json()
        project = data["projects"][0]
        assert project["progress"] == 0
        assert project["progress_detail"] == {"html": 0, "txt": 0, "mp3": 0}


class TestTopicStatus:
    """トピックステータステスト"""

    def test_topic_status_completed(self, client):
        """完了ステータス"""
        mock_project = {"id": 1, "name": "Test", "path": "/test"}
        mock_topics = [
            {"id": 1, "base_name": "test", "has_html": 1, "has_txt": 1, "has_mp3": 1}
        ]

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_project = AsyncMock(return_value=mock_project)
            mock_db.get_topics_by_project = AsyncMock(return_value=mock_topics)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects/1/topics")

        data = response.json()
        assert data["topics"][0]["status"] == "completed"

    def test_topic_status_in_progress(self, client):
        """進行中ステータス"""
        mock_project = {"id": 1, "name": "Test", "path": "/test"}
        mock_topics = [
            {"id": 1, "base_name": "test", "has_html": 1, "has_txt": 1, "has_mp3": 0}
        ]

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_project = AsyncMock(return_value=mock_project)
            mock_db.get_topics_by_project = AsyncMock(return_value=mock_topics)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects/1/topics")

        data = response.json()
        assert data["topics"][0]["status"] == "in_progress"

    def test_topic_status_not_started(self, client):
        """未着手ステータス"""
        mock_project = {"id": 1, "name": "Test", "path": "/test"}
        mock_topics = [
            {"id": 1, "base_name": "test", "has_html": 0, "has_txt": 0, "has_mp3": 0}
        ]

        with patch('backend.api.get_database') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_project = AsyncMock(return_value=mock_project)
            mock_db.get_topics_by_project = AsyncMock(return_value=mock_topics)
            mock_get_db.return_value = mock_db

            response = client.get("/api/projects/1/topics")

        data = response.json()
        assert data["topics"][0]["status"] == "not_started"
