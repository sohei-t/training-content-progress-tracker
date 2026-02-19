"""
高速ファイルスキャナー
パフォーマンス最適化: xxHash、LRUキャッシュ、非同期並列処理
"""

import asyncio
import aiofiles
import re
from pathlib import Path
from typing import Optional, List, Dict, Set, Tuple
from collections import defaultdict
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

            # 削除されたプロジェクトをクリーンアップ
            deleted_count = await self._cleanup_deleted_projects()
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} deleted projects")

            # プロジェクトフォルダを検出（WBS.json または content/ フォルダがあるもの）
            # 除外: old, 隠しフォルダ
            excluded_folders = {'old', '.git', '__pycache__', 'node_modules'}
            project_dirs = [
                d for d in self.base_path.iterdir()
                if d.is_dir()
                and d.name not in excluded_folders
                and not d.name.startswith('.')
                and ((d / 'WBS.json').exists() or (d / 'content').is_dir())
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

    async def _cleanup_deleted_projects(self) -> int:
        """実フォルダが存在しないプロジェクトをDBから削除"""
        deleted_count = 0

        # DB内の全プロジェクトを取得
        db_projects = await self.db.get_all_projects()

        for project in db_projects:
            project_path = Path(project['path'])

            # フォルダが存在しない、またはWBS.json/contentがない場合は削除
            if not project_path.exists():
                logger.info(f"Project folder not found, removing from DB: {project['name']} ({project_path})")
                await self.db.delete_project(project['id'])
                deleted_count += 1
            elif not (project_path / 'WBS.json').exists() and not (project_path / 'content').is_dir():
                logger.info(f"Project has no WBS.json or content folder, removing from DB: {project['name']}")
                await self.db.delete_project(project['id'])
                deleted_count += 1

        return deleted_count

    async def scan_project(self, project_path: Path) -> ScanResult:
        """単一プロジェクトをスキャン"""
        start_time = datetime.now()
        project_name = project_path.name

        result = ScanResult(
            project_name=project_name,
            project_path=project_path
        )

        try:
            # WBS.jsonをパース（存在する場合）
            wbs_path = project_path / 'WBS.json'
            content_path = project_path / 'content'

            topics = []
            wbs_format = None

            if wbs_path.exists():
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

            # WBS.jsonがない場合、またはトピックがない場合はファイルシステムから検出
            if not topics and content_path.exists():
                topics = await self._detect_topics_from_files(content_path)

            # index.html等の非トピックファイルを除外
            topics = [t for t in topics if t.base_name != 'index']

            # WBS base_name と実ファイル名の不一致をフォールバックマッチングで解決
            if topics and content_path.exists():
                topics = self._resolve_base_names(topics, content_path)

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

    @staticmethod
    def _extract_episode_info(base_name: str) -> Tuple[str, Optional[str]]:
        """base_name からレベル接頭語とエピソード番号を抽出

        Returns:
            (prefix, episode): prefix はレベル名（例: "intro", "advanced"）、
                                episode はエピソード番号（例: "01-01", "1-1-1"）。
                                抽出できない場合は ('', None)。

        Examples:
            '01-01_title'       -> ('', '01-01')
            'intro-1-1'         -> ('intro', '1-1')
            'advanced_1-1_xxx'  -> ('advanced', '1-1')
            '1-1-1_title'       -> ('', '1-1-1')
        """
        # アルファベット接頭語あり: advanced_1-1_xxx, intro-1-1
        # 3階層目は同じセパレータの場合のみ許可（\3 で後方参照）
        m = re.match(r'^([a-zA-Z]+)[-_](\d{1,3})([-_])(\d{1,3})(?:(\3)(\d{1,3}))?(?:[-_]|$)', base_name)
        if m:
            episode = f"{m.group(2)}-{m.group(4)}"
            if m.group(6):  # 3階層目あり
                episode += f"-{m.group(6)}"
            return m.group(1).lower(), episode

        # 接頭語なし: 01-01_title, 1-1-1_title
        m = re.match(r'^(\d{1,3})([-_])(\d{1,3})(?:(\2)(\d{1,3}))?(?:[-_]|$)', base_name)
        if m:
            episode = f"{m.group(1)}-{m.group(3)}"
            if m.group(5):  # 3階層目あり
                episode += f"-{m.group(5)}"
            return '', episode

        return '', None

    def _build_file_index(self, content_path: Path) -> Dict[str, List[Tuple[str, str, str]]]:
        """content ディレクトリ内のファイルをエピソード番号でインデックス化

        Returns:
            { normalized_episode: [(base_name, prefix, subfolder), ...] }
        """
        index = defaultdict(list)

        def scan_dir(dir_path: Path, subfolder: str = ""):
            if not dir_path.exists():
                return
            for item in dir_path.iterdir():
                if item.is_dir():
                    if item.name.startswith('.') or item.name in ['__pycache__', 'node_modules', 'old']:
                        continue
                    new_sub = f"{subfolder}/{item.name}" if subfolder else item.name
                    scan_dir(item, new_sub)
                elif item.suffix == '.html' and item.stem != 'index':
                    prefix, episode = self._extract_episode_info(item.stem)
                    if episode:
                        index[episode].append((item.stem, prefix, subfolder))

        scan_dir(content_path)
        return index

    def _resolve_base_names(self, topics: List[ParsedTopic], content_path: Path) -> List[ParsedTopic]:
        """WBS base_name が実ファイルと一致しない場合、エピソード番号でフォールバックマッチング

        マッチング優先順位:
        1. WBS base_name の完全一致（変更不要）
        2. エピソード番号で一意マッチ
        3. エピソード番号 + 接頭語（レベル名）で絞り込み
        4. エピソード番号 + サブフォルダで絞り込み
        """
        # ファイルインデックスを構築
        file_index = self._build_file_index(content_path)

        resolved = []
        resolved_count = 0

        for topic in topics:
            # 1. 完全一致チェック
            search_path = content_path / topic.subfolder if topic.subfolder else content_path
            if (search_path / f"{topic.base_name}.html").exists():
                resolved.append(topic)
                continue

            # エピソード番号を抽出
            wbs_prefix, episode = self._extract_episode_info(topic.base_name)
            if not episode:
                resolved.append(topic)
                continue

            candidates = file_index.get(episode, [])

            if not candidates:
                logger.warning(
                    f"No file found for ep={episode} (WBS base_name: {topic.base_name})"
                )
                resolved.append(topic)
                continue

            # サブフォルダが指定されていれば、同じサブフォルダの候補に絞る
            if topic.subfolder:
                subfolder_filtered = [c for c in candidates if c[2] == topic.subfolder]
                if subfolder_filtered:
                    candidates = subfolder_filtered

            # 2. 一意マッチ
            if len(candidates) == 1:
                actual_base, _, actual_subfolder = candidates[0]
                logger.info(f"Resolved: {topic.base_name} -> {actual_base} (ep={episode})")
                resolved.append(ParsedTopic(
                    topic_id=topic.topic_id,
                    chapter=topic.chapter,
                    title=topic.title,
                    base_name=actual_base,
                    subfolder=actual_subfolder
                ))
                resolved_count += 1
                continue

            # 3. 接頭語で絞り込み
            if wbs_prefix:
                prefix_filtered = [c for c in candidates if c[1] == wbs_prefix]
                if len(prefix_filtered) == 1:
                    actual_base, _, actual_subfolder = prefix_filtered[0]
                    logger.info(
                        f"Resolved (prefix={wbs_prefix}): {topic.base_name} -> {actual_base}"
                    )
                    resolved.append(ParsedTopic(
                        topic_id=topic.topic_id,
                        chapter=topic.chapter,
                        title=topic.title,
                        base_name=actual_base,
                        subfolder=actual_subfolder
                    ))
                    resolved_count += 1
                    continue

            # 4. 解決不能
            logger.warning(
                f"Ambiguous match for {topic.base_name} (ep={episode}): "
                f"{[c[0] for c in candidates]}"
            )
            resolved.append(topic)

        if resolved_count > 0:
            logger.info(f"Resolved {resolved_count} WBS base_name mismatches by episode number")

        return resolved

    async def _detect_topics_from_files(self, content_path: Path, subfolder: str = "") -> List[ParsedTopic]:
        """ファイルシステムからトピックを再帰的に検出（数値-数値パターンを含むファイルのみ）"""
        topics = []
        seen_bases = set()  # (subfolder, base_name) のペアで重複チェック

        # 数値-数値または数値_数値パターン（例: 1-1, 01-02, 2-3, 1_1, 10_2）
        topic_pattern = re.compile(r'\d+[-_]\d+')

        current_path = content_path / subfolder if subfolder else content_path

        if not current_path.exists():
            return topics

        for item in current_path.iterdir():
            # サブフォルダの場合は再帰的にスキャン
            if item.is_dir():
                # 隠しフォルダと特殊フォルダをスキップ
                if item.name.startswith('.') or item.name in ['__pycache__', 'node_modules', 'old']:
                    continue

                # サブフォルダパスを構築
                new_subfolder = f"{subfolder}/{item.name}" if subfolder else item.name
                sub_topics = await self._detect_topics_from_files(content_path, new_subfolder)
                topics.extend(sub_topics)
                continue

            # ファイルの場合
            if item.suffix in ['.html', '.txt', '.mp3']:
                base_name = item.stem

                # _ssml で終わるファイルはスキップ（SSMLは別途チェック）
                if base_name.endswith('_ssml'):
                    continue

                # 数値-数値または数値_数値パターンを含むファイル名のみを対象とする
                # 例: 01-01_xxx, advanced_1-1, basic_2-3, 1_1_xxx など
                if not topic_pattern.search(base_name):
                    continue

                # 重複チェック（サブフォルダ + ファイル名）
                key = (subfolder, base_name)
                if key not in seen_bases:
                    seen_bases.add(key)

                    # トピックID抽出（数値-数値部分）
                    match = topic_pattern.search(base_name)
                    topic_id = match.group(0) if match else base_name[:5]

                    topics.append(ParsedTopic(
                        topic_id=topic_id,
                        chapter=subfolder if subfolder else "",  # サブフォルダ名をchapterとして使用
                        title=base_name,
                        base_name=base_name,
                        subfolder=subfolder
                    ))

        # レベル対応ソート（入門→初級→中級→上級の順）
        LEVEL_ORDER = {
            'intro': 0, 'introduction': 0, 'beginner': 0,
            'basic': 1, 'elementary': 1,
            'intermediate': 2,
            'advanced': 3,
        }

        def sort_key(t):
            subfolder = t.subfolder or ''
            base_name = t.base_name
            level_order = 0

            # サブフォルダからレベル検出
            if subfolder:
                folder = subfolder.split('/')[-1].lower()
                level_order = LEVEL_ORDER.get(folder, 0)

            # レベルプレフィックス: "intro-1-1", "advanced_2-3"
            m = re.match(r'^([a-zA-Z]+)[-_](\d+)[-_](\d+)', base_name)
            if m:
                level_order = LEVEL_ORDER.get(m.group(1).lower(), 99)
                return (level_order, int(m.group(2)), int(m.group(3)), base_name)

            # 3階層数値: "1-1-1_title"
            m = re.match(r'^(\d+)[-_](\d+)[-_](\d+)', base_name)
            if m:
                return (int(m.group(1)), int(m.group(2)), int(m.group(3)), base_name)

            # 2階層数値: "01-01_title"
            m = re.match(r'^(\d+)[-_](\d+)', base_name)
            if m:
                return (level_order, int(m.group(1)), int(m.group(2)), base_name)

            return (99, 0, 0, base_name)

        return sorted(topics, key=sort_key)

    async def _scan_topic_files(
        self,
        project_id: int,
        topic: ParsedTopic,
        content_path: Path
    ) -> Dict:
        """トピックのファイル状態をスキャン（数値-数値パターンを含むファイル、サブフォルダ対応）"""
        # 数値-数値または数値_数値パターン（例: 1-1, 01-02, 2-3, 1_1, 10_2）
        topic_pattern = re.compile(r'\d+[-_]\d+')

        result = {
            'base_name': topic.base_name,
            'topic_id': topic.topic_id,
            'chapter': topic.chapter,
            'title': topic.title,
            'subfolder': topic.subfolder,
            'has_html': False,
            'has_txt': False,
            'has_mp3': False,
            'has_ssml': False,
            'html_hash': None,
            'txt_hash': None,
            'mp3_hash': None,
            'ssml_hash': None,
            'files_scanned': 0,
            'changes': 0
        }

        # 数値-数値パターンを含むファイル名のみを対象とする
        if not topic_pattern.search(topic.base_name):
            return result

        # サブフォルダを考慮したパスを計算
        actual_content_path = content_path / topic.subfolder if topic.subfolder else content_path

        # ファイル存在チェックとハッシュ計算
        for ext in ['html', 'txt', 'mp3']:
            file_path = actual_content_path / f"{topic.base_name}.{ext}"

            if file_path.exists() and topic_pattern.search(file_path.stem):
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

        # SSMLファイルのチェック（{base_name}_ssml.txt）
        ssml_path = actual_content_path / f"{topic.base_name}_ssml.txt"
        if ssml_path.exists():
            result['has_ssml'] = True
            result['files_scanned'] += 1

            ssml_hash = await self._compute_hash(ssml_path)
            result['ssml_hash'] = ssml_hash

            cache_key = str(ssml_path)
            if self.hash_cache.is_changed(cache_key, ssml_hash):
                result['changes'] += 1
                self.hash_cache.set(cache_key, ssml_hash)

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
            has_ssml=result['has_ssml'],
            html_hash=result['html_hash'],
            txt_hash=result['txt_hash'],
            mp3_hash=result['mp3_hash'],
            ssml_hash=result['ssml_hash']
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
