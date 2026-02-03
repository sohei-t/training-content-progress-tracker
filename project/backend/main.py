"""
FastAPIメインアプリケーション
パフォーマンス最適化: uvloop対応、静的ファイル配信最適化、非同期初期化
"""

import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import sys

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .database import get_database, close_database
from .scanner import AsyncScanner
from .watcher import MultiProjectWatcher
from .websocket import get_connection_manager
from .api import router as api_router

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# パス設定
BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DEFAULT_CONTENT_PATH = Path("/Users/sohei/Desktop/Learning-Curricula")

# グローバル状態
_watcher: MultiProjectWatcher = None
_scanner: AsyncScanner = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションライフサイクル管理"""
    global _watcher, _scanner

    logger.info("Starting application...")

    # データベース初期化
    db = await get_database()
    logger.info("Database initialized")

    # スキャナー初期化
    _scanner = AsyncScanner(db, DEFAULT_CONTENT_PATH)

    # ファイルウォッチャー初期化
    ws = get_connection_manager()

    async def on_file_change(project_name: str, paths: list):
        """ファイル変更時のコールバック"""
        logger.info(f"File change detected in {project_name}: {len(paths)} files")

        # 差分スキャン実行
        project = await db.get_project_by_name(project_name)
        if project:
            project_path = Path(project['path'])
            result = await _scanner.scan_project(project_path)

            # WebSocket通知
            updated_project = await db.get_project_by_name(project_name)
            if updated_project:
                await ws.broadcast_project_update(dict(updated_project))

    _watcher = MultiProjectWatcher(
        DEFAULT_CONTENT_PATH,
        on_file_change,
        debounce_ms=100
    )
    await _watcher.start()
    logger.info("File watcher started")

    # 初回スキャン（バックグラウンド）
    asyncio.create_task(_initial_scan())

    yield

    # シャットダウン
    logger.info("Shutting down...")
    await _watcher.stop()
    await close_database()
    logger.info("Shutdown complete")


async def _initial_scan():
    """初回フルスキャン"""
    global _scanner
    try:
        logger.info("Starting initial scan...")
        start_time = datetime.now()
        results = await _scanner.scan_all_projects()
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Initial scan completed: {len(results)} projects in {duration:.2f}s")

        # WebSocket通知
        ws = get_connection_manager()
        await ws.broadcast("scan_completed", {
            "type": "initial",
            "projects_scanned": len(results),
            "duration_seconds": duration
        })

    except Exception as e:
        logger.error(f"Initial scan error: {e}")


# FastAPIアプリ初期化
app = FastAPI(
    title="研修コンテンツ進捗トラッカー",
    description="リアルタイム進捗トラッキングダッシュボード（パフォーマンス最優先）",
    version="1.0.0",
    lifespan=lifespan
)

# CORS設定（ローカル開発用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIルーター登録
app.include_router(api_router)


# WebSocketエンドポイント
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket接続エンドポイント"""
    manager = get_connection_manager()

    connected = await manager.connect(websocket)
    if not connected:
        return

    try:
        # 接続確立を通知
        await manager.send_personal(
            websocket,
            "connected",
            {
                "message": "WebSocket connected",
                "client_count": manager.get_connection_count()
            }
        )

        # メッセージ受信ループ
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received WebSocket message: {data}")

                # pingに応答
                if data == "ping":
                    await manager.send_personal(websocket, "pong", {})

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        await manager.disconnect(websocket)


# 静的ファイル配信
@app.get("/")
async def serve_index():
    """インデックスページ配信"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "Frontend not found"}


# 静的ファイルマウント（CSS, JS, assets）
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


# 手動スキャントリガーエンドポイント（開発用）
@app.post("/api/force-scan")
async def force_scan():
    """強制フルスキャン（開発用）"""
    global _scanner
    if _scanner:
        _scanner.clear_cache()
        results = await _scanner.scan_all_projects()
        return {
            "status": "completed",
            "projects_scanned": len(results),
            "results": [
                {
                    "name": r.project_name,
                    "topics": r.total_topics,
                    "html": r.html_count,
                    "txt": r.txt_count,
                    "mp3": r.mp3_count
                }
                for r in results
            ]
        }
    return {"error": "Scanner not initialized"}


# エントリーポイント
if __name__ == "__main__":
    import uvicorn

    # uvloop使用（利用可能な場合）
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logger.info("Using uvloop for better performance")
    except ImportError:
        logger.info("uvloop not available, using default event loop")

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
