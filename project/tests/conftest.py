"""
pytest共通設定・フィクスチャ
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import Database


# ========== pytest-asyncio設定 ==========

pytest_plugins = ('pytest_asyncio',)


def pytest_configure(config):
    """pytest設定"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


# ========== イベントループフィクスチャ ==========

@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


# ========== データベースフィクスチャ ==========

@pytest.fixture
def db_sync(tmp_path):
    """同期テスト用データベースファクトリ"""
    async def _create_db():
        db_path = tmp_path / "test.db"
        database = Database(db_path)
        await database.connect()
        await database.init_tables()
        return database

    async def _close_db(database):
        await database.disconnect()

    return _create_db, _close_db


@pytest.fixture
async def db(tmp_path):
    """テスト用インメモリデータベース"""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    await database.connect()
    await database.init_tables()
    yield database
    await database.disconnect()


@pytest.fixture
async def db_with_data(tmp_path):
    """サンプルデータ入りデータベース"""
    db_path = tmp_path / "test_with_data.db"
    database = Database(db_path)
    await database.connect()
    await database.init_tables()

    # プロジェクト追加
    project_id = await database.upsert_project(
        name="テストプロジェクト",
        path="/test/path",
        wbs_format="object"
    )

    # トピック追加
    await database.upsert_topic(
        project_id=project_id,
        base_name="01-01_トピック1",
        topic_id="01-01",
        chapter="Chapter 1",
        title="トピック1",
        has_html=True,
        has_txt=True,
        has_mp3=True
    )

    await database.upsert_topic(
        project_id=project_id,
        base_name="01-02_トピック2",
        topic_id="01-02",
        chapter="Chapter 1",
        title="トピック2",
        has_html=True,
        has_txt=True,
        has_mp3=False
    )

    await database.upsert_topic(
        project_id=project_id,
        base_name="01-03_トピック3",
        topic_id="01-03",
        chapter="Chapter 1",
        title="トピック3",
        has_html=True,
        has_txt=False,
        has_mp3=False
    )

    # 統計更新
    await database.update_project_stats(
        project_id=project_id,
        total_topics=3,
        completed_topics=1,
        html_count=3,
        txt_count=2,
        mp3_count=1
    )

    yield database, project_id
    await database.disconnect()


# ========== WBSモックデータ ==========

@pytest.fixture
def mock_wbs_object() -> Dict[str, Any]:
    """オブジェクト型WBSモックデータ"""
    return {
        "project": {"name": "テストプロジェクト（オブジェクト型）"},
        "phases": {
            "phase_2": {
                "name": "Phase 2: コンテンツ作成",
                "chapters": {
                    "chapter_1": {
                        "name": "Chapter 1: 基礎",
                        "topics": [
                            {
                                "id": "topic_01_01",
                                "title": "トピック1-1",
                                "base_name": "01-01_トピック1-1"
                            },
                            {
                                "id": "topic_01_02",
                                "title": "トピック1-2",
                                "base_name": "01-02_トピック1-2"
                            },
                            {
                                "id": "topic_01_03",
                                "title": "トピック1-3",
                                "base_name": "01-03_トピック1-3"
                            }
                        ]
                    },
                    "chapter_2": {
                        "name": "Chapter 2: 応用",
                        "topics": [
                            {
                                "id": "topic_02_01",
                                "title": "トピック2-1",
                                "base_name": "02-01_トピック2-1"
                            },
                            {
                                "id": "topic_02_02",
                                "title": "トピック2-2",
                                "base_name": "02-02_トピック2-2"
                            }
                        ]
                    }
                }
            }
        }
    }


@pytest.fixture
def mock_wbs_array() -> Dict[str, Any]:
    """配列型WBSモックデータ"""
    return {
        "project": {"name": "テストプロジェクト（配列型）"},
        "phases": [
            {
                "id": "phase2",
                "name": "Phase 2: コンテンツ作成",
                "parts": [
                    {
                        "id": "part1",
                        "chapters": [
                            {"id": "ch1", "name": "Chapter 1: 基礎", "topics": 3},
                            {"id": "ch2", "name": "Chapter 2: 応用", "topics": 2}
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture
def mock_wbs_empty() -> Dict[str, Any]:
    """空のWBSデータ"""
    return {"phases": {}}


@pytest.fixture
def mock_wbs_invalid() -> Dict[str, Any]:
    """不正なWBSデータ"""
    return {"phases": "invalid"}


# ========== ファイルシステムフィクスチャ ==========

@pytest.fixture
def content_dir(tmp_path):
    """テスト用コンテンツディレクトリ"""
    content = tmp_path / "content"
    content.mkdir()
    return content


@pytest.fixture
def content_dir_with_files(tmp_path):
    """ファイル入りコンテンツディレクトリ"""
    content_dir = tmp_path / "content_with_files"
    content_dir.mkdir()

    # 完了トピック（HTML + TXT + MP3）
    (content_dir / "01-01_トピック1.html").write_text("<html><body>Content 1</body></html>")
    (content_dir / "01-01_トピック1.txt").write_text("Text content 1")
    (content_dir / "01-01_トピック1.mp3").write_bytes(b'\x00\x01\x02')

    # 進行中トピック（HTML + TXT）
    (content_dir / "01-02_トピック2.html").write_text("<html><body>Content 2</body></html>")
    (content_dir / "01-02_トピック2.txt").write_text("Text content 2")

    # HTMLのみトピック
    (content_dir / "01-03_トピック3.html").write_text("<html><body>Content 3</body></html>")

    return content_dir


@pytest.fixture
def project_dir(tmp_path, mock_wbs_object):
    """テスト用プロジェクトディレクトリ"""
    project = tmp_path / "test_project"
    project.mkdir()

    # WBS.json作成
    wbs_path = project / "WBS.json"
    wbs_path.write_text(json.dumps(mock_wbs_object, ensure_ascii=False))

    # contentディレクトリ作成
    content_path = project / "content"
    content_path.mkdir()

    # 完了トピック（HTML + TXT + MP3）
    (content_path / "01-01_トピック1.html").write_text("<html><body>Content 1</body></html>")
    (content_path / "01-01_トピック1.txt").write_text("Text content 1")
    (content_path / "01-01_トピック1.mp3").write_bytes(b'\x00\x01\x02')

    # 進行中トピック（HTML + TXT）
    (content_path / "01-02_トピック2.html").write_text("<html><body>Content 2</body></html>")
    (content_path / "01-02_トピック2.txt").write_text("Text content 2")

    # HTMLのみトピック
    (content_path / "01-03_トピック3.html").write_text("<html><body>Content 3</body></html>")

    return project


# ========== モッククラス ==========

@dataclass
class MockTopic:
    """モックトピッククラス"""
    has_html: bool = False
    has_txt: bool = False
    has_mp3: bool = False
    base_name: str = "01-01_test"
    topic_id: str = "01-01"
    chapter: str = "Chapter 1"
    title: str = "Test Topic"


@pytest.fixture
def mock_topic():
    """モックトピックファクトリ"""
    return MockTopic


# ========== HTTPクライアントフィクスチャ ==========

@pytest.fixture
def test_client(db):
    """FastAPI TestClient"""
    from fastapi.testclient import TestClient
    from backend.main import app

    # データベースを上書き
    async def override_get_database():
        return db

    from backend import api
    from backend.database import get_database

    app.dependency_overrides[get_database] = override_get_database

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
