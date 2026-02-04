"""
高速ファイルスキャナー
パフォーマンス最適化: xxHash、LRUキャッシュ、非同期並列処理
"""

import asyncio
import aiofiles
from pathlib import Path
from typing import Optional, List, Dict, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
import xxhash
import logging

from .wbs_parser import parse_wbs, ParsedTopic, detect_wbs_format, clear_wbs_cache
from .database import Database

logger = logging.getLogger(__name__)

# キャッシュ設定
MAX_HASH_CACHE_SIZE = 1000
HASH_TTL_SECONDS = 300


@dataclass
class FileInfo:
    """ファイル情報"""
    path: Path
    hash: str
    changed: bool = False
    size: int = 0


@dataclass
class ScanResult:
    """スキャン結果"""
    project_name: str
    project_path: Path
    total_topics: int = 0
    html_count: int = 0
    txt_count: int = 0
    mp3_count: int = 0
    completed_topics: int = 0
    files_scanned: int = 0
    changes_detected: int = 0
    duration_ms: float = 0
    topics: List[Dict] = field(default_factory=list)


class HashCache:
    """LRUハッシュキャッシュ（高速差分検出用）"""

    def __init__(self, max_size: int = MAX_HASH_CACHE_SIZE):
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._max_size = max_size

    def get(self, path: str) -> Optional[str]:
        """キャッシュからハッシュを取得"""
        if path in self._cache:
            hash_val, timestamp = self._cache[path]
            # TTLチェック
            if (datetime.now().timestamp() - timestamp) < HASH_TTL_SECONDS:
                return hash_val
            else:
                del self._cache[path]
        return None

    def set(self, path: str, hash_val: str) -> None:
        """ハッシュをキャッシュに保存"""
        # LRU: キャッシュが満杯なら最古を削除
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        self._cache[path] = (hash_val, datetime.now().timestamp())

    def is_changed(self, path: str, new_hash: str) -> bool:
        """ファイルが変更されたか判定"""
        old_hash = self.get(path)
        return old_hash is None or old_hash != new_hash

    def clear(self) -> None:
        """キャッシュをクリア"""
        self._cache.clear()


class AsyncScanner:
    """高速非同期ファイルスキャナー"""

    def __init__(self, db: Database, base_path: Path):
        self.db = db
        self.base_path = base_path
        self.hash_cache = HashCache()
        self._scanning = False

    async def scan_all_projects(self) -> List[ScanResult]:
        """全プロジェクトをスキャン"""
        if self._scanning:
            logger.warning("Scan already in progress")
            return []

        self._scanning = True
        results = []

        try:
            start_time = datetime.now()

            # プロジェクトフォルダを検出
            project_dirs = [
                d for d in self.base_path.iterdir()
                if d.is_dir() and (d / 'WBS.json').exists()
            ]

            logger.info(f"Found {len(project_dirs)} projects to scan")

            # 並列スキャン（最大4並列）
            semaphore = asyncio.Semaphore(4)

            async def scan_with_limit(project_path: Path) -> ScanResult:
                async with semaphore:
                    return await self.scan_project(project_path)

            tasks = [scan_with_limit(p) for p in project_dirs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # エラーをフィルタリング
            valid_results = []
            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"Scan error: {r}")
                else:
                    valid_results.append(r)

            total_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"Full scan completed: {len(valid_results)} projects in {total_time:.0f}ms")

            return valid_results

        finally:
            self._scanning = False

    async def scan_project(self, project_path: Path) -> ScanResult:
        """単一プロジェクトをスキャン"""
        start_time = datetime.now()
        project_name = project_path.name

        result = ScanResult(
            project_name=project_name,
            project_path=project_path
        )

        try:
            # WBS.jsonをパース
            wbs_path = project_path / 'WBS.json'
            content_path = project_path / 'content'

            if not wbs_path.exists():
                logger.warning(f"No WBS.json found: {project_path}")
                return result

            topics = parse_wbs(wbs_path, content_path)

            # WBS形式検出
            with open(wbs_path, 'r', encoding='utf-8') as f:
                import json
                wbs_data = json.load(f)
                wbs_format = detect_wbs_format(wbs_data)

            # プロジェクトをDB登録
            project_id = await self.db.upsert_project(
                name=project_name,
                path=str(project_path),
                wbs_format=wbs_format
            )

            # トピックがない場合はファイルシステムから検出
            if not topics and content_path.exists():
                topics = await self._detect_topics_from_files(content_path)

            result.total_topics = len(topics)

            # 各トピックのファイル状態をスキャン（並列）
            scan_tasks = []
            for topic in topics:
                scan_tasks.append(
                    self._scan_topic_files(project_id, topic, content_path)
                )

            topic_results = await asyncio.gather(*scan_tasks)

            # 結果集計
            for tr in topic_results:
                if tr.get('has_html'):
                    result.html_count += 1
                if tr.get('has_txt'):
                    result.txt_count += 1
                if tr.get('has_mp3'):
                    result.mp3_count += 1
                if tr.get('has_html') and tr.get('has_txt') and tr.get('has_mp3'):
                    result.completed_topics += 1
                result.files_scanned += tr.get('files_scanned', 0)
                result.changes_detected += tr.get('changes', 0)
                result.topics.append(tr)

            # プロジェクト統計を更新
            await self.db.update_project_stats(
                project_id=project_id,
                total_topics=result.total_topics,
                completed_topics=result.completed_topics,
                html_count=result.html_count,
                txt_count=result.txt_count,
                mp3_count=result.mp3_count
            )

            result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(
                f"Scanned {project_name}: {result.total_topics} topics, "
                f"{result.html_count}H/{result.txt_count}T/{result.mp3_count}M "
                f"in {result.duration_ms:.0f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Error scanning {project_name}: {e}")
            result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return result

    async def _detect_topics_from_files(self, content_path: Path, subfolder: str = "") -> List[ParsedTopic]:
        """ファイルシステムからトピックを再帰的に検出（数値で始まるファイルのみ）"""
        import re
        topics = []
        seen_bases = set()  # (subfolder, base_name) のペアで重複チェック

        current_path = content_path / subfolder if subfolder else content_path

        if not current_path.exists():
            return topics

        for item in current_path.iterdir():
            # サブフォルダの場合は再帰的にスキャン
            if item.is_dir():
                # 隠しフォルダと特殊フォルダをスキップ
                if item.name.startswith('.') or item.name in ['__pycache__', 'node_modules']:
                    continue

                # サブフォルダパスを構築
                new_subfolder = f"{subfolder}/{item.name}" if subfolder else item.name
                sub_topics = await self._detect_topics_from_files(content_path, new_subfolder)
                topics.extend(sub_topics)
                continue

            # ファイルの場合
            if item.suffix in ['.html', '.txt', '.mp3']:
                base_name = item.stem

                # 数値で始まるファイル名のみを対象とする
                # 例: 01-01_xxx, 1_xxx, 01_xxx など
                if not re.match(r'^\d', base_name):
                    continue

                # 重複チェック（サブフォルダ + ファイル名）
                key = (subfolder, base_name)
                if key not in seen_bases:
                    seen_bases.add(key)

                    # トピックID抽出
                    match = re.match(r'^(\d{2}-\d{2})', base_name)
                    topic_id = match.group(1) if match else base_name[:5]

                    topics.append(ParsedTopic(
                        topic_id=topic_id,
                        chapter=subfolder if subfolder else "",  # サブフォルダ名をchapterとして使用
                        title=base_name,
                        base_name=base_name,
                        subfolder=subfolder
                    ))

        return sorted(topics, key=lambda t: (t.subfolder, t.base_name))

    async def _scan_topic_files(
        self,
        project_id: int,
        topic: ParsedTopic,
        content_path: Path
    ) -> Dict:
        """トピックのファイル状態をスキャン（数値で始まるファイルのみ、サブフォルダ対応）"""
        import re

        result = {
            'base_name': topic.base_name,
            'topic_id': topic.topic_id,
            'chapter': topic.chapter,
            'title': topic.title,
            'subfolder': topic.subfolder,
            'has_html': False,
            'has_txt': False,
            'has_mp3': False,
            'html_hash': None,
            'txt_hash': None,
            'mp3_hash': None,
            'files_scanned': 0,
            'changes': 0
        }

        # 数値で始まるファイル名のみを対象とする
        if not re.match(r'^\d', topic.base_name):
            return result

        # サブフォルダを考慮したパスを計算
        actual_content_path = content_path / topic.subfolder if topic.subfolder else content_path

        # ファイル存在チェックとハッシュ計算
        for ext in ['html', 'txt', 'mp3']:
            file_path = actual_content_path / f"{topic.base_name}.{ext}"

            # プレフィックスマッチも試みる（数値で始まるファイルのみ）
            if not file_path.exists():
                prefix = topic.base_name.split('_')[0]  # "01-01"
                # 数値プレフィックスの場合のみマッチを試みる
                if re.match(r'^\d', prefix):
                    matches = [
                        m for m in actual_content_path.glob(f"{prefix}*.{ext}")
                        if re.match(r'^\d', m.stem)  # 数値で始まるファイルのみ
                    ]
                    if matches:
                        file_path = matches[0]

            if file_path.exists() and re.match(r'^\d', file_path.stem):
                result[f'has_{ext}'] = True
                result['files_scanned'] += 1

                # xxHashで高速ハッシュ計算
                file_hash = await self._compute_hash(file_path)
                result[f'{ext}_hash'] = file_hash

                # 変更検出
                cache_key = str(file_path)
                if self.hash_cache.is_changed(cache_key, file_hash):
                    result['changes'] += 1
                    self.hash_cache.set(cache_key, file_hash)

        # DBに保存
        await self.db.upsert_topic(
            project_id=project_id,
            base_name=topic.base_name,
            topic_id=topic.topic_id,
            chapter=topic.chapter,
            title=topic.title,
            subfolder=topic.subfolder,
            has_html=result['has_html'],
            has_txt=result['has_txt'],
            has_mp3=result['has_mp3'],
            html_hash=result['html_hash'],
            txt_hash=result['txt_hash'],
            mp3_hash=result['mp3_hash']
        )

        return result

    async def _compute_hash(self, file_path: Path) -> str:
        """xxHashでファイルハッシュを高速計算"""
        hasher = xxhash.xxh64()

        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(65536):  # 64KB chunks
                hasher.update(chunk)

        return hasher.hexdigest()

    async def scan_single_file(self, file_path: Path) -> Optional[FileInfo]:
        """単一ファイルをスキャン（差分検出用）"""
        if not file_path.exists():
            return None

        try:
            file_hash = await self._compute_hash(file_path)
            cache_key = str(file_path)
            changed = self.hash_cache.is_changed(cache_key, file_hash)

            if changed:
                self.hash_cache.set(cache_key, file_hash)

            stat = file_path.stat()
            return FileInfo(
                path=file_path,
                hash=file_hash,
                changed=changed,
                size=stat.st_size
            )

        except Exception as e:
            logger.error(f"Error scanning file {file_path}: {e}")
            return None

    def clear_cache(self) -> None:
        """全キャッシュをクリア"""
        self.hash_cache.clear()
        clear_wbs_cache()
        logger.info("Scanner cache cleared")
