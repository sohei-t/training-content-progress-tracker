# 研修コンテンツ進捗トラッカー - 詳細仕様書 (SPEC.md)

> **バージョン**: 1.0
> **作成日**: 2026-02-03
> **アプローチ**: 革新的（イベント駆動・リアルタイム・高パフォーマンス）

---

## 1. 機能一覧（優先度付き）

### 1.1 MUST機能（必須）

| ID | 機能名 | 説明 | 完了基準 |
|----|--------|------|---------|
| F-001 | インテリジェントスキャンシステム | 差分検出による高速ファイルスキャン | 初回 < 3秒、差分 < 100ms |
| F-002 | WebSocketリアルタイム更新 | サーバープッシュによる即時UI更新 | 遅延 < 50ms |
| F-003 | ダッシュボード表示 | 全プロジェクトの進捗サマリー表示 | FCP < 1.0秒 |
| F-004 | プロジェクト詳細画面 | トピック別進捗の詳細表示 | 82トピック表示で60fps維持 |
| F-005 | WBS両形式対応パーサー | オブジェクト型・配列型の自動検出・解析 | 13プロジェクト全対応 |
| F-006 | 手動スキャントリガー | ボタンによる即時フルスキャン | クリック後3秒以内に反映 |
| F-007 | 複数プロジェクト一括比較 | 並列表示モードで全プロジェクト俯瞰 | カード形式で一覧表示 |

### 1.2 SHOULD機能（推奨）

| ID | 機能名 | 説明 | 完了基準 |
|----|--------|------|---------|
| F-101 | 進捗予測エンジン | 過去の作成ペースから完了日を予測 | 信頼区間付き予測表示 |
| F-102 | PWA対応 | オフラインキャッシュ、ホーム画面追加 | Lighthouse PWAスコア70+ |
| F-103 | ライブプレビュー | 作成中HTMLファイルのプレビュー表示 | iframe内表示 |
| F-104 | フィルタリング機能 | 完了/進行中/未着手でトピック絞り込み | 即時フィルタ適用 |

### 1.3 COULD機能（あれば良い）

| ID | 機能名 | 説明 | 完了基準 |
|----|--------|------|---------|
| F-201 | AI推奨機能 | 次に作成すべきコンテンツの提案 | 優先度スコア表示 |
| F-202 | エクスポート機能 | CSV/JSON形式での進捗データ出力 | ダウンロードボタン |
| F-203 | プッシュ通知 | トピック完了時のデスクトップ通知 | Web Notifications API |
| F-204 | ダークモード | UIテーマ切り替え | LocalStorage保存 |

---

## 2. 画面仕様

### 2.1 ダッシュボード画面（メイン画面）

#### 2.1.1 レイアウト構成

```
┌─────────────────────────────────────────────────────────────────┐
│                         ヘッダーバー                              │
│  [ロゴ] 研修コンテンツ進捗トラッカー         [WS状態] [スキャン]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ │
│  │  全プロジェクト │ │  全体進捗率   │ │  完了トピック  │ │ 最終更新  │ │
│  │      13       │ │    45.2%     │ │  320 / 708   │ │ 14:23    │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────┘ │
│                                                                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  プロジェクト一覧                              [フィルタ ▼]  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│  │ API入門講座  │ │ GCP入門講座  │ │ Linux入門   │  ...           │
│  │             │ │             │ │             │                 │
│  │ ████████░░ │ │ ██████░░░░ │ │ ████░░░░░░ │                 │
│  │ 82% (67/82) │ │ 60% (48/80) │ │ 40% (32/80) │                 │
│  │             │ │             │ │             │                 │
│  │ [詳細] [📁] │ │ [詳細] [📁] │ │ [詳細] [📁] │                 │
│  └─────────────┘ └─────────────┘ └─────────────┘                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.1.2 ヘッダーバー仕様

| 要素 | 表示内容 | 動作 |
|-----|---------|------|
| ロゴ | アプリ名「研修コンテンツ進捗トラッカー」 | クリックでダッシュボードに戻る |
| WS状態インジケーター | 緑●（接続中）/ 赤●（切断） | ホバーで接続状態詳細表示 |
| スキャンボタン | 「手動スキャン」/ 「スキャン中...」 | クリックで全プロジェクト再スキャン |

#### 2.1.3 サマリーカード仕様

| カード | 表示値 | 計算ロジック |
|-------|--------|-------------|
| 全プロジェクト | 整数 | `projects.length` |
| 全体進捗率 | 小数点1桁 + % | `(sum(completed_topics) / sum(total_topics)) * 100` |
| 完了トピック | 完了数 / 全数 | `sum(completed_topics)` / `sum(total_topics)` |
| 最終更新 | HH:MM | `max(projects.last_scanned_at)` |

#### 2.1.4 プロジェクトカード仕様

```typescript
interface ProjectCard {
  name: string;           // プロジェクト名
  progress: number;       // 進捗率（0-100）
  completedTopics: number;
  totalTopics: number;
  lastUpdated: Date;
  progressBar: {
    html: number;         // HTML完了率（緑）
    txt: number;          // TXT完了率（青）
    mp3: number;          // MP3完了率（オレンジ）
  };
}
```

**プログレスバー色分け**:
- HTML完了: `#10B981` (green-500)
- TXT完了: `#3B82F6` (blue-500)
- MP3完了: `#F59E0B` (amber-500)
- 未完了: `#E5E7EB` (gray-200)

#### 2.1.5 操作仕様

| 操作 | ターゲット | 動作 |
|-----|----------|------|
| カードクリック | プロジェクトカード全体 | プロジェクト詳細画面へ遷移 |
| 詳細ボタン | [詳細] | プロジェクト詳細画面へ遷移 |
| フォルダボタン | [📁] | OSのファイルマネージャーでフォルダを開く |
| スキャンボタン | ヘッダー | 全プロジェクト再スキャン（ローディング表示） |

---

### 2.2 プロジェクト詳細画面

#### 2.2.1 レイアウト構成

```
┌─────────────────────────────────────────────────────────────────┐
│  [← 戻る]  API入門講座                           [🔄] [📁]      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐ ┌─────────────────────────────────────────┤
│  │  サイドバー        │ │  メインコンテンツ                        │
│  │                  │ │                                         │
│  │  ▼ Chapter 1    │ │  ┌─────────────────────────────────────┐│
│  │    □ Topic 1-1  │ │  │ 01-01_APIの基礎                      ││
│  │    ☑ Topic 1-2  │ │  │ [✓HTML] [✓TXT] [□MP3]              ││
│  │    □ Topic 1-3  │ │  │ 更新: 2026-02-03 14:20              ││
│  │                  │ │  └─────────────────────────────────────┘│
│  │  ▼ Chapter 2    │ │  ┌─────────────────────────────────────┐│
│  │    ☑ Topic 2-1  │ │  │ 01-02_リクエストとレスポンス          ││
│  │    ☑ Topic 2-2  │ │  │ [✓HTML] [✓TXT] [✓MP3]              ││
│  │                  │ │  │ 更新: 2026-02-02 10:15              ││
│  │  ▶ Chapter 3    │ │  └─────────────────────────────────────┘│
│  │                  │ │                                         │
│  │  ────────────── │ │  ... (仮想スクロール)                    │
│  │  フィルタ:       │ │                                         │
│  │  [全て ▼]       │ │                                         │
│  │                  │ │                                         │
│  └──────────────────┘ └─────────────────────────────────────────┘
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.2.2 サイドバー仕様

| 要素 | 動作 |
|-----|------|
| チャプター（折りたたみ） | クリックで展開/折りたたみ |
| トピックリスト | クリックでメインエリアにスクロール |
| チェックボックス | 完了状態を視覚表示（読み取り専用） |
| フィルタドロップダウン | 全て/完了/進行中/未着手 で絞り込み |

#### 2.2.3 トピックカード仕様

```typescript
interface TopicCard {
  id: string;             // トピックID（例: "01-01"）
  title: string;          // トピックタイトル
  baseName: string;       // ファイル名ベース
  hasHtml: boolean;       // HTML存在フラグ
  hasTxt: boolean;        // TXT存在フラグ
  hasMp3: boolean;        // MP3存在フラグ
  updatedAt: Date;        // 最終更新日時
  status: 'completed' | 'in_progress' | 'not_started';
}
```

**進捗アイコン表示**:
| 状態 | HTML | TXT | MP3 |
|-----|------|-----|-----|
| 存在 | ✓（緑） | ✓（青） | ✓（オレンジ） |
| 未作成 | □（グレー） | □（グレー） | □（グレー） |

**ステータス判定ロジック**:
```python
def calculate_status(topic):
    if topic.has_html and topic.has_txt and topic.has_mp3:
        return 'completed'
    elif topic.has_html or topic.has_txt or topic.has_mp3:
        return 'in_progress'
    else:
        return 'not_started'
```

#### 2.2.4 仮想スクロール仕様

| 項目 | 仕様値 |
|-----|-------|
| 表示アイテム数 | 可視領域 + バッファ20件 |
| アイテム高さ | 80px固定 |
| スクロール感度 | ネイティブ |
| リサイクル方式 | DOM要素再利用 |

---

## 3. API仕様

### 3.1 エンドポイント一覧

| Method | Path | 説明 | 認証 |
|--------|------|------|-----|
| GET | `/api/projects` | プロジェクト一覧取得 | 不要 |
| GET | `/api/projects/{id}` | プロジェクト詳細取得 | 不要 |
| GET | `/api/projects/{id}/topics` | トピック一覧取得 | 不要 |
| POST | `/api/scan` | 手動スキャン実行 | 不要 |
| GET | `/api/stats` | 全体統計取得 | 不要 |
| WS | `/ws` | WebSocket接続 | 不要 |

### 3.2 レスポンス形式（JSON Schema）

#### GET `/api/projects` - プロジェクト一覧

**Response 200**:
```json
{
  "projects": [
    {
      "id": 1,
      "name": "API入門講座",
      "path": "/Users/sohei/Desktop/Learning-Curricula/API入門講座",
      "wbs_format": "object",
      "total_topics": 82,
      "completed_topics": 67,
      "progress": 81.7,
      "progress_detail": {
        "html": 75,
        "txt": 82,
        "mp3": 67
      },
      "last_scanned_at": "2026-02-03T14:23:45Z",
      "created_at": "2026-02-01T10:00:00Z",
      "updated_at": "2026-02-03T14:23:45Z"
    }
  ],
  "total": 13,
  "last_updated": "2026-02-03T14:23:45Z"
}
```

**JSON Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "projects": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name", "total_topics", "completed_topics", "progress"],
        "properties": {
          "id": { "type": "integer" },
          "name": { "type": "string" },
          "path": { "type": "string" },
          "wbs_format": { "enum": ["object", "array", null] },
          "total_topics": { "type": "integer", "minimum": 0 },
          "completed_topics": { "type": "integer", "minimum": 0 },
          "progress": { "type": "number", "minimum": 0, "maximum": 100 },
          "progress_detail": {
            "type": "object",
            "properties": {
              "html": { "type": "integer" },
              "txt": { "type": "integer" },
              "mp3": { "type": "integer" }
            }
          },
          "last_scanned_at": { "type": "string", "format": "date-time" }
        }
      }
    },
    "total": { "type": "integer" },
    "last_updated": { "type": "string", "format": "date-time" }
  }
}
```

#### GET `/api/projects/{id}/topics` - トピック一覧

**Response 200**:
```json
{
  "project_id": 1,
  "project_name": "API入門講座",
  "topics": [
    {
      "id": 1,
      "topic_id": "01-01",
      "chapter": "Chapter 1: API基礎",
      "title": "APIの基礎",
      "base_name": "01-01_APIの基礎",
      "has_html": true,
      "has_txt": true,
      "has_mp3": false,
      "status": "in_progress",
      "updated_at": "2026-02-03T14:20:00Z"
    }
  ],
  "summary": {
    "total": 82,
    "completed": 67,
    "in_progress": 10,
    "not_started": 5
  }
}
```

#### POST `/api/scan` - 手動スキャン

**Request Body**:
```json
{
  "project_id": null,
  "scan_type": "full"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|---|-----|------|
| project_id | integer/null | No | nullで全プロジェクト |
| scan_type | string | No | "full" or "diff"（デフォルト: "full"） |

**Response 202**:
```json
{
  "status": "accepted",
  "scan_id": "scan_20260203_142345",
  "message": "スキャンを開始しました"
}
```

### 3.3 エラーレスポンス

**共通エラー形式**:
```json
{
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "指定されたプロジェクトが見つかりません",
    "details": {
      "project_id": 999
    }
  }
}
```

**エラーコード一覧**:
| コード | HTTPステータス | 説明 |
|-------|--------------|------|
| PROJECT_NOT_FOUND | 404 | プロジェクトが存在しない |
| SCAN_IN_PROGRESS | 409 | 既にスキャン実行中 |
| INVALID_PATH | 400 | パスが無効 |
| WBS_PARSE_ERROR | 422 | WBS.jsonのパースエラー |
| INTERNAL_ERROR | 500 | 内部エラー |

### 3.4 WebSocketイベント仕様

**接続URL**: `ws://localhost:8000/ws`

**サーバー → クライアント イベント**:

| イベント | ペイロード | 発火タイミング |
|---------|----------|--------------|
| `connected` | `{ client_id: string }` | WebSocket接続確立時 |
| `project_updated` | `{ project: Project }` | プロジェクト情報更新時 |
| `topic_changed` | `{ project_id, topic: Topic }` | トピック状態変更時 |
| `scan_started` | `{ scan_id, project_id?, type }` | スキャン開始時 |
| `scan_progress` | `{ scan_id, progress, current }` | スキャン進捗更新時 |
| `scan_completed` | `{ scan_id, result }` | スキャン完了時 |

**メッセージ形式**:
```json
{
  "event": "project_updated",
  "data": {
    "project": { ... }
  },
  "timestamp": "2026-02-03T14:23:45.123Z"
}
```

---

## 4. データモデル詳細

### 4.1 テーブル定義

#### projects テーブル

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    wbs_format TEXT CHECK(wbs_format IN ('object', 'array', NULL)),
    total_topics INTEGER DEFAULT 0,
    completed_topics INTEGER DEFAULT 0,
    html_count INTEGER DEFAULT 0,
    txt_count INTEGER DEFAULT 0,
    mp3_count INTEGER DEFAULT 0,
    last_scanned_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- インデックス
CREATE INDEX idx_projects_name ON projects(name);
CREATE INDEX idx_projects_updated ON projects(updated_at);
```

| カラム | 型 | 制約 | 説明 |
|-------|---|-----|------|
| id | INTEGER | PK, AUTO | 主キー |
| name | TEXT | NOT NULL, UNIQUE | プロジェクト名 |
| path | TEXT | NOT NULL | フォルダパス |
| wbs_format | TEXT | CHECK | "object" / "array" / NULL |
| total_topics | INTEGER | DEFAULT 0 | 全トピック数 |
| completed_topics | INTEGER | DEFAULT 0 | 完了トピック数 |
| html_count | INTEGER | DEFAULT 0 | HTML完了数 |
| txt_count | INTEGER | DEFAULT 0 | TXT完了数 |
| mp3_count | INTEGER | DEFAULT 0 | MP3完了数 |
| last_scanned_at | TEXT | - | 最終スキャン日時 |
| created_at | TEXT | DEFAULT now | 作成日時 |
| updated_at | TEXT | DEFAULT now | 更新日時 |

#### topics テーブル

```sql
CREATE TABLE topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter TEXT,
    topic_id TEXT,
    title TEXT,
    base_name TEXT NOT NULL,
    has_html INTEGER DEFAULT 0 CHECK(has_html IN (0, 1)),
    has_txt INTEGER DEFAULT 0 CHECK(has_txt IN (0, 1)),
    has_mp3 INTEGER DEFAULT 0 CHECK(has_mp3 IN (0, 1)),
    html_hash TEXT,
    txt_hash TEXT,
    mp3_hash TEXT,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(project_id, base_name)
);

-- インデックス
CREATE INDEX idx_topics_project ON topics(project_id);
CREATE INDEX idx_topics_base_name ON topics(project_id, base_name);
CREATE INDEX idx_topics_chapter ON topics(project_id, chapter);
```

| カラム | 型 | 制約 | 説明 |
|-------|---|-----|------|
| id | INTEGER | PK, AUTO | 主キー |
| project_id | INTEGER | FK, NOT NULL | プロジェクトID |
| chapter | TEXT | - | チャプター名 |
| topic_id | TEXT | - | トピックID（例: "01-01"） |
| title | TEXT | - | トピックタイトル |
| base_name | TEXT | NOT NULL | ファイル名ベース |
| has_html | INTEGER | CHECK 0/1 | HTML存在フラグ |
| has_txt | INTEGER | CHECK 0/1 | TXT存在フラグ |
| has_mp3 | INTEGER | CHECK 0/1 | MP3存在フラグ |
| html_hash | TEXT | - | HTMLファイルハッシュ |
| txt_hash | TEXT | - | TXTファイルハッシュ |
| mp3_hash | TEXT | - | MP3ファイルハッシュ |
| updated_at | TEXT | DEFAULT now | 更新日時 |

#### scan_history テーブル

```sql
CREATE TABLE scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT UNIQUE NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    scan_type TEXT NOT NULL CHECK(scan_type IN ('full', 'diff', 'watch')),
    project_id INTEGER REFERENCES projects(id),
    projects_scanned INTEGER DEFAULT 0,
    files_scanned INTEGER DEFAULT 0,
    changes_detected INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed')),
    error_message TEXT
);

-- インデックス
CREATE INDEX idx_scan_history_started ON scan_history(started_at);
```

### 4.2 ER図

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   projects   │       │    topics    │       │ scan_history │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │───────│ id (PK)      │       │ id (PK)      │
│ name         │   1:N │ project_id   │       │ scan_id      │
│ path         │       │ chapter      │       │ started_at   │
│ wbs_format   │       │ topic_id     │       │ completed_at │
│ total_topics │       │ title        │       │ scan_type    │
│ completed    │       │ base_name    │       │ project_id   │──┐
│ html_count   │       │ has_html     │       │ projects_    │  │
│ txt_count    │       │ has_txt      │       │   scanned    │  │
│ mp3_count    │       │ has_mp3      │       │ files_       │  │
│ last_scanned │       │ html_hash    │       │   scanned    │  │
│ created_at   │       │ txt_hash     │       │ changes_     │  │
│ updated_at   │       │ mp3_hash     │       │   detected   │  │
└──────────────┘       │ updated_at   │       │ status       │  │
                       └──────────────┘       │ error_msg    │  │
                                              └──────────────┘  │
                                                      │         │
                                                      └─────────┘
                                                      (optional FK)
```

---

## 5. WBSパーサー仕様

### 5.1 対応形式

#### 形式1: オブジェクト型（詳細版）

**特徴**: トピックごとに詳細情報（ID、タイトル、ファイル名）を持つ

```json
{
  "project": { "name": "API入門講座" },
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
```

#### 形式2: 配列型（シンプル版）

**特徴**: トピック数のみを持ち、ファイル名は content/ フォルダから推論

```json
{
  "project": { "name": "生成AI入門講座" },
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
              "name": "Chapter 1: AI概要",
              "topics": 4
            },
            {
              "id": "ch2",
              "name": "Chapter 2: プロンプト",
              "topics": 6
            }
          ]
        }
      ]
    }
  ]
}
```

### 5.2 自動検出アルゴリズム

```python
def detect_wbs_format(wbs_data: dict) -> str:
    """
    WBS.jsonの形式を自動検出する

    判定基準:
    1. phases がオブジェクト（dict）なら "object"
    2. phases が配列（list）なら "array"
    3. それ以外は "unknown"
    """
    phases = wbs_data.get('phases', {})

    if isinstance(phases, dict):
        # オブジェクト型: phases.phase_X.chapters.chapter_X.topics[...]
        # topics が配列でオブジェクトを含む
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
        # 配列型: phases[].parts[].chapters[].topics (integer)
        return 'array'

    return 'unknown'
```

### 5.3 パーサー実装

#### オブジェクト型パーサー

```python
class ObjectFormatParser:
    def parse(self, data: dict) -> List[Topic]:
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
                    topics.append(Topic(
                        topic_id=topic_data.get('id', ''),
                        chapter=chapter_name,
                        title=topic_data.get('title', ''),
                        base_name=topic_data.get('base_name', '')
                    ))

        return topics
```

#### 配列型パーサー

```python
class ArrayFormatParser:
    def __init__(self, content_path: Path):
        self.content_path = content_path

    def parse(self, data: dict) -> List[Topic]:
        """
        配列型WBSはトピック数のみを持つため、
        content/ フォルダのファイル名から推論する
        """
        topics = []

        # content/ フォルダのファイル一覧を取得
        files = self._scan_content_files()

        # WBS構造からチャプター情報を取得
        chapters = self._extract_chapters(data)

        # ファイル名とチャプターをマッピング
        for file_name in files:
            chapter = self._infer_chapter(file_name, chapters)
            topic_id = self._extract_topic_id(file_name)

            topics.append(Topic(
                topic_id=topic_id,
                chapter=chapter,
                title=self._clean_title(file_name),
                base_name=file_name
            ))

        return topics

    def _scan_content_files(self) -> List[str]:
        """content/フォルダのHTMLファイルを基準にトピックを特定"""
        files = set()
        for html_file in self.content_path.glob('*.html'):
            # 拡張子を除いたファイル名
            base = html_file.stem
            files.add(base)
        return sorted(files)

    def _extract_topic_id(self, file_name: str) -> str:
        """ファイル名からトピックIDを抽出（例: "01-01_xxx" -> "01-01"）"""
        match = re.match(r'^(\d{2}-\d{2})', file_name)
        return match.group(1) if match else file_name[:5]
```

---

## 6. スキャナー仕様

### 6.1 ファイル検出パターン

| ファイル種別 | 検出パターン | 優先度 |
|------------|-------------|-------|
| HTML | `content/*.html` | 高（必須） |
| TXT | `content/*.txt` | 中 |
| MP3 | `content/*.mp3`, `audio/*.mp3` | 中 |

**ファイル名マッチングルール**:
```python
def match_files(base_name: str, content_dir: Path) -> dict:
    """
    base_nameに対応するHTML/TXT/MP3ファイルを検索

    例: base_name = "01-01_APIの基礎"
    - HTML: "01-01_APIの基礎.html" または "01-01*.html"
    - TXT: "01-01_APIの基礎.txt" または "01-01*.txt"
    - MP3: "01-01_APIの基礎.mp3" または "01-01*.mp3"
    """
    result = {'html': None, 'txt': None, 'mp3': None}

    for ext in ['html', 'txt', 'mp3']:
        # 完全一致
        exact_path = content_dir / f"{base_name}.{ext}"
        if exact_path.exists():
            result[ext] = exact_path
            continue

        # プレフィックス一致（トピックID部分）
        topic_id = base_name.split('_')[0]  # "01-01"
        for file in content_dir.glob(f"{topic_id}*.{ext}"):
            result[ext] = file
            break

    return result
```

### 6.2 進捗計算ロジック

#### トピック単位の進捗

```python
def calculate_topic_progress(topic: Topic) -> float:
    """
    重み付け進捗計算
    - HTML: 40%（メインコンテンツ）
    - TXT: 30%（テキスト版）
    - MP3: 30%（音声版）
    """
    weights = {
        'html': 0.40,
        'txt': 0.30,
        'mp3': 0.30
    }

    progress = 0.0
    if topic.has_html:
        progress += weights['html']
    if topic.has_txt:
        progress += weights['txt']
    if topic.has_mp3:
        progress += weights['mp3']

    return progress * 100  # 0-100%
```

#### プロジェクト単位の進捗

```python
def calculate_project_progress(project: Project, topics: List[Topic]) -> dict:
    """
    プロジェクト全体の進捗を計算
    """
    total = len(topics)
    if total == 0:
        return {'overall': 0, 'html': 0, 'txt': 0, 'mp3': 0}

    html_count = sum(1 for t in topics if t.has_html)
    txt_count = sum(1 for t in topics if t.has_txt)
    mp3_count = sum(1 for t in topics if t.has_mp3)

    # 完了トピック（3つ全て揃っている）
    completed = sum(1 for t in topics
                    if t.has_html and t.has_txt and t.has_mp3)

    # 重み付け全体進捗
    overall = (
        (html_count * 0.4) +
        (txt_count * 0.3) +
        (mp3_count * 0.3)
    ) / total * 100

    return {
        'overall': round(overall, 1),
        'html': round(html_count / total * 100, 1),
        'txt': round(txt_count / total * 100, 1),
        'mp3': round(mp3_count / total * 100, 1),
        'completed_topics': completed,
        'total_topics': total
    }
```

### 6.3 デバウンス処理

```python
class DebouncedScanner:
    def __init__(self, callback: Callable, delay_ms: int = 100):
        self.callback = callback
        self.delay = delay_ms / 1000.0  # 秒に変換
        self._pending_events: List[FileEvent] = []
        self._timer_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def on_file_change(self, event: FileEvent):
        """ファイル変更イベントを受信"""
        async with self._lock:
            self._pending_events.append(event)

            # 既存のタイマーをキャンセル
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()

            # 新しいタイマーを設定
            self._timer_task = asyncio.create_task(self._flush_after_delay())

    async def _flush_after_delay(self):
        """デバウンス待機後、イベントを処理"""
        await asyncio.sleep(self.delay)

        async with self._lock:
            if not self._pending_events:
                return

            events = self._pending_events.copy()
            self._pending_events.clear()

        # 重複除去（同じファイルへの複数イベントを1つに）
        unique_paths = set(e.path for e in events)

        # コールバック実行
        await self.callback(list(unique_paths))
```

### 6.4 キャッシュ戦略

```python
from functools import lru_cache
from cachetools import TTLCache

class ScanCache:
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        # ファイルハッシュキャッシュ（LRU）
        self.hash_cache: TTLCache = TTLCache(maxsize=max_size, ttl=ttl_seconds)

        # プロジェクト情報キャッシュ
        self.project_cache: dict = {}

    def get_file_hash(self, path: str) -> Optional[str]:
        """キャッシュからハッシュを取得"""
        return self.hash_cache.get(path)

    def set_file_hash(self, path: str, hash_value: str):
        """ハッシュをキャッシュに保存"""
        self.hash_cache[path] = hash_value

    def is_file_changed(self, path: str, new_hash: str) -> bool:
        """ファイルが変更されたか判定"""
        old_hash = self.get_file_hash(path)
        if old_hash is None:
            return True  # キャッシュミス = 変更として扱う
        return old_hash != new_hash

    def invalidate(self, path: str = None):
        """キャッシュを無効化"""
        if path:
            self.hash_cache.pop(path, None)
        else:
            self.hash_cache.clear()
```

---

## 7. 非機能要件詳細

### 7.1 パフォーマンス基準

| 項目 | 目標値 | 測定方法 | 許容値 |
|-----|-------|---------|-------|
| 初回フルスキャン（13プロジェクト） | < 3秒 | 実測（計測ログ） | < 5秒 |
| 差分スキャン | < 100ms | 実測（計測ログ） | < 200ms |
| API応答時間（/api/projects） | < 50ms | p99レイテンシ | < 100ms |
| API応答時間（/api/projects/{id}/topics） | < 30ms | p99レイテンシ | < 50ms |
| WebSocket配信遅延 | < 50ms | クライアント計測 | < 100ms |
| フロントエンドFCP | < 1.0秒 | Lighthouse | < 1.5秒 |
| フロントエンドLCP | < 1.5秒 | Lighthouse | < 2.0秒 |
| フロントエンドTTI | < 2.0秒 | Lighthouse | < 3.0秒 |
| メモリ使用量（バックエンド） | < 256MB | プロセス監視 | < 512MB |

### 7.2 スケーラビリティ

| 項目 | 設計値 | テスト確認値 |
|-----|-------|-----------|
| 最大プロジェクト数 | 100 | 負荷テストで確認 |
| 最大トピック数/プロジェクト | 200 | 仮想スクロール対応 |
| 同時WebSocket接続 | 50 | 接続プールで管理 |
| ファイル監視対象数 | 10,000 | watchdog制限 |

### 7.3 可用性

| 項目 | 目標 | 実装方法 |
|-----|-----|---------|
| 起動時間 | < 2秒 | uvicorn最適化 |
| クラッシュ回復 | 自動再起動 | launch_app.command内でリトライ |
| データ整合性 | WALモード | SQLite PRAGMA設定 |
| WebSocket再接続 | 自動（最大5回） | exponential backoff |

### 7.4 セキュリティ

| 項目 | 対策 |
|-----|------|
| ローカル実行 | localhost のみバインド |
| ファイルアクセス | 読み取り専用、対象フォルダ外アクセス禁止 |
| パストラバーサル | パス正規化、許可リスト方式 |
| SQLインジェクション | パラメータバインディング |

---

## 8. テスト仕様

### 8.1 ユニットテスト対象

| モジュール | テスト項目 | カバレッジ目標 |
|----------|----------|--------------|
| wbs_parser.py | オブジェクト型パース、配列型パース、形式検出 | 90% |
| scanner.py | ファイル検出、ハッシュ計算、差分検出 | 85% |
| database.py | CRUD操作、トランザクション | 80% |
| api.py | エンドポイント、エラーハンドリング | 85% |

### 8.2 統合テスト

| シナリオ | 説明 |
|---------|------|
| 起動 → 初回スキャン | アプリ起動から初回スキャン完了まで |
| ファイル追加 → 反映 | HTMLファイル追加後、UI更新まで |
| WebSocket再接続 | 接続切断後の自動再接続 |
| 大量データ | 100プロジェクト、200トピック/プロジェクト |

### 8.3 E2Eテスト

| シナリオ | 操作 | 期待結果 |
|---------|------|---------|
| ダッシュボード表示 | アプリ起動 | 全プロジェクトカード表示 |
| プロジェクト詳細 | カードクリック | 詳細画面遷移、トピック一覧表示 |
| 手動スキャン | スキャンボタンクリック | ローディング→更新反映 |
| リアルタイム更新 | ファイル追加（外部操作） | 5秒以内にUI反映 |

---

## 9. 成果物一覧

### 9.1 バックエンド

| ファイル | 説明 |
|---------|------|
| `backend/main.py` | FastAPIアプリエントリーポイント |
| `backend/config.py` | 設定管理 |
| `backend/database.py` | DB接続・初期化 |
| `backend/models.py` | Pydanticモデル |
| `backend/scanner.py` | 非同期ファイルスキャナー |
| `backend/watcher.py` | ファイルウォッチャー |
| `backend/wbs_parser.py` | WBSパーサー |
| `backend/websocket.py` | WebSocket接続管理 |
| `backend/routers/projects.py` | プロジェクトAPI |
| `backend/routers/scan.py` | スキャンAPI |

### 9.2 フロントエンド

| ファイル | 説明 |
|---------|------|
| `frontend/index.html` | SPAエントリーポイント |
| `frontend/app.js` | Vue.jsアプリ |
| `frontend/store.js` | 状態管理 |
| `frontend/components/Dashboard.js` | ダッシュボード |
| `frontend/components/ProjectCard.js` | プロジェクトカード |
| `frontend/components/ProjectDetail.js` | 詳細画面 |
| `frontend/components/TopicList.js` | トピック一覧 |
| `frontend/services/api.js` | API通信 |
| `frontend/services/websocket.js` | WebSocket通信 |

### 9.3 その他

| ファイル | 説明 |
|---------|------|
| `requirements.txt` | Python依存関係 |
| `launch_app.command` | 起動スクリプト |
| `README.md` | 使用方法 |
| `data/progress_tracker.db` | SQLiteデータベース |

---

## 10. 付録

### 10.1 設定ファイル例（config.yaml）

```yaml
# アプリケーション設定
app:
  name: "研修コンテンツ進捗トラッカー"
  version: "1.0.0"
  host: "127.0.0.1"
  port: 8000

# 対象フォルダ設定
content:
  base_path: "/Users/sohei/Desktop/Learning-Curricula"
  scan_interval_minutes: 5
  debounce_ms: 100

# データベース設定
database:
  path: "./data/progress_tracker.db"
  wal_mode: true

# パフォーマンス設定
performance:
  max_concurrent_scans: 4
  hash_cache_size: 1000
  hash_cache_ttl_seconds: 300

# WebSocket設定
websocket:
  max_connections: 50
  ping_interval_seconds: 30
```

### 10.2 エラーコード一覧

| コード | 説明 | 対処方法 |
|-------|------|---------|
| E001 | WBS.jsonが見つからない | プロジェクトフォルダを確認 |
| E002 | WBS.jsonのパースエラー | JSON構文を確認 |
| E003 | content/フォルダが見つからない | フォルダ構造を確認 |
| E004 | データベース接続エラー | DB再作成 |
| E005 | WebSocket接続エラー | ブラウザ更新 |
| E006 | スキャンタイムアウト | プロジェクト数を確認 |

---

*この仕様書は REQUIREMENTS.md と ARCHITECTURE.md に基づいて作成されました。*
