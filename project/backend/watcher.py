"""
ファイルウォッチャー
パフォーマンス最適化: watchdog + asyncio、デバウンス処理
"""

import asyncio
from pathlib import Path
from typing import Callable, Optional, List, Set
from datetime import datetime
import threading
import logging

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)

# デバウンス設定
DEBOUNCE_MS = 100
SUPPORTED_EXTENSIONS = {'.html', '.txt', '.mp3'}


class DebounceBuffer:
    """デバウンスバッファ（連続イベント集約）"""

    def __init__(self, delay_ms: int = DEBOUNCE_MS):
        self.delay_seconds = delay_ms / 1000.0
        self._pending_paths: Set[str] = set()
        self._timer_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._callback: Optional[Callable] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_callback(self, callback: Callable, loop: asyncio.AbstractEventLoop) -> None:
        """コールバックとイベントループを設定"""
        self._callback = callback
        self._loop = loop

    async def add_event(self, path: str) -> None:
        """イベントを追加（デバウンス処理）"""
        async with self._lock:
            self._pending_paths.add(path)

            # 既存のタイマーをキャンセル
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
                try:
                    await self._timer_task
                except asyncio.CancelledError:
                    pass

            # 新しいタイマーを設定
            self._timer_task = asyncio.create_task(self._flush_after_delay())

    async def _flush_after_delay(self) -> None:
        """デバウンス待機後、イベントを処理"""
        await asyncio.sleep(self.delay_seconds)

        async with self._lock:
            if not self._pending_paths:
                return

            paths = list(self._pending_paths)
            self._pending_paths.clear()

        # コールバック実行
        if self._callback:
            try:
                await self._callback(paths)
            except Exception as e:
                logger.error(f"Debounce callback error: {e}")


class ContentEventHandler(FileSystemEventHandler):
    """コンテンツファイル変更ハンドラー"""

    def __init__(self, debounce_buffer: DebounceBuffer, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.debounce_buffer = debounce_buffer
        self.loop = loop

    def on_any_event(self, event: FileSystemEvent) -> None:
        """全イベントをハンドル"""
        if event.is_directory:
            return

        # サポートされる拡張子のみ処理
        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return

        # イベントタイプをフィルタ
        if event.event_type not in ('created', 'modified', 'deleted', 'moved'):
            return

        logger.debug(f"File event: {event.event_type} - {path}")

        # asyncioイベントループにタスクを追加
        asyncio.run_coroutine_threadsafe(
            self.debounce_buffer.add_event(str(path)),
            self.loop
        )


class ContentWatcher:
    """コンテンツフォルダ監視クラス"""

    def __init__(
        self,
        path: Path,
        on_change_callback: Callable[[List[str]], None],
        debounce_ms: int = DEBOUNCE_MS
    ):
        self.path = path
        self.on_change_callback = on_change_callback
        self.debounce_ms = debounce_ms

        self._observer: Optional[Observer] = None
        self._debounce_buffer: Optional[DebounceBuffer] = None
        self._running = False

    async def start(self) -> None:
        """監視を開始"""
        if self._running:
            logger.warning("Watcher already running")
            return

        if not self.path.exists():
            logger.error(f"Watch path does not exist: {self.path}")
            return

        # デバウンスバッファ初期化
        self._debounce_buffer = DebounceBuffer(self.debounce_ms)
        self._debounce_buffer.set_callback(
            self._process_changes,
            asyncio.get_event_loop()
        )

        # watchdog Observer初期化
        self._observer = Observer()
        handler = ContentEventHandler(
            self._debounce_buffer,
            asyncio.get_event_loop()
        )

        # 全サブフォルダを監視
        self._observer.schedule(handler, str(self.path), recursive=True)
        self._observer.start()

        self._running = True
        logger.info(f"Started watching: {self.path}")

    async def stop(self) -> None:
        """監視を停止"""
        if not self._running:
            return

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        self._running = False
        logger.info(f"Stopped watching: {self.path}")

    async def _process_changes(self, paths: List[str]) -> None:
        """変更されたパスを処理"""
        if not paths:
            return

        logger.info(f"Processing {len(paths)} file changes")

        try:
            await self.on_change_callback(paths)
        except Exception as e:
            logger.error(f"Error processing file changes: {e}")

    @property
    def is_running(self) -> bool:
        """監視中かどうか"""
        return self._running


class MultiProjectWatcher:
    """複数プロジェクト監視マネージャー"""

    def __init__(
        self,
        base_path: Path,
        on_change_callback: Callable[[str, List[str]], None],
        debounce_ms: int = DEBOUNCE_MS
    ):
        self.base_path = base_path
        self.on_change_callback = on_change_callback
        self.debounce_ms = debounce_ms

        self._watcher: Optional[ContentWatcher] = None

    async def start(self) -> None:
        """全プロジェクトの監視を開始"""
        async def handle_changes(paths: List[str]) -> None:
            # パスからプロジェクト名を特定
            project_changes: dict = {}

            for path in paths:
                # パスからプロジェクト名を抽出
                try:
                    rel_path = Path(path).relative_to(self.base_path)
                    project_name = rel_path.parts[0]

                    if project_name not in project_changes:
                        project_changes[project_name] = []
                    project_changes[project_name].append(path)
                except ValueError:
                    logger.warning(f"Path outside base: {path}")

            # プロジェクトごとにコールバック
            for project_name, project_paths in project_changes.items():
                await self.on_change_callback(project_name, project_paths)

        self._watcher = ContentWatcher(
            self.base_path,
            handle_changes,
            self.debounce_ms
        )
        await self._watcher.start()

    async def stop(self) -> None:
        """監視を停止"""
        if self._watcher:
            await self._watcher.stop()
            self._watcher = None

    @property
    def is_running(self) -> bool:
        """監視中かどうか"""
        return self._watcher is not None and self._watcher.is_running
