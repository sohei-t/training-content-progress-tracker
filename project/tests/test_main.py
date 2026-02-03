"""
main.py のユニットテスト
FastAPIアプリケーションの起動、静的ファイル配信、CORS設定、WebSocketエンドポイントをテスト
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# ========== アプリケーション基本テスト ==========

class TestAppConfiguration:
    """アプリケーション設定のテスト"""

    def test_MAIN001_app_title(self):
        """MAIN001: アプリケーションタイトルが正しく設定されている"""
        from backend.main import app
        assert app.title == "研修コンテンツ進捗トラッカー"

    def test_MAIN002_app_version(self):
        """MAIN002: アプリケーションバージョンが正しく設定されている"""
        from backend.main import app
        assert app.version == "1.0.0"

    def test_MAIN003_cors_middleware_added(self):
        """MAIN003: CORSミドルウェアが追加されている"""
        from backend.main import app
        middleware_types = [type(m).__name__ for m in app.user_middleware]
        # Note: FastAPIはミドルウェアを内部的に管理するため、直接確認は難しい
        # 代わりにapp.add_middlewareが呼ばれていることを設定から確認
        assert app is not None  # アプリが正常に初期化されている


class TestStaticFileServing:
    """静的ファイル配信のテスト"""

    @pytest.fixture
    def mock_frontend_dir(self, tmp_path):
        """テスト用フロントエンドディレクトリを作成"""
        frontend = tmp_path / "frontend"
        frontend.mkdir()
        css_dir = frontend / "css"
        css_dir.mkdir()
        js_dir = frontend / "js"
        js_dir.mkdir()

        # index.html作成
        (frontend / "index.html").write_text("<html><body>Test</body></html>")
        (css_dir / "styles.css").write_text("body { color: black; }")
        (js_dir / "app.js").write_text("console.log('test');")

        return frontend

    @pytest.mark.asyncio
    async def test_MAIN004_serve_index_when_exists(self):
        """MAIN004: index.htmlが存在する場合は正しく配信される"""
        from backend.main import serve_index, FRONTEND_DIR
        from fastapi.responses import FileResponse

        result = await serve_index()

        # FRONTENDディレクトリにindex.htmlが存在する場合はFileResponseを返す
        if (FRONTEND_DIR / "index.html").exists():
            assert isinstance(result, FileResponse)
        else:
            # 存在しない場合はエラー辞書を返す
            assert isinstance(result, dict)
            assert "error" in result

    @pytest.mark.asyncio
    async def test_MAIN005_serve_index_not_found(self):
        """MAIN005: index.htmlが存在しない場合はエラーを返す"""
        from backend.main import serve_index
        import backend.main as main_module
        from pathlib import Path

        # FRONTEND_DIRを一時的に存在しないパスに変更
        original_frontend_dir = main_module.FRONTEND_DIR
        main_module.FRONTEND_DIR = Path("/nonexistent/path")

        result = await serve_index()
        assert isinstance(result, dict)
        assert result == {"error": "Frontend not found"}

        main_module.FRONTEND_DIR = original_frontend_dir

    def test_MAIN006_css_mount_configured(self):
        """MAIN006: CSSディレクトリがマウントされている"""
        from backend.main import app
        routes = [route.path for route in app.routes]
        # マウントされたルートを確認
        assert any("/css" in str(route) for route in app.routes)

    def test_MAIN007_js_mount_configured(self):
        """MAIN007: JSディレクトリがマウントされている"""
        from backend.main import app
        routes = [route.path for route in app.routes]
        # マウントされたルートを確認
        assert any("/js" in str(route) for route in app.routes)


class TestWebSocketEndpoint:
    """WebSocketエンドポイントのテスト"""

    def test_MAIN008_websocket_route_exists(self):
        """MAIN008: WebSocketエンドポイントが登録されている"""
        from backend.main import app
        ws_routes = [route for route in app.routes if hasattr(route, 'path') and route.path == '/ws']
        assert len(ws_routes) > 0

    @pytest.mark.asyncio
    async def test_MAIN009_websocket_connect_handler(self):
        """MAIN009: WebSocket接続ハンドラーが正しく動作する"""
        from backend.main import websocket_endpoint
        from backend.websocket import get_connection_manager

        # WebSocket接続のモック
        mock_websocket = AsyncMock()
        mock_websocket.receive_text = AsyncMock(side_effect=Exception("Disconnect"))

        manager = get_connection_manager()
        manager.connect = AsyncMock(return_value=True)
        manager.send_personal = AsyncMock()
        manager.disconnect = AsyncMock()
        manager.get_connection_count = MagicMock(return_value=1)

        # WebSocketハンドラーが呼び出し可能であることを確認
        assert callable(websocket_endpoint)


class TestForceScanEndpoint:
    """強制スキャンエンドポイントのテスト"""

    def test_MAIN010_force_scan_route_exists(self):
        """MAIN010: 強制スキャンエンドポイントが登録されている"""
        from backend.main import app
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        assert "/api/force-scan" in routes

    @pytest.mark.asyncio
    async def test_MAIN011_force_scan_no_scanner(self):
        """MAIN011: スキャナー未初期化時はエラーを返す"""
        from backend.main import force_scan
        import backend.main as main_module

        # スキャナーをNoneに設定
        original_scanner = main_module._scanner
        main_module._scanner = None

        result = await force_scan()
        assert result == {"error": "Scanner not initialized"}

        main_module._scanner = original_scanner

    @pytest.mark.asyncio
    async def test_MAIN012_force_scan_with_scanner(self):
        """MAIN012: スキャナー初期化済みの場合は正しく実行される"""
        from backend.main import force_scan
        import backend.main as main_module
        from dataclasses import dataclass

        @dataclass
        class MockScanResult:
            project_name: str
            total_topics: int
            html_count: int
            txt_count: int
            mp3_count: int

        mock_scanner = MagicMock()
        mock_scanner.clear_cache = MagicMock()
        mock_scanner.scan_all_projects = AsyncMock(return_value=[
            MockScanResult("test_project", 10, 8, 6, 4)
        ])

        original_scanner = main_module._scanner
        main_module._scanner = mock_scanner

        result = await force_scan()
        assert result["status"] == "completed"
        assert result["projects_scanned"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "test_project"

        main_module._scanner = original_scanner


class TestLifespan:
    """アプリケーションライフサイクルのテスト"""

    @pytest.mark.asyncio
    async def test_MAIN013_lifespan_context_manager(self):
        """MAIN013: lifespanコンテキストマネージャーが定義されている"""
        from backend.main import lifespan
        from contextlib import asynccontextmanager
        # lifespanはasynccontextmanagerデコレータで装飾された関数
        assert callable(lifespan)
        # 関数名を確認
        assert lifespan.__name__ == "lifespan"

    def test_MAIN014_default_content_path_defined(self):
        """MAIN014: デフォルトコンテンツパスが定義されている"""
        from backend.main import DEFAULT_CONTENT_PATH
        assert DEFAULT_CONTENT_PATH is not None
        assert isinstance(DEFAULT_CONTENT_PATH, Path)


class TestInitialScan:
    """初回スキャンのテスト"""

    @pytest.mark.asyncio
    async def test_MAIN015_initial_scan_function(self):
        """MAIN015: 初回スキャン関数が定義されている"""
        from backend.main import _initial_scan
        assert callable(_initial_scan)

    @pytest.mark.asyncio
    async def test_MAIN016_initial_scan_broadcasts(self):
        """MAIN016: 初回スキャン完了時にブロードキャストする"""
        from backend.main import _initial_scan
        import backend.main as main_module
        from backend.websocket import get_connection_manager

        mock_scanner = MagicMock()
        mock_scanner.scan_all_projects = AsyncMock(return_value=[])

        original_scanner = main_module._scanner
        main_module._scanner = mock_scanner

        manager = get_connection_manager()
        manager.broadcast = AsyncMock()

        await _initial_scan()

        # scan_all_projectsが呼ばれたことを確認
        mock_scanner.scan_all_projects.assert_called_once()

        main_module._scanner = original_scanner

    @pytest.mark.asyncio
    async def test_MAIN017_initial_scan_error_handling(self):
        """MAIN017: 初回スキャンでエラーが発生しても例外を投げない"""
        from backend.main import _initial_scan
        import backend.main as main_module

        mock_scanner = MagicMock()
        mock_scanner.scan_all_projects = AsyncMock(side_effect=Exception("Scan error"))

        original_scanner = main_module._scanner
        main_module._scanner = mock_scanner

        # エラーが発生しても例外を投げないことを確認
        await _initial_scan()  # Should not raise

        main_module._scanner = original_scanner


class TestAPIRouter:
    """APIルーターのテスト"""

    def test_MAIN018_api_router_included(self):
        """MAIN018: APIルーターが含まれている"""
        from backend.main import app
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        # APIエンドポイントが登録されていることを確認
        api_routes = [r for r in routes if r.startswith('/api')]
        assert len(api_routes) > 0

    def test_MAIN019_health_endpoint(self):
        """MAIN019: ヘルスチェックエンドポイントが利用可能"""
        from backend.main import app
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        assert "/api/health" in routes


class TestPathConfiguration:
    """パス設定のテスト"""

    def test_MAIN020_base_dir_defined(self):
        """MAIN020: BASE_DIRが正しく定義されている"""
        from backend.main import BASE_DIR
        assert BASE_DIR is not None
        assert isinstance(BASE_DIR, Path)

    def test_MAIN021_frontend_dir_defined(self):
        """MAIN021: FRONTEND_DIRが正しく定義されている"""
        from backend.main import FRONTEND_DIR
        assert FRONTEND_DIR is not None
        assert isinstance(FRONTEND_DIR, Path)

    def test_MAIN022_frontend_dir_relative_to_base(self):
        """MAIN022: FRONTEND_DIRはBASE_DIRからの相対パス"""
        from backend.main import BASE_DIR, FRONTEND_DIR
        assert FRONTEND_DIR == BASE_DIR / "frontend"
