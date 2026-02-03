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

            # ステータス計算
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


# ========== ヘルスチェック ==========

@router.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
