"""
REST APIルーター
パフォーマンス最適化: 非同期処理、レスポンスキャッシュ、軽量バリデーション
"""

from datetime import datetime
from typing import Optional
from pathlib import Path
import uuid
import asyncio

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from .database import get_database
from .scanner import AsyncScanner
from .websocket import get_connection_manager
from .models import (
    ProjectListResponse,
    ProjectDetailResponse,
    ScanRequest,
    ScanResponse,
    StatsResponse,
    ErrorResponse
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["API"])

# デフォルトコンテンツパス
DEFAULT_CONTENT_PATH = Path("/Users/sohei/Desktop/Learning-Curricula")


# ========== プロジェクトAPI ==========

@router.get("/projects", response_model=ProjectListResponse)
async def get_projects():
    """プロジェクト一覧取得"""
    try:
        db = await get_database()
        projects = await db.get_all_projects()

        # 進捗率を計算して追加
        result = []
        for p in projects:
            project_data = dict(p)
            total = project_data.get('total_topics', 0)

            if total > 0:
                # 重み付け進捗率
                progress = (
                    (project_data.get('html_count', 0) * 0.4) +
                    (project_data.get('txt_count', 0) * 0.3) +
                    (project_data.get('mp3_count', 0) * 0.3)
                ) / total * 100
                project_data['progress'] = round(progress, 1)

                # 詳細進捗
                project_data['progress_detail'] = {
                    'html': round(project_data.get('html_count', 0) / total * 100, 1),
                    'txt': round(project_data.get('txt_count', 0) / total * 100, 1),
                    'mp3': round(project_data.get('mp3_count', 0) / total * 100, 1)
                }
            else:
                project_data['progress'] = 0
                project_data['progress_detail'] = {'html': 0, 'txt': 0, 'mp3': 0}

            result.append(project_data)

        # 最終更新日時を取得
        last_updated = None
        if result:
            dates = [p.get('last_scanned_at') for p in result if p.get('last_scanned_at')]
            if dates:
                last_updated = max(dates)

        return ProjectListResponse(
            projects=result,
            total=len(result),
            last_updated=last_updated
        )

    except Exception as e:
        logger.error(f"Error getting projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(project_id: int):
    """プロジェクト詳細取得"""
    try:
        db = await get_database()
        project = await db.get_project(project_id)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        project_data = dict(project)
        total = project_data.get('total_topics', 0)

        if total > 0:
            project_data['progress'] = (
                (project_data.get('html_count', 0) * 0.4) +
                (project_data.get('txt_count', 0) * 0.3) +
                (project_data.get('mp3_count', 0) * 0.3)
            ) / total * 100
            project_data['progress'] = round(project_data['progress'], 1)
        else:
            project_data['progress'] = 0

        return project_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/topics", response_model=ProjectDetailResponse)
async def get_project_topics(project_id: int):
    """プロジェクトのトピック一覧取得"""
    try:
        db = await get_database()
        project = await db.get_project(project_id)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        topics = await db.get_topics_by_project(project_id)

        # トピックにステータスを追加
        result_topics = []
        completed = 0
        in_progress = 0
        not_started = 0

        for t in topics:
            topic_data = dict(t)

            # Boolean変換
            topic_data['has_html'] = bool(topic_data.get('has_html'))
            topic_data['has_txt'] = bool(topic_data.get('has_txt'))
            topic_data['has_mp3'] = bool(topic_data.get('has_mp3'))
            topic_data['has_ssml'] = bool(topic_data.get('has_ssml'))

            # ステータス計算（SSMLは進捗に影響しない）
            if topic_data['has_html'] and topic_data['has_txt'] and topic_data['has_mp3']:
                topic_data['status'] = 'completed'
                completed += 1
            elif topic_data['has_html'] or topic_data['has_txt'] or topic_data['has_mp3']:
                topic_data['status'] = 'in_progress'
                in_progress += 1
            else:
                topic_data['status'] = 'not_started'
                not_started += 1

            result_topics.append(topic_data)

        return ProjectDetailResponse(
            project_id=project_id,
            project_name=project['name'],
            topics=result_topics,
            summary={
                'total': len(result_topics),
                'completed': completed,
                'in_progress': in_progress,
                'not_started': not_started
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting topics for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== スキャンAPI ==========

@router.post("/scan", response_model=ScanResponse)
async def trigger_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks
):
    """スキャンをトリガー"""
    scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    try:
        db = await get_database()

        # スキャン履歴を作成
        await db.create_scan_history(
            scan_id=scan_id,
            scan_type=request.scan_type,
            project_id=request.project_id
        )

        # バックグラウンドでスキャン実行
        background_tasks.add_task(
            _run_scan,
            scan_id,
            request.project_id,
            request.scan_type
        )

        return ScanResponse(
            status="accepted",
            scan_id=scan_id,
            message="スキャンを開始しました"
        )

    except Exception as e:
        logger.error(f"Error triggering scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_scan(
    scan_id: str,
    project_id: Optional[int],
    scan_type: str
):
    """バックグラウンドスキャン実行"""
    db = await get_database()
    ws = get_connection_manager()

    try:
        # スキャン開始を通知
        await ws.broadcast_scan_started(scan_id, project_id, scan_type)

        # スキャナー初期化
        scanner = AsyncScanner(db, DEFAULT_CONTENT_PATH)

        if project_id:
            # 単一プロジェクトスキャン
            project = await db.get_project(project_id)
            if project:
                result = await scanner.scan_project(Path(project['path']))
                results = [result]
            else:
                results = []
        else:
            # 全プロジェクトスキャン
            results = await scanner.scan_all_projects()

        # 結果を集計
        total_files = sum(r.files_scanned for r in results)
        total_changes = sum(r.changes_detected for r in results)

        # スキャン履歴を更新
        await db.update_scan_history(
            scan_id=scan_id,
            status="completed",
            projects_scanned=len(results),
            files_scanned=total_files,
            changes_detected=total_changes
        )

        # 完了を通知
        await ws.broadcast_scan_completed(
            scan_id,
            {
                "projects_scanned": len(results),
                "files_scanned": total_files,
                "changes_detected": total_changes
            }
        )

        # 各プロジェクトの更新を通知
        for result in results:
            project = await db.get_project_by_name(result.project_name)
            if project:
                await ws.broadcast_project_update(dict(project))

        logger.info(f"Scan completed: {scan_id}")

    except Exception as e:
        logger.error(f"Scan error: {e}")
        await db.update_scan_history(
            scan_id=scan_id,
            status="failed",
            error_message=str(e)
        )


# ========== 統計API ==========

@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """全体統計取得"""
    try:
        db = await get_database()
        stats = await db.get_stats()

        return StatsResponse(
            total_projects=stats['total_projects'],
            total_topics=stats['total_topics'],
            completed_topics=stats['completed_topics'],
            overall_progress=stats['overall_progress'],
            html_total=stats['html_total'],
            txt_total=stats['txt_total'],
            mp3_total=stats['mp3_total']
        )

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 納品先マスターAPI ==========

@router.get("/destinations")
async def get_destinations():
    """納品先一覧取得"""
    try:
        db = await get_database()
        destinations = await db.get_all_destinations()
        return {"destinations": destinations}
    except Exception as e:
        logger.error(f"Error getting destinations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/destinations")
async def create_destination(data: dict):
    """納品先作成"""
    try:
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=400, detail="名前は必須です")

        display_order = data.get('display_order', 0)

        db = await get_database()
        destination_id = await db.create_destination(name, display_order)
        destination = await db.get_destination(destination_id)

        return {"destination": destination}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating destination: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/destinations/reorder")
async def reorder_destinations(data: dict):
    """納品先の並べ替え"""
    try:
        ordered_ids = data.get('ordered_ids')
        if not ordered_ids or not isinstance(ordered_ids, list):
            raise HTTPException(status_code=400, detail="ordered_ids は必須です")
        db = await get_database()
        await db.reorder_destinations(ordered_ids)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering destinations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/destinations/{destination_id}")
async def update_destination(destination_id: int, data: dict):
    """納品先更新"""
    try:
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=400, detail="名前は必須です")

        display_order = data.get('display_order')

        db = await get_database()
        await db.update_destination(destination_id, name, display_order)
        destination = await db.get_destination(destination_id)

        return {"destination": destination}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating destination: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/destinations/{destination_id}")
async def delete_destination(destination_id: int):
    """納品先削除"""
    try:
        db = await get_database()
        await db.delete_destination(destination_id)
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Error deleting destination: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 音声変換エンジンマスターAPI ==========

@router.get("/tts-engines")
async def get_tts_engines():
    """音声変換エンジン一覧取得"""
    try:
        db = await get_database()
        tts_engines = await db.get_all_tts_engines()
        return {"tts_engines": tts_engines}
    except Exception as e:
        logger.error(f"Error getting TTS engines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts-engines")
async def create_tts_engine(data: dict):
    """音声変換エンジン作成"""
    try:
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=400, detail="名前は必須です")

        display_order = data.get('display_order', 0)

        db = await get_database()
        tts_engine_id = await db.create_tts_engine(name, display_order)
        tts_engine = await db.get_tts_engine(tts_engine_id)

        return {"tts_engine": tts_engine}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating TTS engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tts-engines/reorder")
async def reorder_tts_engines(data: dict):
    """音声変換エンジンの並べ替え"""
    try:
        ordered_ids = data.get('ordered_ids')
        if not ordered_ids or not isinstance(ordered_ids, list):
            raise HTTPException(status_code=400, detail="ordered_ids は必須です")
        db = await get_database()
        await db.reorder_tts_engines(ordered_ids)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering TTS engines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tts-engines/{tts_engine_id}")
async def update_tts_engine(tts_engine_id: int, data: dict):
    """音声変換エンジン更新"""
    try:
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=400, detail="名前は必須です")

        display_order = data.get('display_order')

        db = await get_database()
        await db.update_tts_engine(tts_engine_id, name, display_order)
        tts_engine = await db.get_tts_engine(tts_engine_id)

        return {"tts_engine": tts_engine}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating TTS engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tts-engines/{tts_engine_id}")
async def delete_tts_engine(tts_engine_id: int):
    """音声変換エンジン削除"""
    try:
        db = await get_database()
        await db.delete_tts_engine(tts_engine_id)
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Error deleting TTS engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 公開状態マスターAPI ==========

@router.get("/publication-statuses")
async def get_publication_statuses():
    """公開状態一覧取得"""
    try:
        db = await get_database()
        publication_statuses = await db.get_all_publication_statuses()
        return {"publication_statuses": publication_statuses}
    except Exception as e:
        logger.error(f"Error getting publication statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/publication-statuses")
async def create_publication_status(data: dict):
    """公開状態作成"""
    try:
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=400, detail="名前は必須です")

        display_order = data.get('display_order', 0)

        db = await get_database()
        publication_status_id = await db.create_publication_status(name, display_order)
        publication_status = await db.get_publication_status(publication_status_id)

        return {"publication_status": publication_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating publication status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/publication-statuses/reorder")
async def reorder_publication_statuses(data: dict):
    """公開状態の並べ替え"""
    try:
        ordered_ids = data.get('ordered_ids')
        if not ordered_ids or not isinstance(ordered_ids, list):
            raise HTTPException(status_code=400, detail="ordered_ids は必須です")
        db = await get_database()
        await db.reorder_publication_statuses(ordered_ids)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering publication statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/publication-statuses/{publication_status_id}")
async def update_publication_status(publication_status_id: int, data: dict):
    """公開状態更新"""
    try:
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=400, detail="名前は必須です")

        display_order = data.get('display_order')

        db = await get_database()
        await db.update_publication_status(publication_status_id, name, display_order)
        publication_status = await db.get_publication_status(publication_status_id)

        return {"publication_status": publication_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating publication status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/publication-statuses/{publication_status_id}")
async def delete_publication_status(publication_status_id: int):
    """公開状態削除"""
    try:
        db = await get_database()
        await db.delete_publication_status(publication_status_id)
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Error deleting publication status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== チェック進捗マスターAPI ==========

@router.get("/check-statuses")
async def get_check_statuses():
    """チェック進捗一覧取得"""
    try:
        db = await get_database()
        check_statuses = await db.get_all_check_statuses()
        return {"check_statuses": check_statuses}
    except Exception as e:
        logger.error(f"Error getting check statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-statuses")
async def create_check_status(data: dict):
    """チェック進捗作成"""
    try:
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=400, detail="名前は必須です")

        display_order = data.get('display_order', 0)

        db = await get_database()
        check_status_id = await db.create_check_status(name, display_order)
        check_status = await db.get_check_status(check_status_id)

        return {"check_status": check_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating check status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/check-statuses/reorder")
async def reorder_check_statuses(data: dict):
    """チェック進捗の並べ替え"""
    try:
        ordered_ids = data.get('ordered_ids')
        if not ordered_ids or not isinstance(ordered_ids, list):
            raise HTTPException(status_code=400, detail="ordered_ids は必須です")
        db = await get_database()
        await db.reorder_check_statuses(ordered_ids)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering check statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/check-statuses/{check_status_id}")
async def update_check_status(check_status_id: int, data: dict):
    """チェック進捗更新"""
    try:
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=400, detail="名前は必須です")

        display_order = data.get('display_order')

        db = await get_database()
        await db.update_check_status(check_status_id, name, display_order)
        check_status = await db.get_check_status(check_status_id)

        return {"check_status": check_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating check status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/check-statuses/{check_status_id}")
async def delete_check_status(check_status_id: int):
    """チェック進捗削除"""
    try:
        db = await get_database()
        await db.delete_check_status(check_status_id)
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Error deleting check status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== プロジェクト設定API ==========

@router.put("/projects/{project_id}/settings")
async def update_project_settings(project_id: int, data: dict):
    """プロジェクト設定更新（納品先・音声変換エンジン・公開状態・チェック進捗・備考）"""
    try:
        db = await get_database()

        # プロジェクトの存在確認
        project = await db.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        destination_id = data.get('destination_id')
        tts_engine_id = data.get('tts_engine_id')
        publication_status_id = data.get('publication_status_id')
        check_status_id = data.get('check_status_id')
        notes = data.get('notes')

        await db.update_project_settings(
            project_id, destination_id, tts_engine_id,
            publication_status_id, check_status_id, notes
        )

        # 更新後のプロジェクトを取得
        updated_project = await db.get_project(project_id)

        return {"project": updated_project}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== RAG API ==========

@router.get("/projects/{project_id}/rag-status")
async def get_rag_status(project_id: int):
    """RAGインデックス状態取得"""
    try:
        db = await get_database()
        project = await db.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        rag_index = await db.get_rag_index(project_id)

        return {
            "project_id": project_id,
            "has_rag_chunks": bool(project.get('has_rag_chunks', 0)),
            "rag_index": rag_index
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting RAG status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/rag-build")
async def build_rag_index(
    project_id: int,
    background_tasks: BackgroundTasks
):
    """RAGインデックス構築開始（バックグラウンド）"""
    try:
        db = await get_database()
        project = await db.get_project(project_id)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if not project.get('has_rag_chunks', 0):
            raise HTTPException(status_code=400, detail="rag_chunks.json が見つかりません")

        # ステータスを更新
        await db.upsert_rag_index(project_id=project_id, status='indexing')

        # バックグラウンドで構築
        background_tasks.add_task(
            _run_rag_build,
            project_id,
            project['path']
        )

        return {
            "status": "accepted",
            "message": "RAGインデックス構築を開始しました"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting RAG build: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/rag-index")
async def delete_rag_index(project_id: int):
    """RAGインデックス削除"""
    try:
        db = await get_database()
        project = await db.get_project(project_id)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # DBからRAGインデックスを削除
        await db.delete_rag_index(project_id)

        # rag_index.json ファイルも削除
        index_path = Path(project['path']) / "rag_index.json"
        if index_path.exists():
            index_path.unlink()

        return {"status": "deleted", "message": "RAGインデックスを削除しました"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting RAG index: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_rag_build(project_id: int, project_path: str):
    """バックグラウンドRAGインデックス構築"""
    from .rag_service import get_rag_builder

    db = await get_database()
    ws = get_connection_manager()

    try:
        builder = get_rag_builder()

        async def progress_callback(current, total, message):
            await ws.broadcast(
                "rag_build_progress",
                {
                    "project_id": project_id,
                    "current": current,
                    "total": total,
                    "message": message
                }
            )

        result = await builder.build_index(project_path, progress_callback)

        if result["success"]:
            await db.upsert_rag_index(
                project_id=project_id,
                status='indexed',
                chunk_count=result["chunk_count"]
            )
            await ws.broadcast(
                "rag_build_progress",
                {
                    "project_id": project_id,
                    "current": result["chunk_count"],
                    "total": result["chunk_count"],
                    "message": "構築完了",
                    "completed": True
                }
            )
        else:
            await db.update_rag_index_status(
                project_id=project_id,
                status='failed',
                error_message=result["error"]
            )
            await ws.broadcast(
                "rag_build_progress",
                {
                    "project_id": project_id,
                    "error": result["error"],
                    "completed": True
                }
            )
    except Exception as e:
        logger.error(f"RAG build error: {e}")
        await db.update_rag_index_status(
            project_id=project_id,
            status='failed',
            error_message=str(e)
        )


# ========== ヘルスチェック ==========

@router.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
