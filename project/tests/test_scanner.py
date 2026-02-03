"""
スキャナーテスト
テスト対象: backend/scanner.py
"""

import pytest
import asyncio
import time
from pathlib import Path

from backend.scanner import AsyncScanner, HashCache, FileInfo, ScanResult
from backend.wbs_parser import ParsedTopic, clear_wbs_cache


class TestHashCache:
    """ハッシュキャッシュテスト"""

    def test_set_and_get(self):
        """キャッシュへの保存と取得"""
        cache = HashCache()
        cache.set("/test/path", "abc123")

        result = cache.get("/test/path")
        assert result == "abc123"

    def test_get_nonexistent(self):
        """存在しないキーの取得"""
        cache = HashCache()
        result = cache.get("/nonexistent")
        assert result is None

    def test_is_changed_new_file(self):
        """新規ファイルの変更検出"""
        cache = HashCache()
        assert cache.is_changed("/new/path", "hash123") is True

    def test_is_changed_same_hash(self):
        """同一ハッシュの変更検出"""
        cache = HashCache()
        cache.set("/test/path", "hash123")
        assert cache.is_changed("/test/path", "hash123") is False

    def test_is_changed_different_hash(self):
        """異なるハッシュの変更検出"""
        cache = HashCache()
        cache.set("/test/path", "hash123")
        assert cache.is_changed("/test/path", "hash456") is True

    def test_clear(self):
        """キャッシュのクリア"""
        cache = HashCache()
        cache.set("/test/path", "hash123")
        cache.clear()
        assert cache.get("/test/path") is None

    def test_lru_eviction(self):
        """LRU削除（キャッシュサイズ制限）"""
        cache = HashCache(max_size=3)

        cache.set("/path1", "hash1")
        cache.set("/path2", "hash2")
        cache.set("/path3", "hash3")

        # 4つ目を追加すると最古のものが削除される
        cache.set("/path4", "hash4")

        # path1が削除されているはず
        assert cache.get("/path1") is None
        assert cache.get("/path2") == "hash2"
        assert cache.get("/path3") == "hash3"
        assert cache.get("/path4") == "hash4"


class TestFileDetection:
    """ファイル検出テスト"""

    @pytest.mark.asyncio
    async def test_SCN001_html_detection(self, db, content_dir):
        """SCN-001: HTML検出"""
        (content_dir / "01-01_APIの基礎.html").write_text("<html></html>")

        scanner = AsyncScanner(db, content_dir.parent)

        topic = ParsedTopic(
            topic_id="01-01",
            chapter="Chapter 1",
            title="APIの基礎",
            base_name="01-01_APIの基礎"
        )

        result = await scanner._scan_topic_files(1, topic, content_dir)

        assert result['has_html'] is True
        assert result['has_txt'] is False
        assert result['has_mp3'] is False

    @pytest.mark.asyncio
    async def test_SCN002_txt_detection(self, db, content_dir):
        """SCN-002: TXT検出"""
        (content_dir / "01-01_APIの基礎.txt").write_text("text content")

        scanner = AsyncScanner(db, content_dir.parent)

        topic = ParsedTopic(
            topic_id="01-01",
            chapter="Chapter 1",
            title="APIの基礎",
            base_name="01-01_APIの基礎"
        )

        result = await scanner._scan_topic_files(1, topic, content_dir)

        assert result['has_html'] is False
        assert result['has_txt'] is True
        assert result['has_mp3'] is False

    @pytest.mark.asyncio
    async def test_SCN003_mp3_detection(self, db, content_dir):
        """SCN-003: MP3検出"""
        (content_dir / "01-01_APIの基礎.mp3").write_bytes(b'\x00\x01\x02')

        scanner = AsyncScanner(db, content_dir.parent)

        topic = ParsedTopic(
            topic_id="01-01",
            chapter="Chapter 1",
            title="APIの基礎",
            base_name="01-01_APIの基礎"
        )

        result = await scanner._scan_topic_files(1, topic, content_dir)

        assert result['has_html'] is False
        assert result['has_txt'] is False
        assert result['has_mp3'] is True

    @pytest.mark.asyncio
    async def test_SCN004_no_files_detection(self, db, content_dir):
        """SCN-004: ファイル不在検出"""
        scanner = AsyncScanner(db, content_dir.parent)

        topic = ParsedTopic(
            topic_id="01-01",
            chapter="Chapter 1",
            title="存在しないトピック",
            base_name="01-01_存在しないトピック"
        )

        result = await scanner._scan_topic_files(1, topic, content_dir)

        assert result['has_html'] is False
        assert result['has_txt'] is False
        assert result['has_mp3'] is False

    @pytest.mark.asyncio
    async def test_SCN005_prefix_matching(self, db, content_dir):
        """SCN-005: プレフィックス一致"""
        # 異なるタイトル名でも同じプレフィックスなら検出される
        (content_dir / "01-01_別のタイトル.html").write_text("<html></html>")

        scanner = AsyncScanner(db, content_dir.parent)

        topic = ParsedTopic(
            topic_id="01-01",
            chapter="Chapter 1",
            title="APIの基礎",
            base_name="01-01_APIの基礎"
        )

        result = await scanner._scan_topic_files(1, topic, content_dir)

        # プレフィックス（01-01）でマッチするべき
        assert result['has_html'] is True

    @pytest.mark.asyncio
    async def test_SCN009_complete_progress(self, db, content_dir):
        """SCN-009: 進捗計算（完了）"""
        (content_dir / "01-01_test.html").write_text("<html></html>")
        (content_dir / "01-01_test.txt").write_text("text")
        (content_dir / "01-01_test.mp3").write_bytes(b'\x00')

        scanner = AsyncScanner(db, content_dir.parent)

        topic = ParsedTopic(
            topic_id="01-01",
            chapter="Chapter 1",
            title="test",
            base_name="01-01_test"
        )

        result = await scanner._scan_topic_files(1, topic, content_dir)

        assert result['has_html'] is True
        assert result['has_txt'] is True
        assert result['has_mp3'] is True


class TestHashCalculation:
    """ハッシュ計算テスト"""

    @pytest.mark.asyncio
    async def test_SCN006_hash_calculation(self, db, content_dir):
        """SCN-006: ハッシュ計算"""
        test_file = content_dir / "test.txt"
        test_file.write_text("test content")

        scanner = AsyncScanner(db, content_dir.parent)

        file_hash = await scanner._compute_hash(test_file)

        assert file_hash is not None
        assert len(file_hash) == 16  # xxhash64 hex length

    @pytest.mark.asyncio
    async def test_hash_deterministic(self, db, content_dir):
        """同一ファイルは同一ハッシュ"""
        test_file = content_dir / "test.txt"
        test_file.write_text("test content")

        scanner = AsyncScanner(db, content_dir.parent)

        hash1 = await scanner._compute_hash(test_file)
        hash2 = await scanner._compute_hash(test_file)

        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_hash_different_content(self, db, content_dir):
        """異なる内容は異なるハッシュ"""
        test_file1 = content_dir / "test1.txt"
        test_file2 = content_dir / "test2.txt"
        test_file1.write_text("content 1")
        test_file2.write_text("content 2")

        scanner = AsyncScanner(db, content_dir.parent)

        hash1 = await scanner._compute_hash(test_file1)
        hash2 = await scanner._compute_hash(test_file2)

        assert hash1 != hash2


class TestChangeDetection:
    """変更検出テスト"""

    @pytest.mark.asyncio
    async def test_SCN007_change_detection(self, db, content_dir):
        """SCN-007: 変更検出"""
        test_file = content_dir / "test.txt"
        test_file.write_text("initial content")

        scanner = AsyncScanner(db, content_dir.parent)

        # 初回スキャン
        file_info1 = await scanner.scan_single_file(test_file)
        assert file_info1.changed is True  # 初回は常にTrue

        # ファイル変更
        test_file.write_text("modified content")

        # 変更後スキャン
        file_info2 = await scanner.scan_single_file(test_file)
        assert file_info2.changed is True

    @pytest.mark.asyncio
    async def test_SCN008_no_change_detection(self, db, content_dir):
        """SCN-008: 変更なし検出"""
        test_file = content_dir / "test.txt"
        test_file.write_text("initial content")

        scanner = AsyncScanner(db, content_dir.parent)

        # 初回スキャン
        await scanner.scan_single_file(test_file)

        # 同一ファイル再スキャン
        file_info = await scanner.scan_single_file(test_file)
        assert file_info.changed is False

    @pytest.mark.asyncio
    async def test_scan_single_file_nonexistent(self, db, content_dir):
        """存在しないファイルのスキャン"""
        scanner = AsyncScanner(db, content_dir.parent)

        result = await scanner.scan_single_file(content_dir / "nonexistent.txt")
        assert result is None


class TestProjectScanning:
    """プロジェクトスキャンテスト"""

    @pytest.mark.asyncio
    async def test_scan_project(self, db, project_dir):
        """プロジェクトスキャン"""
        clear_wbs_cache()
        scanner = AsyncScanner(db, project_dir.parent)

        result = await scanner.scan_project(project_dir)

        assert isinstance(result, ScanResult)
        assert result.project_name == "test_project"
        assert result.total_topics > 0

    @pytest.mark.asyncio
    async def test_scan_project_no_wbs(self, db, tmp_path):
        """WBS.jsonがないプロジェクト"""
        project_dir = tmp_path / "no_wbs_project"
        project_dir.mkdir()

        scanner = AsyncScanner(db, tmp_path)

        result = await scanner.scan_project(project_dir)

        assert result.total_topics == 0

    @pytest.mark.asyncio
    async def test_SCN013_scan_all_projects(self, db, tmp_path, mock_wbs_object):
        """SCN-013: 並列スキャン（複数プロジェクト）"""
        import json

        # 複数プロジェクトを作成
        for i in range(3):
            project_dir = tmp_path / f"project_{i}"
            project_dir.mkdir()
            wbs_path = project_dir / "WBS.json"
            wbs_path.write_text(json.dumps(mock_wbs_object, ensure_ascii=False))
            content_dir = project_dir / "content"
            content_dir.mkdir()
            (content_dir / "01-01_test.html").write_text("<html></html>")

        clear_wbs_cache()
        scanner = AsyncScanner(db, tmp_path)

        results = await scanner.scan_all_projects()

        assert len(results) == 3
        assert all(isinstance(r, ScanResult) for r in results)

    @pytest.mark.asyncio
    async def test_scan_already_in_progress(self, db, project_dir):
        """スキャン中の重複実行防止"""
        clear_wbs_cache()
        scanner = AsyncScanner(db, project_dir.parent)

        # スキャンフラグを手動設定
        scanner._scanning = True

        results = await scanner.scan_all_projects()

        # スキャン中なので空リストが返される
        assert results == []

    @pytest.mark.asyncio
    async def test_detect_topics_from_files(self, db, content_dir_with_files):
        """ファイルからのトピック検出"""
        scanner = AsyncScanner(db, content_dir_with_files.parent)

        topics = await scanner._detect_topics_from_files(content_dir_with_files)

        assert len(topics) == 3
        assert all(isinstance(t, ParsedTopic) for t in topics)


class TestPerformance:
    """パフォーマンステスト"""

    @pytest.mark.asyncio
    async def test_SCN012_large_scan_performance(self, db, tmp_path):
        """SCN-012: 大量ファイルスキャンパフォーマンス"""
        # 200ファイルを作成
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        for i in range(200):
            (content_dir / f"{i//10:02d}-{i%10:02d}_topic{i}.html").write_text(f"<html>{i}</html>")

        scanner = AsyncScanner(db, tmp_path)

        start_time = time.time()
        topics = await scanner._detect_topics_from_files(content_dir)
        duration = time.time() - start_time

        assert len(topics) == 200
        assert duration < 1.0, f"処理時間が1秒を超えました: {duration:.2f}s"


class TestCacheManagement:
    """キャッシュ管理テスト"""

    @pytest.mark.asyncio
    async def test_clear_cache(self, db, content_dir):
        """キャッシュクリア"""
        test_file = content_dir / "test.txt"
        test_file.write_text("content")

        scanner = AsyncScanner(db, content_dir.parent)

        # ファイルをスキャンしてキャッシュに保存
        await scanner.scan_single_file(test_file)

        # キャッシュクリア
        scanner.clear_cache()

        # 再スキャン（キャッシュがクリアされているので変更として検出）
        file_info = await scanner.scan_single_file(test_file)
        assert file_info.changed is True
