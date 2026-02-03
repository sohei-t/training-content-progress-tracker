# 研修コンテンツ進捗トラッカー - 要件定義書

## 革新的アプローチ（Approach B）

> **設計思想**: リアルタイム・イベント駆動・高パフォーマンス

---

## 1. ユーザーストーリー

### 1.1 研修管理者として

| ID | ストーリー | 優先度 | 革新的ポイント |
|----|----------|--------|--------------|
| US-001 | ダッシュボードを開いた瞬間に全プロジェクトの進捗が見える | MUST | WebSocket即時更新 |
| US-002 | ファイル追加・変更がリアルタイムで反映される | MUST | ファイルウォッチャー + 差分検出 |
| US-003 | 進捗率だけでなく、完了予測も知りたい | SHOULD | 機械学習による完了予測 |
| US-004 | スマホからも進捗確認したい | SHOULD | PWA対応 |
| US-005 | 複数プロジェクトを一括比較したい | MUST | 並列表示モード |

### 1.2 コンテンツ作成者として

| ID | ストーリー | 優先度 | 革新的ポイント |
|----|----------|--------|--------------|
| US-101 | 自分の作業がすぐに反映されてモチベーションが上がる | MUST | 0.5秒以内の更新 |
| US-102 | 次に何を作るべきかガイダンスが欲しい | COULD | AI推奨機能 |
| US-103 | 作成中のファイルのプレビューが見たい | SHOULD | ライブプレビュー |

---

## 2. 機能要件

### 2.1 コア機能（MUST）

#### F-001: インテリジェントスキャンシステム
```yaml
概要: 差分検出による高速スキャン
実装方式:
  初回スキャン: 全ファイル走査（バックグラウンド）
  差分スキャン: ファイルハッシュ比較（メモリキャッシュ）
  リアルタイム: watchdog + asyncio

技術詳細:
  - aiofiles による非同期ファイル読み込み
  - xxhash による高速ハッシュ計算（MD5の10倍速）
  - デバウンス処理（100ms）で連続変更を集約
  - メモリ内キャッシュ（LRU、最大1000エントリ）

トリガー:
  - 起動時: 初回フルスキャン
  - 5分間隔: 差分スキャン
  - ファイル変更検出: 即時差分更新
  - 手動ボタン: 強制フルスキャン
```

#### F-002: WebSocketリアルタイム更新
```yaml
概要: サーバー→クライアントのプッシュ更新
技術詳細:
  - FastAPI WebSocket
  - 接続プール管理
  - 再接続ロジック（exponential backoff）
  - バイナリ圧縮（MessagePack）

更新イベント:
  - project_updated: 個別プロジェクト更新
  - scan_progress: スキャン進捗
  - topic_completed: トピック完了通知
```

#### F-003: ダッシュボード表示
```yaml
概要: 全体サマリー + プロジェクト一覧
レイアウト:
  ヘッダー:
    - 全体進捗（数値 + アニメーション付き円グラフ）
    - 合計トピック数 / 完了数
    - 最終更新時刻

  プロジェクトカード:
    - プロジェクト名
    - 進捗バー（HTML / TXT / MP3 別色分け）
    - 完了トピック / 全トピック
    - 最終更新日時
    - クイックアクション（詳細 / フォルダを開く）

パフォーマンス目標:
  - FCP: < 1.0秒
  - LCP: < 1.5秒
  - TTI: < 2.0秒
```

#### F-004: プロジェクト詳細画面
```yaml
概要: トピック別進捗の詳細表示
レイアウト:
  サイドバー:
    - チャプター一覧（折りたたみ可能）
    - 進捗フィルター（完了 / 進行中 / 未着手）

  メインエリア:
    - トピック一覧（仮想スクロール対応）
    - 各トピックの成果物状態（HTML/TXT/MP3 アイコン）
    - WBS情報表示（対応形式両方サポート）

仮想スクロール:
  - 82トピック表示でも60fps維持
  - 表示範囲外のDOMを動的に生成・破棄
```

### 2.2 拡張機能（SHOULD/COULD）

#### F-101: 進捗予測エンジン
```yaml
概要: 過去の作成ペースから完了日を予測
アルゴリズム:
  - 移動平均（直近7日の作成速度）
  - 週末・祝日を考慮
  - 信頼区間付き予測

表示:
  - 予測完了日（90%信頼区間）
  - 残り作業量グラフ
```

#### F-102: PWA対応
```yaml
概要: スマートフォンからのアクセス最適化
機能:
  - オフラインキャッシュ（Service Worker）
  - ホーム画面追加
  - プッシュ通知（完了通知）
```

---

## 3. 非機能要件

### 3.1 パフォーマンス（最優先）

| 項目 | 目標値 | 測定方法 |
|-----|-------|---------|
| 初回スキャン（13プロジェクト） | < 3秒 | 実測 |
| 差分スキャン | < 100ms | 実測 |
| API応答時間（一覧） | < 50ms | p99 |
| API応答時間（詳細） | < 30ms | p99 |
| WebSocket遅延 | < 50ms | クライアント計測 |
| フロントエンドFCP | < 1.0秒 | Lighthouse |
| フロントエンドLCP | < 1.5秒 | Lighthouse |

### 3.2 スケーラビリティ

| 項目 | 設計値 |
|-----|-------|
| 最大プロジェクト数 | 100 |
| 最大トピック数/プロジェクト | 200 |
| 同時WebSocket接続 | 50 |
| メモリ使用量 | < 256MB |

### 3.3 可用性

| 項目 | 目標 |
|-----|-----|
| 起動時間 | < 2秒 |
| クラッシュ回復 | 自動再起動 |
| データ整合性 | WALモード有効 |

### 3.4 保守性

- コード行数: 最小限（DRY原則）
- テストカバレッジ: 80%以上
- ドキュメント: API自動生成（Swagger）

---

## 4. 技術スタック

### 4.1 バックエンド
```yaml
フレームワーク: FastAPI 0.115+
  理由: 非同期ネイティブ、WebSocketサポート、自動ドキュメント

データベース: SQLite + aiosqlite
  理由: 軽量、WALモードで並行アクセス対応

ファイル監視: watchdog + asyncio
  理由: クロスプラットフォーム、低リソース

ハッシュ: xxhash
  理由: MD5の10倍高速

スキャンキュー: asyncio.Queue
  理由: 外部依存なし、シンプル
```

### 4.2 フロントエンド
```yaml
フレームワーク: Vue.js 3 (CDN)
  理由: 軽量、Composition API、リアクティブ

UIライブラリ: Tailwind CSS (CDN)
  理由: ユーティリティファースト、小さいバンドル

チャート: Chart.js
  理由: 軽量、アニメーション対応

WebSocket: ネイティブ WebSocket API
  理由: 追加依存なし

仮想スクロール: vue-virtual-scroller
  理由: 大量トピック対応
```

### 4.3 データフロー（イベント駆動）
```
[ファイルシステム]
       ↓ watchdog
[ファイルウォッチャー]
       ↓ asyncio.Queue
[スキャナー (非同期)]
       ↓
[SQLite (aiosqlite)]
       ↓ WebSocket
[接続プール]
       ↓ MessagePack
[ブラウザ (Vue.js)]
```

---

## 5. データモデル

### 5.1 プロジェクト
```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    wbs_format TEXT CHECK(wbs_format IN ('object', 'array')),
    total_topics INTEGER DEFAULT 0,
    completed_topics INTEGER DEFAULT 0,
    last_scanned_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_projects_name ON projects(name);
```

### 5.2 トピック
```sql
CREATE TABLE topics (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    chapter TEXT,
    topic_id TEXT,
    title TEXT,
    base_name TEXT NOT NULL,
    has_html INTEGER DEFAULT 0,
    has_txt INTEGER DEFAULT 0,
    has_mp3 INTEGER DEFAULT 0,
    html_hash TEXT,
    txt_hash TEXT,
    mp3_hash TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_topics_project ON topics(project_id);
CREATE INDEX idx_topics_base_name ON topics(base_name);
```

### 5.3 スキャン履歴
```sql
CREATE TABLE scan_history (
    id INTEGER PRIMARY KEY,
    started_at TEXT,
    completed_at TEXT,
    scan_type TEXT CHECK(scan_type IN ('full', 'diff', 'watch')),
    projects_scanned INTEGER,
    files_scanned INTEGER,
    changes_detected INTEGER
);
```

---

## 6. WBS.json対応パターン

### 6.1 オブジェクト型（詳細版）
```json
{
  "phases": {
    "phase_2": {
      "chapters": {
        "chapter_1": {
          "topics": [
            {
              "id": "topic_01_01",
              "title": "タイトル",
              "base_name": "01-01_filename"
            }
          ]
        }
      }
    }
  }
}
```

### 6.2 配列型（シンプル版）
```json
{
  "phases": [
    {
      "id": "phase2",
      "parts": [
        {
          "chapters": [
            {
              "id": "ch1",
              "topics": 4
            }
          ]
        }
      ]
    }
  ]
}
```

### 6.3 パーサー設計
```python
def detect_wbs_format(wbs_data: dict) -> str:
    """WBS形式を自動検出"""
    phases = wbs_data.get('phases', {})
    if isinstance(phases, dict):
        return 'object'
    elif isinstance(phases, list):
        return 'array'
    return 'unknown'
```

---

## 7. API設計（概要）

### 7.1 RESTエンドポイント
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | /api/projects | プロジェクト一覧 |
| GET | /api/projects/{id} | プロジェクト詳細 |
| GET | /api/projects/{id}/topics | トピック一覧 |
| POST | /api/scan | 手動スキャン実行 |
| GET | /api/stats | 全体統計 |

### 7.2 WebSocket
| Event | 方向 | 説明 |
|-------|-----|------|
| connect | C→S | 接続確立 |
| project_updated | S→C | プロジェクト更新 |
| scan_started | S→C | スキャン開始 |
| scan_completed | S→C | スキャン完了 |
| topic_changed | S→C | トピック変更 |

---

## 8. 成果物チェックリスト

- [ ] REQUIREMENTS.md（本ファイル）
- [ ] WBS.json
- [ ] CRITICAL_PATH.md
- [ ] ARCHITECTURE.md
- [ ] TECH_STACK.md（ARCHITECTURE内に統合）
