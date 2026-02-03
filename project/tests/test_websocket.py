"""
WebSocketテスト
テスト対象: backend/websocket.py
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket

from backend.websocket import ConnectionManager, get_connection_manager


@pytest.fixture
def manager():
    """ConnectionManager フィクスチャ"""
    return ConnectionManager(max_connections=5)


@pytest.fixture
def mock_websocket():
    """モックWebSocket"""
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_websockets(count=3):
    """複数のモックWebSocket"""
    return [
        AsyncMock(
            spec=WebSocket,
            accept=AsyncMock(),
            send_text=AsyncMock(),
            close=AsyncMock()
        )
        for _ in range(count)
    ]


class TestConnectionManagement:
    """接続管理テスト"""

    @pytest.mark.asyncio
    async def test_WS001_connect(self, manager, mock_websocket):
        """WS-001: 接続確立"""
        result = await manager.connect(mock_websocket)

        assert result is True
        assert mock_websocket in manager.active_connections
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_WS002_disconnect(self, manager, mock_websocket):
        """WS-002: 切断処理"""
        await manager.connect(mock_websocket)
        await manager.disconnect(mock_websocket)

        assert mock_websocket not in manager.active_connections
        assert mock_websocket not in manager._client_info

    @pytest.mark.asyncio
    async def test_WS006_max_connections(self, manager):
        """WS-006: 接続数制限"""
        # 5つの接続を作成
        websockets = []
        for _ in range(5):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.close = AsyncMock()
            websockets.append(ws)
            await manager.connect(ws)

        assert len(manager.active_connections) == 5

        # 6つ目の接続は拒否される
        ws_overflow = AsyncMock(spec=WebSocket)
        ws_overflow.accept = AsyncMock()
        ws_overflow.close = AsyncMock()

        result = await manager.connect(ws_overflow)

        assert result is False
        ws_overflow.close.assert_called_once()
        assert len(manager.active_connections) == 5

    @pytest.mark.asyncio
    async def test_get_connection_count(self, manager, mock_websocket):
        """接続数の取得"""
        assert manager.get_connection_count() == 0

        await manager.connect(mock_websocket)
        assert manager.get_connection_count() == 1

        await manager.disconnect(mock_websocket)
        assert manager.get_connection_count() == 0


class TestBroadcast:
    """ブロードキャストテスト"""

    @pytest.mark.asyncio
    async def test_WS003_broadcast(self, manager):
        """WS-003: ブロードキャスト"""
        websockets = []
        for _ in range(3):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            websockets.append(ws)
            await manager.connect(ws)

        sent_count = await manager.broadcast("test_event", {"message": "Hello"})

        assert sent_count == 3
        for ws in websockets:
            ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_empty(self, manager):
        """接続なしのブロードキャスト"""
        sent_count = await manager.broadcast("test_event", {"message": "Hello"})
        assert sent_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected(self, manager):
        """切断されたクライアントの自動削除"""
        ws_ok = AsyncMock(spec=WebSocket)
        ws_ok.accept = AsyncMock()
        ws_ok.send_text = AsyncMock()

        ws_fail = AsyncMock(spec=WebSocket)
        ws_fail.accept = AsyncMock()
        ws_fail.send_text = AsyncMock(side_effect=Exception("Connection closed"))

        await manager.connect(ws_ok)
        await manager.connect(ws_fail)

        assert len(manager.active_connections) == 2

        await manager.broadcast("test_event", {"message": "Hello"})

        # 失敗したクライアントは削除される
        assert len(manager.active_connections) == 1
        assert ws_ok in manager.active_connections
        assert ws_fail not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_message_format(self, manager, mock_websocket):
        """ブロードキャストメッセージ形式"""
        await manager.connect(mock_websocket)

        await manager.broadcast("test_event", {"key": "value"})

        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message["event"] == "test_event"
        assert message["data"] == {"key": "value"}
        assert "timestamp" in message


class TestPersonalMessage:
    """個別メッセージテスト"""

    @pytest.mark.asyncio
    async def test_WS004_send_personal(self, manager, mock_websocket):
        """WS-004: 個別送信"""
        await manager.connect(mock_websocket)

        result = await manager.send_personal(
            mock_websocket,
            "personal_event",
            {"message": "Hello"}
        )

        assert result is True
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_personal_to_disconnected(self, manager, mock_websocket):
        """切断済みクライアントへの送信"""
        result = await manager.send_personal(
            mock_websocket,
            "personal_event",
            {"message": "Hello"}
        )

        assert result is False
        mock_websocket.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_personal_with_error(self, manager, mock_websocket):
        """送信エラー時の処理"""
        mock_websocket.send_text = AsyncMock(side_effect=Exception("Send failed"))
        await manager.connect(mock_websocket)

        result = await manager.send_personal(
            mock_websocket,
            "personal_event",
            {"message": "Hello"}
        )

        assert result is False
        # エラー時は自動切断
        assert mock_websocket not in manager.active_connections


class TestSpecializedBroadcast:
    """特化ブロードキャストテスト"""

    @pytest.mark.asyncio
    async def test_broadcast_project_update(self, manager, mock_websocket):
        """プロジェクト更新ブロードキャスト"""
        await manager.connect(mock_websocket)

        project_data = {"id": 1, "name": "Test Project", "progress": 50}
        sent_count = await manager.broadcast_project_update(project_data)

        assert sent_count == 1

        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message["event"] == "project_updated"
        assert message["data"]["project"] == project_data

    @pytest.mark.asyncio
    async def test_broadcast_topic_change(self, manager, mock_websocket):
        """トピック変更ブロードキャスト"""
        await manager.connect(mock_websocket)

        topic_data = {"id": 1, "base_name": "01-01_test"}
        sent_count = await manager.broadcast_topic_change(1, topic_data)

        assert sent_count == 1

        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message["event"] == "topic_changed"
        assert message["data"]["project_id"] == 1
        assert message["data"]["topic"] == topic_data

    @pytest.mark.asyncio
    async def test_broadcast_scan_started(self, manager, mock_websocket):
        """スキャン開始ブロードキャスト"""
        await manager.connect(mock_websocket)

        sent_count = await manager.broadcast_scan_started("scan_123", 1, "full")

        assert sent_count == 1

        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message["event"] == "scan_started"
        assert message["data"]["scan_id"] == "scan_123"
        assert message["data"]["project_id"] == 1
        assert message["data"]["type"] == "full"

    @pytest.mark.asyncio
    async def test_broadcast_scan_progress(self, manager, mock_websocket):
        """スキャン進捗ブロードキャスト"""
        await manager.connect(mock_websocket)

        sent_count = await manager.broadcast_scan_progress("scan_123", 50.0, "Project A")

        assert sent_count == 1

        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message["event"] == "scan_progress"
        assert message["data"]["scan_id"] == "scan_123"
        assert message["data"]["progress"] == 50.0
        assert message["data"]["current"] == "Project A"

    @pytest.mark.asyncio
    async def test_broadcast_scan_completed(self, manager, mock_websocket):
        """スキャン完了ブロードキャスト"""
        await manager.connect(mock_websocket)

        result = {
            "projects_scanned": 5,
            "files_scanned": 100,
            "changes_detected": 10
        }
        sent_count = await manager.broadcast_scan_completed("scan_123", result)

        assert sent_count == 1

        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message["event"] == "scan_completed"
        assert message["data"]["scan_id"] == "scan_123"
        assert message["data"]["result"] == result


class TestConnectionStats:
    """接続統計テスト"""

    @pytest.mark.asyncio
    async def test_get_connection_stats(self, manager, mock_websocket):
        """接続統計の取得"""
        await manager.connect(mock_websocket)

        stats = manager.get_connection_stats()

        assert stats["total_connections"] == 1
        assert stats["max_connections"] == 5
        assert len(stats["clients"]) == 1
        assert "connected_at" in stats["clients"][0]
        assert "message_count" in stats["clients"][0]

    @pytest.mark.asyncio
    async def test_message_count_tracking(self, manager, mock_websocket):
        """メッセージカウントの追跡"""
        await manager.connect(mock_websocket)

        # 3回ブロードキャスト
        await manager.broadcast("event1", {})
        await manager.broadcast("event2", {})
        await manager.broadcast("event3", {})

        stats = manager.get_connection_stats()
        assert stats["clients"][0]["message_count"] == 3


class TestSingleton:
    """シングルトンテスト"""

    def test_get_connection_manager(self):
        """シングルトン取得"""
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()

        assert manager1 is manager2


class TestWS005InvalidMessage:
    """不正メッセージテスト"""

    @pytest.mark.asyncio
    async def test_WS005_broadcast_with_special_characters(self, manager, mock_websocket):
        """特殊文字を含むメッセージのブロードキャスト"""
        await manager.connect(mock_websocket)

        data = {
            "message": "日本語テスト",
            "special": "特殊文字: <>\"'&",
            "unicode": "絵文字: 🎉🚀"
        }

        sent_count = await manager.broadcast("test_event", data)

        assert sent_count == 1
        # 正しくJSONエンコードされていることを確認
        call_args = mock_websocket.send_text.call_args[0][0]
        decoded = json.loads(call_args)
        assert decoded["data"]["message"] == "日本語テスト"
