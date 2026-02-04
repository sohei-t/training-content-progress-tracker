"""
WBSパーサー（両形式対応）
パフォーマンス最適化: キャッシュ付きパース、遅延評価
"""

import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Protocol
from dataclasses import dataclass
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParsedTopic:
    """パース済みトピック"""
    topic_id: str
    chapter: str
    title: str
    base_name: str
    subfolder: str = ""  # サブフォルダパス（例: "入門", "初級/基礎" など）


class WBSParserProtocol(Protocol):
    """WBSパーサーインターフェース"""
    def parse(self, data: dict) -> List[ParsedTopic]: ...


class ObjectFormatParser:
    """オブジェクト型WBSパーサー（API入門講座形式）"""

    def parse(self, data: dict) -> List[ParsedTopic]:
        """オブジェクト型WBSをパース"""
        topics = []
        phases = data.get('phases', {})

        for phase_key, phase in phases.items():
            if not isinstance(phase, dict):
                continue

            chapters = phase.get('chapters', {})
            for ch_key, chapter in chapters.items():
                if not isinstance(chapter, dict):
                    continue

                chapter_name = chapter.get('name', ch_key)
                for topic_data in chapter.get('topics', []):
                    if not isinstance(topic_data, dict):
                        continue

                    topics.append(ParsedTopic(
                        topic_id=topic_data.get('id', ''),
                        chapter=chapter_name,
                        title=topic_data.get('title', ''),
                        base_name=topic_data.get('base_name', '')
                    ))

        return topics


class ArrayFormatParser:
    """配列型WBSパーサー（生成AI入門講座形式）"""

    def __init__(self, content_path: Optional[Path] = None):
        self.content_path = content_path

    def parse(self, data: dict) -> List[ParsedTopic]:
        """配列型WBSをパース（ファイルシステムから推論）"""
        topics = []

        if not self.content_path:
            logger.warning("Content path not set for array format parser")
            return topics

        # content/ フォルダのファイルを基準にトピックを特定
        files = self._scan_content_files()
        chapters = self._extract_chapters(data)

        for file_name in files:
            chapter = self._infer_chapter(file_name, chapters)
            topic_id = self._extract_topic_id(file_name)

            topics.append(ParsedTopic(
                topic_id=topic_id,
                chapter=chapter,
                title=self._clean_title(file_name),
                base_name=file_name
            ))

        return topics

    def _scan_content_files(self) -> List[str]:
        """content/フォルダのHTMLファイルを基準にトピックを特定"""
        if not self.content_path or not self.content_path.exists():
            return []

        files = set()
        for html_file in self.content_path.glob('*.html'):
            base = html_file.stem
            files.add(base)

        return sorted(files)

    def _extract_chapters(self, data: dict) -> Dict[str, str]:
        """WBS構造からチャプター情報を抽出"""
        chapters = {}
        phases = data.get('phases', [])

        if not isinstance(phases, list):
            return chapters

        for phase in phases:
            if not isinstance(phase, dict):
                continue

            for part in phase.get('parts', []):
                if not isinstance(part, dict):
                    continue

                for chapter in part.get('chapters', []):
                    if isinstance(chapter, dict):
                        ch_id = chapter.get('id', '')
                        ch_name = chapter.get('name', ch_id)
                        chapters[ch_id] = ch_name

        return chapters

    def _infer_chapter(self, file_name: str, chapters: Dict[str, str]) -> str:
        """ファイル名からチャプターを推論"""
        # ファイル名パターン: "01-01_title" -> chapter 1
        match = re.match(r'^(\d{2})-\d{2}', file_name)
        if match:
            chapter_num = int(match.group(1))
            ch_key = f"ch{chapter_num}"
            if ch_key in chapters:
                return chapters[ch_key]
            return f"Chapter {chapter_num}"
        return "Unknown"

    def _extract_topic_id(self, file_name: str) -> str:
        """ファイル名からトピックIDを抽出"""
        match = re.match(r'^(\d{2}-\d{2})', file_name)
        return match.group(1) if match else file_name[:5]

    def _clean_title(self, file_name: str) -> str:
        """ファイル名からタイトルを抽出"""
        # "01-01_APIの基礎" -> "APIの基礎"
        match = re.match(r'^\d{2}-\d{2}_(.+)$', file_name)
        return match.group(1) if match else file_name


def detect_wbs_format(wbs_data: dict) -> str:
    """WBS形式を自動検出"""
    phases = wbs_data.get('phases', {})

    if isinstance(phases, dict):
        # オブジェクト型の詳細チェック
        for phase_key, phase_value in phases.items():
            if isinstance(phase_value, dict) and 'chapters' in phase_value:
                chapters = phase_value['chapters']
                if isinstance(chapters, dict):
                    for ch_key, ch_value in chapters.items():
                        if isinstance(ch_value, dict):
                            topics = ch_value.get('topics', [])
                            if isinstance(topics, list) and len(topics) > 0:
                                if isinstance(topics[0], dict):
                                    return 'object'
        return 'object'  # デフォルト

    elif isinstance(phases, list):
        return 'array'

    return 'unknown'


@lru_cache(maxsize=100)
def _load_wbs_cached(wbs_path: str) -> Dict[str, Any]:
    """WBSファイルをキャッシュ付きで読み込み"""
    with open(wbs_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_wbs(wbs_path: Path, content_path: Optional[Path] = None) -> List[ParsedTopic]:
    """WBSファイルをパース（自動形式検出）"""
    try:
        data = _load_wbs_cached(str(wbs_path))
    except json.JSONDecodeError as e:
        logger.error(f"WBS JSON parse error: {wbs_path} - {e}")
        return []
    except FileNotFoundError:
        logger.error(f"WBS file not found: {wbs_path}")
        return []

    format_type = detect_wbs_format(data)
    logger.info(f"Detected WBS format: {format_type} for {wbs_path}")

    if format_type == 'object':
        parser = ObjectFormatParser()
        return parser.parse(data)
    elif format_type == 'array':
        parser = ArrayFormatParser(content_path)
        return parser.parse(data)
    else:
        logger.warning(f"Unknown WBS format: {wbs_path}")
        return []


def clear_wbs_cache() -> None:
    """WBSキャッシュをクリア"""
    _load_wbs_cached.cache_clear()
    logger.info("WBS cache cleared")
