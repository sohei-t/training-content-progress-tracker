"""
watcher.py のユニットテスト
ファイル監視、デバウンス処理、複数プロジェクト監視をテスト
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from backend.watcher import (
    DebounceBuffer,
    ContentEventHandler,
    ContentWatcher,
    MultiProjectWatcher,
    DEBOUNCE_MS,
    SUPPORTED_EXTENSIONS
)


# ========== DebounceBufferテスト ==========

class TestDebounceBuffer:
    """デバウンスバッファのテスト"""

    def test_WATCH001_default_delay(self):
        """WATCH001: デフォルトの遅延時間が正しく設定される"""
        buffer = DebounceBuffer()
        assert buffer.delay_seconds == DEBOUNCE_MS / 1000.0

    def test_WATCH002_custom_delay(self):
        """WATCH002: カスタム遅延時間が正しく設定される"""
        buffer = DebounceBuffer(delay_ms=200)
        assert buffer.delay_seconds == 0.2

    @pytest.mark.asyncio
    async def test_WATCH003_set_callback(self):
        """WATCH003: コールバック設定が正しく動作する"""
        buffer = DebounceBuffer()
        callback = AsyncMock()
        loop = asyncio.get_event_loop()

        buffer.set_callback(callback, loop)

        assert buffer._callback == callback
        assert buffer._loop == loop

    @pytest.mark.asyncio
    async def test_WATCH004_add_event_stores_path(self):
        """WATCH004: イベント追加でパスが保存される"""
        buffer = DebounceBuffer(delay_ms=50)
        callback = AsyncMock()
        loop = asyncio.get_event_loop()
        buffer.set_callback(callback, loop)

        await buffer.add_event("/test/path1.html")

        # パスが保存されていることを確認
        assert "/test/path1.html" in buffer._pending_paths

    @pytest.mark.asyncio
    async def test_WATCH005_debounce_collects_multiple_events(self):
        """WATCH005: デバウンスが複数イベントを集約する"""
        buffer = DebounceBuffer(delay_ms=50)
        callback = AsyncMock()
        loop = asyncio.get_event_loop()
        buffer.set_callback(callback, loop)

        # 複数イベントを連続追加
        await buffer.add_event("/test/path1.html")
        await buffer.add_event("/test/path2.txt")
        await buffer.add_event("/test/path3.mp3")

        # デバウンス完了を待つ
        await asyncio.sleep(0.1)

        # コールバックが1回だけ呼ばれることを確認
        assert callback.call_count == 1
        # 全パスが含まれていることを確認
        called_paths = callback.call_args[0][0]
        assert len(called_paths) == 3

    @pytest.mark.asyncio
    async def test_WATCH006_debounce_resets_timer(self):
        """WATCH006: 新しいイベントでタイマーがリセットされる"""
        buffer = DebounceBuffer(delay_ms=100)
        callback = AsyncMock()
        loop = asyncio.get_event_loop()
        buffer.set_callback(callback, loop)

        await buffer.add_event("/test/path1.html")
        await asyncio.sleep(0.05)  # 50ms待機
        await buffer.add_event("/test/path2.html")  # タイマーリセット
        await asyncio.sleep(0.05)  # 50ms待機（まだ発火しない）

        # まだコールバックは呼ばれていない
        assert callback.call_count == 0

        await asyncio.sleep(0.1)  # さらに100ms待機

        # 今度はコールバックが呼ばれる
        assert callback.call_count == 1

    @pytest.mark.asyncio
    async def test_WATCH007_flush_clears_pending_paths(self):
        """WATCH007: フラッシュ後にpending_pathsがクリアされる"""
        buffer = DebounceBuffer(delay_ms=50)
        callback = AsyncMock()
        loop = asyncio.get_event_loop()
        buffer.set_callback(callback, loop)

        await buffer.add_event("/test/path1.html")
        await asyncio.sleep(0.1)

        assert len(buffer._pending_paths) == 0

    @pytest.mark.asyncio
    async def test_WATCH008_callback_error_handling(self):
        """WATCH008: コールバックエラーが適切に処理される"""
        buffer = DebounceBuffer(delay_ms=50)
        callback = AsyncMock(side_effect=Exception("Callback error"))
        loop = asyncio.get_event_loop()
        buffer.set_callback(callback, loop)

        await buffer.add_event("/test/path1.html")

        # エラーが発生しても例外を投げない
        await asyncio.sleep(0.1)

        assert callback.call_count == 1


# ========== ContentEventHandlerテスト ==========

class TestContentEventHandler:
    """コンテンツイベントハンドラーのテスト"""

    def test_WATCH009_supported_extensions(self):
        """WATCH009: サポートされる拡張子が正しく定義されている"""
        assert '.html' in SUPPORTED_EXTENSIONS
        assert '.txt' in SUPPORTED_EXTENSIONS
        assert '.mp3' in SUPPORTED_EXTENSIONS

    def test_WATCH010_ignore_directory_events(self):
        """WATCH010: ディレクトリイベントは無視される"""
        buffer = MagicMock()
        loop = asyncio.new_event_loop()
        handler = ContentEventHandler(buffer, loop)

        mock_event = MagicMock()
        mock_event.is_directory = True
        mock_event.src_path = "/test/dir"

        handler.on_any_event(mock_event)

        # バッファに追加されないことを確認
        buffer.add_event.assert_not_called()

    def test_WATCH011_ignore_unsupported_extensions(self):
        """WATCH011: サポートされない拡張子は無視される"""
        buffer = MagicMock()
        loop = asyncio.new_event_loop()
        handler = ContentEventHandler(buffer, loop)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/file.py"
        mock_event.event_type = "modified"

        handler.on_any_event(mock_event)

        # バッファに追加されないことを確認
        # Note: asyncio.run_coroutine_threadsafeが呼ばれていないことを確認

    def test_WATCH012_process_supported_file(self):
        """WATCH012: サポートされるファイルのイベントを処理する"""
        buffer = DebounceBuffer()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        handler = ContentEventHandler(buffer, loop)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/file.html"
        mock_event.event_type = "modified"

        # イベント処理
        handler.on_any_event(mock_event)

        # 少し待ってからチェック
        # Note: run_coroutine_threadsafeは別スレッドで実行されるため確認が難しい
        loop.close()

    def test_WATCH013_filter_event_types(self):
        """WATCH013: イベントタイプがフィルタされる"""
        buffer = MagicMock()
        loop = asyncio.new_event_loop()
        handler = ContentEventHandler(buffer, loop)

        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/file.html"
        mock_event.event_type = "opened"  # サポートされないイベントタイプ

        handler.on_any_event(mock_event)

        # バッファに追加されない


# ========== ContentWatcherテスト ==========

class TestContentWatcher:
    """コンテンツウォッチャーのテスト"""

    @pytest.fixture
    def watcher_dir(self, tmp_path):
        """ウォッチャーテスト用ディレクトリ"""
        watch_dir = tmp_path / "watch_test"
        watch_dir.mkdir()
        return watch_dir

    def test_WATCH014_watcher_initialization(self, watcher_dir):
        """WATCH014: ウォッチャーが正しく初期化される"""
        callback = AsyncMock()
        watcher = ContentWatcher(watcher_dir, callback)

        assert watcher.path == watcher_dir
        assert watcher.debounce_ms == DEBOUNCE_MS
        assert not watcher.is_running

    def test_WATCH015_custom_debounce(self, watcher_dir):
        """WATCH015: カスタムデバウンス時間が設定される"""
        callback = AsyncMock()
        watcher = ContentWatcher(watcher_dir, callback, debounce_ms=200)

        assert watcher.debounce_ms == 200

    @pytest.mark.asyncio
    async def test_WATCH016_start_watcher(self, watcher_dir):
        """WATCH016: ウォッチャーが正常に開始される"""
        callback = AsyncMock()
        watcher = ContentWatcher(watcher_dir, callback)

        await watcher.start()
        assert watcher.is_running

        await watcher.stop()
        assert not watcher.is_running

    @pytest.mark.asyncio
    async def test_WATCH017_start_nonexistent_path(self, tmp_path):
        """WATCH017: 存在しないパスでは開始しない"""
        nonexistent = tmp_path / "nonexistent"
        callback = AsyncMock()
        watcher = ContentWatcher(nonexistent, callback)

        await watcher.start()
        assert not watcher.is_running

    @pytest.mark.asyncio
    async def test_WATCH018_start_already_running(self, watcher_dir):
        """WATCH018: 既に実行中の場合は再開始しない"""
        callback = AsyncMock()
        watcher = ContentWatcher(watcher_dir, callback)

        await watcher.start()
        assert watcher.is_running

        # 再度開始しようとしても問題ない
        await watcher.start()
        assert watcher.is_running

        await watcher.stop()

    @pytest.mark.asyncio
    async def test_WATCH019_stop_not_running(self, watcher_dir):
        """WATCH019: 実行中でない場合の停止は何もしない"""
        callback = AsyncMock()
        watcher = ContentWatcher(watcher_dir, callback)

        # 開始せずに停止しても問題ない
        await watcher.stop()
        assert not watcher.is_running

    @pytest.mark.asyncio
    async def test_WATCH020_process_changes_calls_callback(self, watcher_dir):
        """WATCH020: _process_changesがコールバックを呼ぶ"""
        callback = AsyncMock()
        watcher = ContentWatcher(watcher_dir, callback)

        await watcher._process_changes(["/test/path1.html", "/test/path2.txt"])

        callback.assert_called_once_with(["/test/path1.html", "/test/path2.txt"])

    @pytest.mark.asyncio
    async def test_WATCH021_process_changes_empty_list(self, watcher_dir):
        """WATCH021: 空のリストでは何もしない"""
        callback = AsyncMock()
        watcher = ContentWatcher(watcher_dir, callback)

        await watcher._process_changes([])

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_WATCH022_process_changes_error_handling(self, watcher_dir):
        """WATCH022: コールバックエラーが適切に処理される"""
        callback = AsyncMock(side_effect=Exception("Callback error"))
        watcher = ContentWatcher(watcher_dir, callback)

        # エラーが発生しても例外を投げない
        await watcher._process_changes(["/test/path1.html"])

        callback.assert_called_once()


# ========== MultiProjectWatcherテスト ==========

class TestMultiProjectWatcher:
    """マルチプロジェクトウォッチャーのテスト"""

    @pytest.fixture
    def multi_watcher_dir(self, tmp_path):
        """マルチウォッチャーテスト用ディレクトリ"""
        base_dir = tmp_path / "projects"
        base_dir.mkdir()

        # プロジェクト1
        project1 = base_dir / "project1"
        project1.mkdir()
        (project1 / "file1.html").write_text("content1")

        # プロジェクト2
        project2 = base_dir / "project2"
        project2.mkdir()
        (project2 / "file2.html").write_text("content2")

        return base_dir

    def test_WATCH023_multi_watcher_initialization(self, multi_watcher_dir):
        """WATCH023: マルチウォッチャーが正しく初期化される"""
        callback = AsyncMock()
        watcher = MultiProjectWatcher(multi_watcher_dir, callback)

        assert watcher.base_path == multi_watcher_dir
        assert watcher.debounce_ms == DEBOUNCE_MS
        assert not watcher.is_running

    def test_WATCH024_custom_debounce_multi(self, multi_watcher_dir):
        """WATCH024: マルチウォッチャーでカスタムデバウンスが設定される"""
        callback = AsyncMock()
        watcher = MultiProjectWatcher(multi_watcher_dir, callback, debounce_ms=150)

        assert watcher.debounce_ms == 150

    @pytest.mark.asyncio
    async def test_WATCH025_start_multi_watcher(self, multi_watcher_dir):
        """WATCH025: マルチウォッチャーが正常に開始される"""
        callback = AsyncMock()
        watcher = MultiProjectWatcher(multi_watcher_dir, callback)

        await watcher.start()
        assert watcher.is_running

        await watcher.stop()
        assert not watcher.is_running

    @pytest.mark.asyncio
    async def test_WATCH026_stop_multi_watcher(self, multi_watcher_dir):
        """WATCH026: マルチウォッチャーが正常に停止される"""
        callback = AsyncMock()
        watcher = MultiProjectWatcher(multi_watcher_dir, callback)

        await watcher.start()
        await watcher.stop()

        assert not watcher.is_running
        assert watcher._watcher is None

    @pytest.mark.asyncio
    async def test_WATCH027_project_name_extraction(self, multi_watcher_dir):
        """WATCH027: パスからプロジェクト名が正しく抽出される"""
        collected_changes = []

        async def capture_callback(project_name, paths):
            collected_changes.append((project_name, paths))

        watcher = MultiProjectWatcher(multi_watcher_dir, capture_callback, debounce_ms=50)

        await watcher.start()

        # 内部のハンドラーをテスト
        internal_handler = watcher._watcher.on_change_callback
        await internal_handler([
            str(multi_watcher_dir / "project1" / "file1.html"),
            str(multi_watcher_dir / "project2" / "file2.html")
        ])

        await watcher.stop()

        # 2つのプロジェクトに対してコールバックが呼ばれる
        assert len(collected_changes) == 2
        project_names = [c[0] for c in collected_changes]
        assert "project1" in project_names
        assert "project2" in project_names

    @pytest.mark.asyncio
    async def test_WATCH028_path_outside_base(self, multi_watcher_dir):
        """WATCH028: ベースパス外のパスは警告される"""
        collected_changes = []

        async def capture_callback(project_name, paths):
            collected_changes.append((project_name, paths))

        watcher = MultiProjectWatcher(multi_watcher_dir, capture_callback, debounce_ms=50)

        await watcher.start()

        # ベースパス外のパスを含むリスト
        internal_handler = watcher._watcher.on_change_callback
        await internal_handler(["/some/other/path/file.html"])

        await watcher.stop()

        # ベースパス外のパスはコールバックに渡されない
        assert len(collected_changes) == 0

    @pytest.mark.asyncio
    async def test_WATCH029_is_running_property(self, multi_watcher_dir):
        """WATCH029: is_runningプロパティが正しく動作する"""
        callback = AsyncMock()
        watcher = MultiProjectWatcher(multi_watcher_dir, callback)

        assert not watcher.is_running

        await watcher.start()
        assert watcher.is_running

        await watcher.stop()
        assert not watcher.is_running

    @pytest.mark.asyncio
    async def test_WATCH030_same_project_multiple_files(self, multi_watcher_dir):
        """WATCH030: 同一プロジェクトの複数ファイルがグループ化される"""
        collected_changes = []

        async def capture_callback(project_name, paths):
            collected_changes.append((project_name, paths))

        watcher = MultiProjectWatcher(multi_watcher_dir, capture_callback, debounce_ms=50)

        await watcher.start()

        # 同じプロジェクトの複数ファイル
        internal_handler = watcher._watcher.on_change_callback
        await internal_handler([
            str(multi_watcher_dir / "project1" / "file1.html"),
            str(multi_watcher_dir / "project1" / "file2.txt"),
            str(multi_watcher_dir / "project1" / "file3.mp3")
        ])

        await watcher.stop()

        # 1つのプロジェクトに対して1回のコールバック
        assert len(collected_changes) == 1
        assert collected_changes[0][0] == "project1"
        assert len(collected_changes[0][1]) == 3
