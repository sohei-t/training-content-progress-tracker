# 研修コンテンツ進捗トラッカー - テスト設計書 (TEST_DESIGN.md)

> **バージョン**: 1.0
> **作成日**: 2026-02-03
> **対象**: 革新的アプローチ（イベント駆動・リアルタイム・高パフォーマンス）

---

## 1. テスト戦略

### 1.1 テストピラミッド

```
                    ┌───────────┐
                   /   E2E(10%) \         ← ユーザーシナリオテスト
                  /───────────────\            Playwright
                 /                 \
                /─────────────────────\
               /   統合テスト (20%)     \   ← API + DB + WebSocket
              /─────────────────────────\
             /                           \
            /───────────────────────────────\
           /      ユニットテスト (70%)        \  ← パーサー、スキャナー、計算ロジック
          /─────────────────────────────────────\
```

| レベル | 比率 | 実行時間目標 | 主な対象 |
|--------|-----|-------------|---------|
| ユニットテスト | 70% | < 5秒 | パーサー、スキャナー、計算ロジック、API |
| 統合テスト | 20% | < 30秒 | API + DB、WebSocket、ファイル監視 |
| E2Eテスト | 10% | < 2分 | ダッシュボード表示、リアルタイム更新 |

### 1.2 優先度マトリクス

| 優先度 | 対象 | カバレッジ目標 | 理由 |
|--------|------|--------------|------|
| **CRITICAL** | WBSパーサー（両形式） | 100% | 全機能の基盤、形式検出の正確性必須 |
| **CRITICAL** | スキャナー（ファイル検出・進捗計算） | 95% | コア機能、誤計算は致命的 |
| **CRITICAL** | WebSocket接続・配信 | 90% | リアルタイム更新の核心 |
| **HIGH** | REST API全エンドポイント | 90% | ユーザー向けインターフェース |
| **HIGH** | ダッシュボード表示 | 85% | メイン画面の正常動作 |
| **MEDIUM** | プロジェクト詳細画面 | 80% | サブ画面 |
| **LOW** | 進捗グラフ描画 | 70% | 視覚的補助 |

### 1.3 クリティカルパス テスト優先順位

WBS.jsonのクリティカルパスに基づくテスト優先順位：

```
T-001 → T-101 → T-102 → T-201 → T-202 → T-301 → T-302 → T-401 → T-402
                  ↓                                        ↓
          WBSパーサー ──────────────────────────────→ ユニットテスト
                                                     E2Eテスト
```

**最優先テスト対象**:
1. `wbs_parser.py` - 形式検出・パース処理
2. `scanner.py` - ファイル検出・進捗計算
3. `/api/projects` - プロジェクト一覧API
4. WebSocket `project_updated` イベント

---

## 2. ユニットテスト設計

### 2.1 バックエンドテスト

#### 2.1.1 WBSパーサーテスト (`tests/unit/test_wbs_parser.py`)

**テスト対象**: `backend/wbs_parser.py`

| テストID | テスト名 | 入力 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| WBS-001 | オブジェクト型形式検出 | オブジェクト型WBS.json | `format == 'object'` | CRITICAL |
| WBS-002 | 配列型形式検出 | 配列型WBS.json | `format == 'array'` | CRITICAL |
| WBS-003 | 不明形式検出 | 不正なWBS.json | `format == 'unknown'` または例外 | HIGH |
| WBS-004 | オブジェクト型パース | API入門講座形式 | 82トピック抽出、全フィールド正常 | CRITICAL |
| WBS-005 | 配列型パース | 生成AI入門講座形式 | トピック数一致 | CRITICAL |
| WBS-006 | 空WBS処理 | `{"phases": {}}` | 空リスト返却 | HIGH |
| WBS-007 | ネスト深い構造 | 複数phase、複数chapter | 全トピック抽出 | MEDIUM |
| WBS-008 | 必須フィールド欠損 | `base_name`なし | 適切なエラー | HIGH |
| WBS-009 | 日本語タイトル処理 | 日本語を含むWBS | 文字化けなし | MEDIUM |
| WBS-010 | 大規模WBS処理 | 200トピック | 処理時間 < 100ms | MEDIUM |

**テストデータ（モック）**:

```python
# オブジェクト型モック
MOCK_WBS_OBJECT = {
    "project": {"name": "API入門講座"},
    "phases": {
        "phase_2": {
            "name": "Phase 2: コンテンツ作成",
            "chapters": {
                "chapter_1": {
                    "name": "Chapter 1: API基礎",
                    "topics": [
                        {
                            "id": "topic_01_01",
                            "title": "APIの基礎",
                            "base_name": "01-01_APIの基礎"
                        },
                        {
                            "id": "topic_01_02",
                            "title": "リクエストとレスポンス",
                            "base_name": "01-02_リクエストとレスポンス"
                        }
                    ]
                }
            }
        }
    }
}

# 配列型モック
MOCK_WBS_ARRAY = {
    "project": {"name": "生成AI入門講座"},
    "phases": [
        {
            "id": "phase2",
            "name": "Phase 2: コンテンツ作成",
            "parts": [
                {
                    "id": "part1",
                    "chapters": [
                        {"id": "ch1", "name": "Chapter 1: AI概要", "topics": 4},
                        {"id": "ch2", "name": "Chapter 2: プロンプト", "topics": 6}
                    ]
                }
            ]
        }
    ]
}
```

**テスト実装例**:

```python
import pytest
from backend.wbs_parser import detect_wbs_format, ObjectFormatParser, ArrayFormatParser

class TestWBSFormatDetection:
    def test_detect_object_format(self):
        """WBS-001: オブジェクト型形式検出"""
        result = detect_wbs_format(MOCK_WBS_OBJECT)
        assert result == 'object'

    def test_detect_array_format(self):
        """WBS-002: 配列型形式検出"""
        result = detect_wbs_format(MOCK_WBS_ARRAY)
        assert result == 'array'

    def test_detect_unknown_format(self):
        """WBS-003: 不明形式検出"""
        invalid_wbs = {"phases": "invalid"}
        result = detect_wbs_format(invalid_wbs)
        assert result == 'unknown'

class TestObjectFormatParser:
    def test_parse_object_format(self):
        """WBS-004: オブジェクト型パース"""
        parser = ObjectFormatParser()
        topics = parser.parse(MOCK_WBS_OBJECT)

        assert len(topics) == 2
        assert topics[0].topic_id == "topic_01_01"
        assert topics[0].title == "APIの基礎"
        assert topics[0].base_name == "01-01_APIの基礎"
        assert topics[0].chapter == "Chapter 1: API基礎"

    def test_empty_wbs(self):
        """WBS-006: 空WBS処理"""
        parser = ObjectFormatParser()
        topics = parser.parse({"phases": {}})
        assert topics == []

class TestArrayFormatParser:
    def test_parse_array_format(self, tmp_path):
        """WBS-005: 配列型パース"""
        # content/フォルダをモック作成
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "01-01_AI概要.html").touch()
        (content_dir / "01-02_機械学習.html").touch()

        parser = ArrayFormatParser(content_dir)
        topics = parser.parse(MOCK_WBS_ARRAY)

        assert len(topics) >= 2  # ファイル数に基づく
```

---

#### 2.1.2 スキャナーテスト (`tests/unit/test_scanner.py`)

**テスト対象**: `backend/scanner.py`

| テストID | テスト名 | 入力 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| SCN-001 | HTML検出 | `.html`ファイル存在 | `has_html == True` | CRITICAL |
| SCN-002 | TXT検出 | `.txt`ファイル存在 | `has_txt == True` | CRITICAL |
| SCN-003 | MP3検出 | `.mp3`ファイル存在 | `has_mp3 == True` | CRITICAL |
| SCN-004 | ファイル不在検出 | ファイルなし | 全フラグ `False` | HIGH |
| SCN-005 | プレフィックス一致 | `01-01_*.html` | 正しくマッチ | HIGH |
| SCN-006 | ハッシュ計算 | 任意ファイル | xxhash値返却 | HIGH |
| SCN-007 | 変更検出 | ファイル更新 | `changed == True` | CRITICAL |
| SCN-008 | 変更なし検出 | 同一ファイル | `changed == False` | HIGH |
| SCN-009 | 進捗計算（完了） | HTML+TXT+MP3 | `progress == 100%` | CRITICAL |
| SCN-010 | 進捗計算（部分） | HTMLのみ | `progress == 40%` | CRITICAL |
| SCN-011 | 進捗計算（なし） | ファイルなし | `progress == 0%` | HIGH |
| SCN-012 | 大量ファイルスキャン | 200ファイル | 処理時間 < 1秒 | MEDIUM |
| SCN-013 | 並列スキャン | 複数プロジェクト | 正常完了 | HIGH |

**テスト実装例**:

```python
import pytest
from pathlib import Path
from backend.scanner import AsyncScanner, match_files, calculate_topic_progress

class TestFileDetection:
    @pytest.fixture
    def content_dir(self, tmp_path):
        """テスト用ディレクトリ作成"""
        content = tmp_path / "content"
        content.mkdir()
        return content

    def test_html_detection(self, content_dir):
        """SCN-001: HTML検出"""
        (content_dir / "01-01_APIの基礎.html").write_text("<html></html>")

        result = match_files("01-01_APIの基礎", content_dir)

        assert result['html'] is not None
        assert result['txt'] is None
        assert result['mp3'] is None

    def test_all_files_detection(self, content_dir):
        """SCN-009: 完了トピック検出"""
        (content_dir / "01-01_APIの基礎.html").write_text("<html></html>")
        (content_dir / "01-01_APIの基礎.txt").write_text("text")
        (content_dir / "01-01_APIの基礎.mp3").write_bytes(b'\x00')

        result = match_files("01-01_APIの基礎", content_dir)

        assert result['html'] is not None
        assert result['txt'] is not None
        assert result['mp3'] is not None

    def test_prefix_matching(self, content_dir):
        """SCN-005: プレフィックス一致"""
        (content_dir / "01-01_別のタイトル.html").write_text("<html></html>")

        result = match_files("01-01_APIの基礎", content_dir)

        # プレフィックス（01-01）で一致すべき
        assert result['html'] is not None

class TestProgressCalculation:
    def test_complete_progress(self):
        """SCN-009: 進捗計算（完了）"""
        topic = MockTopic(has_html=True, has_txt=True, has_mp3=True)
        progress = calculate_topic_progress(topic)
        assert progress == 100.0

    def test_partial_progress_html_only(self):
        """SCN-010: 進捗計算（HTMLのみ）"""
        topic = MockTopic(has_html=True, has_txt=False, has_mp3=False)
        progress = calculate_topic_progress(topic)
        assert progress == 40.0  # HTML 40%

    def test_partial_progress_html_txt(self):
        """進捗計算（HTML+TXT）"""
        topic = MockTopic(has_html=True, has_txt=True, has_mp3=False)
        progress = calculate_topic_progress(topic)
        assert progress == 70.0  # HTML 40% + TXT 30%

    def test_no_progress(self):
        """SCN-011: 進捗計算（なし）"""
        topic = MockTopic(has_html=False, has_txt=False, has_mp3=False)
        progress = calculate_topic_progress(topic)
        assert progress == 0.0

class TestHashAndChangeDetection:
    @pytest.fixture
    def scanner(self, tmp_path):
        return AsyncScanner(db=None, content_path=tmp_path)

    @pytest.mark.asyncio
    async def test_hash_calculation(self, scanner, tmp_path):
        """SCN-006: ハッシュ計算"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        file_info = await scanner._scan_file(test_file)

        assert file_info.hash is not None
        assert len(file_info.hash) == 16  # xxhash64 hex length

    @pytest.mark.asyncio
    async def test_change_detection(self, scanner, tmp_path):
        """SCN-007: 変更検出"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("initial content")

        # 初回スキャン
        file_info1 = await scanner._scan_file(test_file)
        assert file_info1.changed is True  # 初回は常にTrue

        # 変更なし再スキャン
        file_info2 = await scanner._scan_file(test_file)
        assert file_info2.changed is False

        # ファイル変更後スキャン
        test_file.write_text("modified content")
        file_info3 = await scanner._scan_file(test_file)
        assert file_info3.changed is True
```

---

#### 2.1.3 APIテスト (`tests/unit/test_api.py`)

**テスト対象**: `backend/routers/projects.py`, `backend/routers/scan.py`

| テストID | テスト名 | エンドポイント | 期待結果 | 優先度 |
|---------|---------|--------------|---------|--------|
| API-001 | プロジェクト一覧取得 | GET /api/projects | 200, 全プロジェクト返却 | CRITICAL |
| API-002 | プロジェクト詳細取得 | GET /api/projects/1 | 200, 詳細データ返却 | HIGH |
| API-003 | 存在しないプロジェクト | GET /api/projects/999 | 404, PROJECT_NOT_FOUND | HIGH |
| API-004 | トピック一覧取得 | GET /api/projects/1/topics | 200, トピック配列返却 | HIGH |
| API-005 | 全体統計取得 | GET /api/stats | 200, 統計データ返却 | MEDIUM |
| API-006 | 手動スキャン実行 | POST /api/scan | 202, スキャン開始 | HIGH |
| API-007 | スキャン中の重複実行 | POST /api/scan (2回目) | 409, SCAN_IN_PROGRESS | MEDIUM |
| API-008 | レスポンス形式検証 | GET /api/projects | JSON Schema準拠 | HIGH |
| API-009 | 応答時間検証 | GET /api/projects | < 50ms | MEDIUM |

**テスト実装例**:

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import app

class TestProjectsAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_projects(self, client):
        """API-001: プロジェクト一覧取得"""
        response = client.get("/api/projects")

        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "total" in data
        assert isinstance(data["projects"], list)

    def test_get_project_detail(self, client):
        """API-002: プロジェクト詳細取得"""
        response = client.get("/api/projects/1")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "total_topics" in data

    def test_get_nonexistent_project(self, client):
        """API-003: 存在しないプロジェクト"""
        response = client.get("/api/projects/999")

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "PROJECT_NOT_FOUND"

    def test_get_topics(self, client):
        """API-004: トピック一覧取得"""
        response = client.get("/api/projects/1/topics")

        assert response.status_code == 200
        data = response.json()
        assert "topics" in data
        assert "summary" in data
        assert isinstance(data["topics"], list)

class TestScanAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_trigger_scan(self, client):
        """API-006: 手動スキャン実行"""
        response = client.post("/api/scan", json={"scan_type": "full"})

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert "scan_id" in data

class TestResponseSchema:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_projects_response_schema(self, client):
        """API-008: レスポンス形式検証"""
        response = client.get("/api/projects")
        data = response.json()

        # 必須フィールド検証
        for project in data["projects"]:
            assert "id" in project
            assert "name" in project
            assert "total_topics" in project
            assert "completed_topics" in project
            assert "progress" in project
            assert 0 <= project["progress"] <= 100
```

---

#### 2.1.4 WebSocketテスト (`tests/unit/test_websocket.py`)

**テスト対象**: `backend/websocket.py`

| テストID | テスト名 | 入力 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| WS-001 | 接続確立 | WebSocket接続 | connected イベント受信 | CRITICAL |
| WS-002 | 切断処理 | 接続クローズ | 接続プールから削除 | HIGH |
| WS-003 | ブロードキャスト | project_updated | 全クライアント受信 | CRITICAL |
| WS-004 | 個別送信 | 特定クライアント | 指定クライアントのみ受信 | MEDIUM |
| WS-005 | 不正メッセージ | 不正JSON | エラー処理、接続維持 | MEDIUM |
| WS-006 | 接続数制限 | 51接続目 | 拒否または待機 | LOW |

---

### 2.2 フロントエンドテスト

#### 2.2.1 コンポーネントテスト（Vue.js）

| テストID | コンポーネント | テスト内容 | 期待結果 | 優先度 |
|---------|--------------|----------|---------|--------|
| FE-001 | Dashboard | 初期表示 | サマリーカード4つ表示 | CRITICAL |
| FE-002 | Dashboard | プロジェクトカード表示 | 全プロジェクトカード表示 | CRITICAL |
| FE-003 | ProjectCard | 進捗バー表示 | 正しい色分け表示 | HIGH |
| FE-004 | ProjectCard | クリック | 詳細画面遷移 | HIGH |
| FE-005 | ProjectDetail | トピック一覧表示 | 全トピック表示 | HIGH |
| FE-006 | ProjectDetail | フィルタリング | 条件に応じた絞り込み | MEDIUM |
| FE-007 | ProgressChart | グラフ描画 | Chart.js正常描画 | MEDIUM |
| FE-008 | WebSocketService | 再接続 | 5回まで再接続試行 | HIGH |

---

## 3. 統合テスト設計

### 3.1 API + データベース連携 (`tests/integration/test_api_db.py`)

| テストID | シナリオ | 手順 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| INT-001 | プロジェクト登録→取得 | 1. DBにプロジェクト挿入<br>2. API取得 | 挿入データと一致 | CRITICAL |
| INT-002 | トピック更新→反映 | 1. トピック更新<br>2. API取得 | 更新データ反映 | HIGH |
| INT-003 | スキャン→DB更新 | 1. スキャン実行<br>2. DB確認 | 正しく更新 | CRITICAL |
| INT-004 | トランザクション | 1. 大量更新<br>2. エラー発生 | ロールバック | HIGH |

**テスト実装例**:

```python
import pytest
from backend.database import Database
from backend.scanner import AsyncScanner

class TestAPIDBIntegration:
    @pytest.fixture
    async def db(self, tmp_path):
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.initialize()
        return db

    @pytest.mark.asyncio
    async def test_project_insert_and_retrieve(self, db, client):
        """INT-001: プロジェクト登録→取得"""
        # DBに直接挿入
        await db.execute(
            "INSERT INTO projects (name, path, total_topics) VALUES (?, ?, ?)",
            ("テストプロジェクト", "/test/path", 10)
        )

        # API経由で取得
        response = client.get("/api/projects")
        data = response.json()

        project = next(p for p in data["projects"] if p["name"] == "テストプロジェクト")
        assert project["total_topics"] == 10

    @pytest.mark.asyncio
    async def test_scan_updates_db(self, db, tmp_path):
        """INT-003: スキャン→DB更新"""
        # テスト用ファイル作成
        content_dir = tmp_path / "project" / "content"
        content_dir.mkdir(parents=True)
        (content_dir / "01-01_test.html").write_text("<html></html>")

        scanner = AsyncScanner(db, content_dir)
        await scanner.scan_project(tmp_path / "project")

        # DB確認
        topics = await db.fetch_all("SELECT * FROM topics")
        assert len(topics) > 0
        assert any(t["has_html"] == 1 for t in topics)
```

---

### 3.2 WebSocket接続テスト (`tests/integration/test_websocket.py`)

| テストID | シナリオ | 手順 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| INT-WS-001 | 接続→更新受信 | 1. WS接続<br>2. スキャン実行<br>3. メッセージ受信 | project_updated受信 | CRITICAL |
| INT-WS-002 | 複数クライアント | 1. 3クライアント接続<br>2. 更新発生 | 全クライアント受信 | HIGH |
| INT-WS-003 | 再接続動作 | 1. 接続<br>2. 切断<br>3. 再接続 | 自動再接続成功 | HIGH |

**テスト実装例**:

```python
import pytest
import asyncio
import websockets

class TestWebSocketIntegration:
    @pytest.mark.asyncio
    async def test_realtime_update(self, server):
        """INT-WS-001: 接続→更新受信"""
        received_messages = []

        async with websockets.connect("ws://localhost:8000/ws") as ws:
            # 接続確認
            msg = await ws.recv()
            assert "connected" in msg

            # スキャンをトリガー（別タスク）
            asyncio.create_task(trigger_scan())

            # 更新メッセージ待機
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                received_messages.append(msg)
            except asyncio.TimeoutError:
                pass

        assert any("project_updated" in m for m in received_messages)
```

---

### 3.3 スキャナー + ファイルシステム (`tests/integration/test_scanner_fs.py`)

| テストID | シナリオ | 手順 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| INT-FS-001 | 実フォルダスキャン | 1. テストフォルダ作成<br>2. スキャン実行 | 全ファイル検出 | CRITICAL |
| INT-FS-002 | ファイル追加検出 | 1. ウォッチャー起動<br>2. ファイル追加 | イベント検出 | CRITICAL |
| INT-FS-003 | デバウンス動作 | 1. 連続ファイル変更<br>2. イベント確認 | 1回のイベントに集約 | HIGH |

---

## 4. E2Eテスト設計

### 4.1 ダッシュボード表示シナリオ (`tests/e2e/test_dashboard.py`)

| テストID | シナリオ | 操作 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| E2E-001 | 初期表示 | アプリ起動、ダッシュボードアクセス | 全プロジェクトカード表示 | CRITICAL |
| E2E-002 | サマリー表示 | ダッシュボードアクセス | 4つのサマリーカード表示 | CRITICAL |
| E2E-003 | 進捗バー表示 | カード確認 | 色分け進捗バー表示 | HIGH |
| E2E-004 | WS接続状態 | ダッシュボード確認 | 緑●インジケーター表示 | HIGH |

**Playwrightテスト実装例**:

```python
import pytest
from playwright.sync_api import Page, expect

class TestDashboardE2E:
    def test_initial_display(self, page: Page):
        """E2E-001: 初期表示"""
        page.goto("http://localhost:8000")

        # プロジェクトカードが表示されるまで待機
        page.wait_for_selector(".project-card")

        # カードが複数表示されていることを確認
        cards = page.locator(".project-card")
        expect(cards).to_have_count_greater_than(0)

    def test_summary_cards(self, page: Page):
        """E2E-002: サマリー表示"""
        page.goto("http://localhost:8000")

        # 4つのサマリーカード確認
        expect(page.locator("text=全プロジェクト")).to_be_visible()
        expect(page.locator("text=全体進捗")).to_be_visible()
        expect(page.locator("text=完了トピック")).to_be_visible()
        expect(page.locator("text=最終更新")).to_be_visible()

    def test_websocket_indicator(self, page: Page):
        """E2E-004: WS接続状態"""
        page.goto("http://localhost:8000")

        # 接続インジケーターが緑色であることを確認
        indicator = page.locator(".ws-indicator")
        expect(indicator).to_have_class(/connected/)
```

---

### 4.2 プロジェクト詳細表示シナリオ (`tests/e2e/test_project_detail.py`)

| テストID | シナリオ | 操作 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| E2E-101 | 詳細画面遷移 | プロジェクトカードクリック | 詳細画面表示 | HIGH |
| E2E-102 | トピック一覧表示 | 詳細画面確認 | 全トピック表示（仮想スクロール） | HIGH |
| E2E-103 | フィルタ動作 | フィルタ選択 | 絞り込み結果表示 | MEDIUM |
| E2E-104 | 戻るボタン | 戻るボタンクリック | ダッシュボードに戻る | MEDIUM |

---

### 4.3 手動スキャンシナリオ (`tests/e2e/test_manual_scan.py`)

| テストID | シナリオ | 操作 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| E2E-201 | スキャン実行 | スキャンボタンクリック | ローディング表示→完了 | HIGH |
| E2E-202 | スキャン結果反映 | スキャン完了後 | 進捗値更新 | CRITICAL |

---

### 4.4 リアルタイム更新シナリオ (`tests/e2e/test_realtime.py`)

| テストID | シナリオ | 操作 | 期待結果 | 優先度 |
|---------|---------|------|---------|--------|
| E2E-301 | ファイル追加→反映 | 外部でHTMLファイル追加 | 5秒以内にUI更新 | CRITICAL |
| E2E-302 | ファイル削除→反映 | 外部でファイル削除 | 5秒以内にUI更新 | HIGH |
| E2E-303 | 複数変更一括 | 複数ファイル同時追加 | 1回の更新で反映 | MEDIUM |

**テスト実装例**:

```python
import pytest
from pathlib import Path
import time

class TestRealtimeE2E:
    def test_file_add_reflects_in_ui(self, page, test_content_dir: Path):
        """E2E-301: ファイル追加→反映"""
        page.goto("http://localhost:8000")

        # 初期状態の進捗を記録
        initial_progress = page.locator(".overall-progress").text_content()

        # 外部でファイル追加
        new_file = test_content_dir / "99-99_新規トピック.html"
        new_file.write_text("<html><body>新規コンテンツ</body></html>")

        # UI更新を待機（最大5秒）
        page.wait_for_function(
            f"""() => {{
                const el = document.querySelector('.overall-progress');
                return el && el.textContent !== '{initial_progress}';
            }}""",
            timeout=5000
        )

        # 更新されたことを確認
        new_progress = page.locator(".overall-progress").text_content()
        assert new_progress != initial_progress
```

---

## 5. テストデータ

### 5.1 モックWBS.jsonファイル

#### オブジェクト型（完全版）

```json
{
  "project": {
    "name": "テストプロジェクト（オブジェクト型）"
  },
  "phases": {
    "phase_2": {
      "name": "Phase 2: コンテンツ作成",
      "chapters": {
        "chapter_1": {
          "name": "Chapter 1: 基礎",
          "topics": [
            {
              "id": "topic_01_01",
              "title": "トピック1-1",
              "base_name": "01-01_トピック1-1"
            },
            {
              "id": "topic_01_02",
              "title": "トピック1-2",
              "base_name": "01-02_トピック1-2"
            },
            {
              "id": "topic_01_03",
              "title": "トピック1-3",
              "base_name": "01-03_トピック1-3"
            }
          ]
        },
        "chapter_2": {
          "name": "Chapter 2: 応用",
          "topics": [
            {
              "id": "topic_02_01",
              "title": "トピック2-1",
              "base_name": "02-01_トピック2-1"
            },
            {
              "id": "topic_02_02",
              "title": "トピック2-2",
              "base_name": "02-02_トピック2-2"
            }
          ]
        }
      }
    }
  }
}
```

#### 配列型（完全版）

```json
{
  "project": {
    "name": "テストプロジェクト（配列型）"
  },
  "phases": [
    {
      "id": "phase2",
      "name": "Phase 2: コンテンツ作成",
      "parts": [
        {
          "id": "part1",
          "chapters": [
            {
              "id": "ch1",
              "name": "Chapter 1: 基礎",
              "topics": 3
            },
            {
              "id": "ch2",
              "name": "Chapter 2: 応用",
              "topics": 2
            }
          ]
        }
      ]
    }
  ]
}
```

### 5.2 モックディレクトリ構造

```
test_project/
├── WBS.json
└── content/
    ├── 01-01_トピック1-1.html     ← 完了トピック
    ├── 01-01_トピック1-1.txt
    ├── 01-01_トピック1-1.mp3
    ├── 01-02_トピック1-2.html     ← 進行中トピック
    ├── 01-02_トピック1-2.txt
    ├── 01-03_トピック1-3.html     ← HTMLのみ
    ├── 02-01_トピック2-1.html     ← 完了トピック
    ├── 02-01_トピック2-1.txt
    ├── 02-01_トピック2-1.mp3
    └── (02-02は未着手 - ファイルなし)
```

### 5.3 期待される進捗計算結果

| トピック | HTML | TXT | MP3 | ステータス | 進捗率 |
|---------|------|-----|-----|----------|-------|
| 01-01 | Yes | Yes | Yes | completed | 100% |
| 01-02 | Yes | Yes | No | in_progress | 70% |
| 01-03 | Yes | No | No | in_progress | 40% |
| 02-01 | Yes | Yes | Yes | completed | 100% |
| 02-02 | No | No | No | not_started | 0% |

**プロジェクト全体**:
- 全トピック: 5
- 完了: 2
- 進行中: 2
- 未着手: 1
- 全体進捗率: (4*40 + 3*30 + 3*30) / 5 = 62%

---

## 6. カバレッジ目標

### 6.1 全体目標

| カテゴリ | 目標 | 最低限 |
|---------|-----|-------|
| 全体 | 80% | 70% |
| クリティカルパス | 100% | 95% |
| ビジネスロジック | 90% | 85% |

### 6.2 モジュール別目標

| モジュール | 目標 | 理由 |
|----------|-----|------|
| `wbs_parser.py` | 95% | 形式検出・パースはコア機能 |
| `scanner.py` | 90% | ファイル検出・進捗計算は重要 |
| `database.py` | 85% | CRUD操作のカバー |
| `websocket.py` | 85% | リアルタイム更新の核心 |
| `routers/projects.py` | 90% | 主要API |
| `routers/scan.py` | 85% | スキャンAPI |
| `frontend/*.js` | 75% | UIコンポーネント |

### 6.3 カバレッジ計測コマンド

```bash
# バックエンドカバレッジ計測
pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing

# カバレッジレポート確認
open htmlcov/index.html
```

---

## 7. テスト実行計画

### 7.1 テスト実行順序

```
1. ユニットテスト（CI/毎コミット）
   ├── test_wbs_parser.py
   ├── test_scanner.py
   ├── test_api.py
   └── test_websocket.py

2. 統合テスト（CI/毎PR）
   ├── test_api_db.py
   ├── test_websocket.py
   └── test_scanner_fs.py

3. E2Eテスト（CI/マージ前）
   ├── test_dashboard.py
   ├── test_project_detail.py
   ├── test_manual_scan.py
   └── test_realtime.py
```

### 7.2 テスト環境

| 環境 | 用途 | データベース |
|-----|------|-------------|
| 開発 | ローカルテスト | SQLite (メモリ) |
| CI | 自動テスト | SQLite (一時ファイル) |
| E2E | 画面テスト | SQLite (テストデータ) |

### 7.3 CI設定例（GitHub Actions）

```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/unit/ --cov=backend --cov-fail-under=80

  integration-test:
    runs-on: ubuntu-latest
    needs: unit-test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: pytest tests/integration/

  e2e-test:
    runs-on: ubuntu-latest
    needs: integration-test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: pip install playwright && playwright install
      - run: |
          python -m backend.main &
          sleep 5
          pytest tests/e2e/
```

---

## 8. 付録

### 8.1 テストユーティリティ

```python
# tests/conftest.py
import pytest
from pathlib import Path
import tempfile
import shutil

@pytest.fixture
def test_project_dir():
    """テスト用プロジェクトディレクトリを作成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / "test_project"
        project_dir.mkdir()

        # WBS.json作成
        wbs_path = project_dir / "WBS.json"
        wbs_path.write_text('{"phases": {}}')

        # content/作成
        content_dir = project_dir / "content"
        content_dir.mkdir()

        yield project_dir

@pytest.fixture
def mock_topic():
    """モックトピック生成"""
    class MockTopic:
        def __init__(self, has_html=False, has_txt=False, has_mp3=False):
            self.has_html = has_html
            self.has_txt = has_txt
            self.has_mp3 = has_mp3

    return MockTopic
```

### 8.2 テスト命名規則

| パターン | 例 | 説明 |
|---------|---|------|
| `test_<機能>_<条件>_<期待結果>` | `test_parse_object_format_returns_topics` | 詳細な命名 |
| `test_<テストID>_<説明>` | `test_WBS001_object_format_detection` | テストID参照可能 |

### 8.3 テストタグ

```python
# タグ付きテスト
@pytest.mark.critical
def test_critical_function():
    pass

@pytest.mark.slow
def test_performance():
    pass

# 実行時にタグでフィルタ
# pytest -m critical  # クリティカルテストのみ
# pytest -m "not slow"  # 遅いテスト以外
```

---

*このテスト設計書は REQUIREMENTS.md, ARCHITECTURE.md, SPEC.md, WBS.json に基づいて作成されました。*
