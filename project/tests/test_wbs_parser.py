"""
WBSパーサーテスト
テスト対象: backend/wbs_parser.py
"""

import pytest
import json
import tempfile
from pathlib import Path

from backend.wbs_parser import (
    detect_wbs_format,
    ObjectFormatParser,
    ArrayFormatParser,
    parse_wbs,
    ParsedTopic,
    clear_wbs_cache
)


class TestWBSFormatDetection:
    """WBS形式検出テスト"""

    def test_WBS001_detect_object_format(self, mock_wbs_object):
        """WBS-001: オブジェクト型形式検出"""
        result = detect_wbs_format(mock_wbs_object)
        assert result == 'object'

    def test_WBS002_detect_array_format(self, mock_wbs_array):
        """WBS-002: 配列型形式検出"""
        result = detect_wbs_format(mock_wbs_array)
        assert result == 'array'

    def test_WBS003_detect_unknown_format(self, mock_wbs_invalid):
        """WBS-003: 不明形式検出"""
        result = detect_wbs_format(mock_wbs_invalid)
        assert result == 'unknown'

    def test_detect_empty_phases_dict(self):
        """空のphasesオブジェクトの検出"""
        wbs = {"phases": {}}
        result = detect_wbs_format(wbs)
        assert result == 'object'

    def test_detect_empty_phases_list(self):
        """空のphasesリストの検出"""
        wbs = {"phases": []}
        result = detect_wbs_format(wbs)
        assert result == 'array'

    def test_detect_missing_phases(self):
        """phasesキーがない場合"""
        wbs = {"project": {"name": "Test"}}
        result = detect_wbs_format(wbs)
        # デフォルトでobjectになる（phasesがないので空のdictとして処理）
        assert result == 'object'


class TestObjectFormatParser:
    """オブジェクト型パーサーテスト"""

    def test_WBS004_parse_object_format(self, mock_wbs_object):
        """WBS-004: オブジェクト型パース"""
        parser = ObjectFormatParser()
        topics = parser.parse(mock_wbs_object)

        assert len(topics) == 5  # 3 + 2 topics
        assert all(isinstance(t, ParsedTopic) for t in topics)

        # 最初のトピックを検証
        first_topic = topics[0]
        assert first_topic.topic_id == "topic_01_01"
        assert first_topic.title == "トピック1-1"
        assert first_topic.base_name == "01-01_トピック1-1"
        assert first_topic.chapter == "Chapter 1: 基礎"

    def test_WBS006_empty_wbs(self, mock_wbs_empty):
        """WBS-006: 空WBS処理"""
        parser = ObjectFormatParser()
        topics = parser.parse(mock_wbs_empty)
        assert topics == []

    def test_WBS007_nested_structure(self):
        """WBS-007: ネストが深い構造"""
        wbs = {
            "phases": {
                "phase_1": {
                    "name": "Phase 1",
                    "chapters": {
                        "ch1": {
                            "name": "Chapter 1",
                            "topics": [{"id": "t1", "title": "Topic 1", "base_name": "01-01_t1"}]
                        }
                    }
                },
                "phase_2": {
                    "name": "Phase 2",
                    "chapters": {
                        "ch1": {
                            "name": "Chapter 1",
                            "topics": [{"id": "t2", "title": "Topic 2", "base_name": "02-01_t2"}]
                        },
                        "ch2": {
                            "name": "Chapter 2",
                            "topics": [
                                {"id": "t3", "title": "Topic 3", "base_name": "02-02_t3"},
                                {"id": "t4", "title": "Topic 4", "base_name": "02-03_t4"}
                            ]
                        }
                    }
                }
            }
        }
        parser = ObjectFormatParser()
        topics = parser.parse(wbs)
        assert len(topics) == 4

    def test_WBS008_missing_base_name(self):
        """WBS-008: base_name欠損時"""
        wbs = {
            "phases": {
                "phase_1": {
                    "chapters": {
                        "ch1": {
                            "name": "Chapter 1",
                            "topics": [{"id": "t1", "title": "Topic 1"}]  # base_nameなし
                        }
                    }
                }
            }
        }
        parser = ObjectFormatParser()
        topics = parser.parse(wbs)
        # base_nameがなくても空文字列でパースされる
        assert len(topics) == 1
        assert topics[0].base_name == ""

    def test_WBS009_japanese_title(self, mock_wbs_object):
        """WBS-009: 日本語タイトル処理"""
        parser = ObjectFormatParser()
        topics = parser.parse(mock_wbs_object)

        # 日本語が正しく処理されていることを確認
        assert any("トピック" in t.title for t in topics)
        assert any("基礎" in t.chapter for t in topics)

    def test_invalid_phase_value(self):
        """不正なフェーズ値のスキップ"""
        wbs = {
            "phases": {
                "phase_1": "invalid",  # dictではない
                "phase_2": {
                    "chapters": {
                        "ch1": {
                            "name": "Chapter 1",
                            "topics": [{"id": "t1", "title": "Topic 1", "base_name": "01-01_t1"}]
                        }
                    }
                }
            }
        }
        parser = ObjectFormatParser()
        topics = parser.parse(wbs)
        assert len(topics) == 1  # phase_2のトピックのみ

    def test_invalid_chapter_value(self):
        """不正なチャプター値のスキップ"""
        wbs = {
            "phases": {
                "phase_1": {
                    "chapters": {
                        "ch1": "invalid",  # dictではない
                        "ch2": {
                            "name": "Chapter 2",
                            "topics": [{"id": "t1", "title": "Topic 1", "base_name": "01-01_t1"}]
                        }
                    }
                }
            }
        }
        parser = ObjectFormatParser()
        topics = parser.parse(wbs)
        assert len(topics) == 1

    def test_invalid_topic_value(self):
        """不正なトピック値のスキップ"""
        wbs = {
            "phases": {
                "phase_1": {
                    "chapters": {
                        "ch1": {
                            "name": "Chapter 1",
                            "topics": [
                                "invalid",  # dictではない
                                {"id": "t1", "title": "Topic 1", "base_name": "01-01_t1"}
                            ]
                        }
                    }
                }
            }
        }
        parser = ObjectFormatParser()
        topics = parser.parse(wbs)
        assert len(topics) == 1


class TestArrayFormatParser:
    """配列型パーサーテスト"""

    def test_WBS005_parse_array_format(self, tmp_path, mock_wbs_array):
        """WBS-005: 配列型パース"""
        # content/フォルダを作成
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "01-01_AI概要.html").touch()
        (content_dir / "01-02_機械学習.html").touch()

        parser = ArrayFormatParser(content_dir)
        topics = parser.parse(mock_wbs_array)

        # ファイル数に基づいてトピックを生成
        assert len(topics) == 2

    def test_parse_array_without_content_path(self, mock_wbs_array):
        """content_pathなしの場合"""
        parser = ArrayFormatParser(content_path=None)
        topics = parser.parse(mock_wbs_array)
        assert topics == []

    def test_parse_array_with_nonexistent_content(self, tmp_path, mock_wbs_array):
        """存在しないcontent_pathの場合"""
        nonexistent_path = tmp_path / "nonexistent"
        parser = ArrayFormatParser(nonexistent_path)
        topics = parser.parse(mock_wbs_array)
        assert topics == []

    def test_extract_chapters(self, mock_wbs_array):
        """チャプター抽出テスト"""
        parser = ArrayFormatParser()
        chapters = parser._extract_chapters(mock_wbs_array)

        assert "ch1" in chapters
        assert "ch2" in chapters
        assert chapters["ch1"] == "Chapter 1: 基礎"
        assert chapters["ch2"] == "Chapter 2: 応用"

    def test_infer_chapter(self):
        """チャプター推論テスト"""
        parser = ArrayFormatParser()
        chapters = {"ch1": "Chapter 1: 基礎", "ch2": "Chapter 2: 応用"}

        assert parser._infer_chapter("01-01_test", chapters) == "Chapter 1: 基礎"
        assert parser._infer_chapter("02-01_test", chapters) == "Chapter 2: 応用"
        assert parser._infer_chapter("03-01_test", chapters) == "Chapter 3"
        assert parser._infer_chapter("invalid", chapters) == "Unknown"

    def test_extract_topic_id(self):
        """トピックID抽出テスト"""
        parser = ArrayFormatParser()

        assert parser._extract_topic_id("01-01_APIの基礎") == "01-01"
        assert parser._extract_topic_id("02-15_高度な使い方") == "02-15"
        assert parser._extract_topic_id("invalid") == "inval"

    def test_clean_title(self):
        """タイトルクリーニングテスト"""
        parser = ArrayFormatParser()

        assert parser._clean_title("01-01_APIの基礎") == "APIの基礎"
        assert parser._clean_title("02-15_高度な使い方") == "高度な使い方"
        assert parser._clean_title("invalid_name") == "invalid_name"


class TestParseWBS:
    """WBSパース統合テスト"""

    def test_parse_object_wbs_file(self, tmp_path, mock_wbs_object):
        """オブジェクト型WBSファイルのパース"""
        wbs_path = tmp_path / "WBS.json"
        wbs_path.write_text(json.dumps(mock_wbs_object, ensure_ascii=False))

        # キャッシュをクリア
        clear_wbs_cache()

        topics = parse_wbs(wbs_path)
        assert len(topics) == 5

    def test_parse_array_wbs_file(self, tmp_path, mock_wbs_array):
        """配列型WBSファイルのパース"""
        # content/フォルダを作成
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "01-01_test.html").touch()

        wbs_path = tmp_path / "WBS.json"
        wbs_path.write_text(json.dumps(mock_wbs_array, ensure_ascii=False))

        clear_wbs_cache()

        topics = parse_wbs(wbs_path, content_dir)
        assert len(topics) == 1

    def test_parse_nonexistent_file(self, tmp_path):
        """存在しないファイルのパース"""
        clear_wbs_cache()
        topics = parse_wbs(tmp_path / "nonexistent.json")
        assert topics == []

    def test_parse_invalid_json(self, tmp_path):
        """不正なJSONファイルのパース"""
        wbs_path = tmp_path / "WBS.json"
        wbs_path.write_text("invalid json {{{")

        clear_wbs_cache()

        topics = parse_wbs(wbs_path)
        assert topics == []

    def test_WBS010_large_wbs_performance(self, tmp_path):
        """WBS-010: 大規模WBS処理パフォーマンス"""
        import time

        # 200トピックを持つ大規模WBSを生成
        topics_list = [
            {"id": f"topic_{i:03d}", "title": f"Topic {i}", "base_name": f"{i//10:02d}-{i%10:02d}_Topic{i}"}
            for i in range(200)
        ]

        wbs = {
            "phases": {
                "phase_1": {
                    "chapters": {
                        "ch1": {
                            "name": "Large Chapter",
                            "topics": topics_list
                        }
                    }
                }
            }
        }

        wbs_path = tmp_path / "WBS.json"
        wbs_path.write_text(json.dumps(wbs, ensure_ascii=False))

        clear_wbs_cache()

        start_time = time.time()
        topics = parse_wbs(wbs_path)
        duration_ms = (time.time() - start_time) * 1000

        assert len(topics) == 200
        assert duration_ms < 100, f"処理時間が100msを超えました: {duration_ms:.2f}ms"


class TestWBSCache:
    """WBSキャッシュテスト"""

    def test_cache_works(self, tmp_path, mock_wbs_object):
        """キャッシュが動作することを確認"""
        wbs_path = tmp_path / "WBS.json"
        wbs_path.write_text(json.dumps(mock_wbs_object, ensure_ascii=False))

        clear_wbs_cache()

        # 1回目の呼び出し
        topics1 = parse_wbs(wbs_path)

        # 2回目の呼び出し（キャッシュから）
        topics2 = parse_wbs(wbs_path)

        assert len(topics1) == len(topics2)

    def test_clear_cache(self, tmp_path, mock_wbs_object):
        """キャッシュクリアが動作することを確認"""
        wbs_path = tmp_path / "WBS.json"
        wbs_path.write_text(json.dumps(mock_wbs_object, ensure_ascii=False))

        clear_wbs_cache()
        topics1 = parse_wbs(wbs_path)

        # キャッシュクリア
        clear_wbs_cache()

        # ファイル内容を変更
        mock_wbs_object["phases"]["phase_2"]["chapters"]["chapter_1"]["topics"].append(
            {"id": "new", "title": "New Topic", "base_name": "new_topic"}
        )
        wbs_path.write_text(json.dumps(mock_wbs_object, ensure_ascii=False))

        topics2 = parse_wbs(wbs_path)
        assert len(topics2) == len(topics1) + 1
