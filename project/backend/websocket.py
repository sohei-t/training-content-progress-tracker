"""
WebSocket接続管理
パフォーマンス最適化: 接続プール、再接続ロジック、msgpack圧縮対応
"""

import asyncio
import json
from typing import Set, Dict, Any, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket接続プール管理クラス"""

    def __init__(self, max_connections: int = 50):
        self.max_connections = max_connections
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._client_info: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket) -> bool:
        """新しい接続を受け入れ"""
        async with self._lock:
            # 接続数制限チェック
            if len(self.active_connections) >= self.max_connections:
                logger.warning(f"Max connections reached: {self.max_connections}")
                await websocket.close(code=1013, reason="Max connections reached")
                return False

            await websocket.accept()
            self.active_connections.add(websocket)

            # クライアント情報を記録
            self._client_info[websocket] = {
                'connected_at': datetime.now().isoformat(),
                'last_ping': datetime.now().isoformat(),
                'message_count': 0
            }

            logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
            return True

    async def disconnect(self, websocket: WebSocket) -> None:
        """接続を切断"""
        async with self._lock:
            self.active_connections.discard(websocket)
            self._client_info.pop(websocket, None)
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, event: str, data: Dict[str, Any]) -> int:
        """全クライアントに送信"""
        message = {
            "event": event,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        message_json = json.dumps(message, ensure_ascii=False)

        disconnected: Set[WebSocket] = set()
        sent_count = 0

        # コピーを作成して反復
        connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_text(message_json)
                sent_count += 1

                # メッセージカウント更新
                if connection in self._client_info:
                    self._client_info[connection]['message_count'] += 1

            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.add(connection)

        # 切断された接続を削除
        if disconnected:
            async with self._lock:
                self.active_connections -= disconnected
                for conn in disconnected:
                    self._client_info.pop(conn, None)

        logger.debug(f"Broadcast '{event}' to {sent_count} clients")
        return sent_count

    async def send_personal(
        self,
        websocket: WebSocket,
        event: str,
        data: Dict[str, Any]
    ) -> bool:
        """特定クライアントに送信"""
        if websocket not in self.active_connections:
            return False

        message = {
            "event": event,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))

            if websocket in self._client_info:
                self._client_info[websocket]['message_count'] += 1

            return True

        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            await self.disconnect(websocket)
            return False

    async def broadcast_project_update(self, project_data: Dict[str, Any]) -> int:
        """プロジェクト更新をブロードキャスト"""
        return await self.broadcast("project_updated", {"project": project_data})

    async def broadcast_topic_change(
        self,
        project_id: int,
        topic_data: Dict[str, Any]
    ) -> int:
        """トピック変更をブロードキャスト"""
        return await self.broadcast(
            "topic_changed",
            {"project_id": project_id, "topic": topic_data}
        )

    async def broadcast_scan_started(
        self,
        scan_id: str,
        project_id: Optional[int] = None,
        scan_type: str = "full"
    ) -> int:
        """スキャン開始をブロードキャスト"""
        return await self.broadcast(
            "scan_started",
            {
                "scan_id": scan_id,
                "project_id": project_id,
                "type": scan_type
            }
        )

    async def broadcast_scan_progress(
        self,
        scan_id: str,
        progress: float,
        current: str
    ) -> int:
        """スキャン進捗をブロードキャスト"""
        return await self.broadcast(
            "scan_progress",
            {
                "scan_id": scan_id,
                "progress": progress,
                "current": current
            }
        )

    async def broadcast_scan_completed(
        self,
        scan_id: str,
        result: Dict[str, Any]
    ) -> int:
        """スキャン完了をブロードキャスト"""
        return await self.broadcast(
            "scan_completed",
            {"scan_id": scan_id, "result": result}
        )

    def get_connection_count(self) -> int:
        """接続数を取得"""
        return len(self.active_connections)

    def get_connection_stats(self) -> Dict[str, Any]:
        """接続統計を取得"""
        return {
            "total_connections": len(self.active_connections),
            "max_connections": self.max_connections,
            "clients": [
                {
                    "connected_at": info['connected_at'],
                    "message_count": info['message_count']
                }
                for info in self._client_info.values()
            ]
        }


# シングルトンインスタンス
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """ConnectionManagerインスタンスを取得"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
