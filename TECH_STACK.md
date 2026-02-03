# 技術スタック決定書 (TECH_STACK.md)

> **プロジェクト**: 研修コンテンツ進捗トラッカー
> **バージョン**: 1.0
> **作成日**: 2026-02-03
> **アプローチ**: 革新的（イベント駆動・リアルタイム・高パフォーマンス）

---

## 1. 技術スタック概要

### 1.1 バックエンド

| 技術 | バージョン | 選定理由 |
|------|-----------|---------|
| Python | 3.11+ | 非同期処理サポート、豊富なエコシステム |
| FastAPI | 0.115+ | 非同期ネイティブ、WebSocket対応、自動OpenAPIドキュメント生成 |
| uvicorn | 0.30+ | ASGI対応、高パフォーマンス、ホットリロード対応 |
| aiosqlite | 0.20+ | SQLiteの非同期ラッパー、asyncio完全対応 |
| watchdog | 4.0+ | クロスプラットフォームファイル監視、低リソース消費 |
| xxhash | 3.4+ | 高速ハッシュ計算（MD5の10倍速）、差分検出に最適 |
| pydantic | 2.0+ | 型検証、データバリデーション、FastAPIとの統合 |
| python-multipart | 0.0.9+ | ファイルアップロード対応（将来の拡張用） |

### 1.2 フロントエンド

| 技術 | バージョン | 選定理由 |
|------|-----------|---------|
| Vue.js 3 | CDN (latest) | 軽量、Composition API、リアクティブ、ビルド不要 |
| Tailwind CSS | CDN (latest) | ユーティリティファースト、高速開発、小さいバンドル |
| Chart.js | CDN (latest) | 軽量チャートライブラリ、アニメーション対応 |
| Native WebSocket API | - | ブラウザネイティブ、追加依存なし |

### 1.3 データベース

| 技術 | バージョン | 選定理由 |
|------|-----------|---------|
| SQLite | 3.35+ | 軽量、単一ファイル、WALモードで並行アクセス対応 |

---

## 2. 依存関係詳細

### 2.1 Python依存関係（requirements.txt形式）

```
# Web Framework
fastapi>=0.115.0
uvicorn[standard]>=0.30.0

# Database
aiosqlite>=0.20.0

# File System
watchdog>=4.0.0
aiofiles>=24.1.0

# Hashing
xxhash>=3.4.0

# Data Validation
pydantic>=2.0.0
pydantic-settings>=2.0.0

# File Upload (optional)
python-multipart>=0.0.9

# Testing
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.0.0
httpx>=0.27.0
```

### 2.2 フロントエンド（CDN）

```html
<!-- Vue.js 3 -->
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>

<!-- Tailwind CSS -->
<script src="https://cdn.tailwindcss.com"></script>

<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

**CDN選択理由**:
- ビルドプロセス不要（Node.js不要）
- 即座に開発開始可能
- ブラウザキャッシュ活用
- 依存関係管理の簡素化

---

## 3. 開発環境

### 3.1 必須要件

| 項目 | 要件 |
|-----|-----|
| Python | 3.11以上 |
| Node.js | 不要（CDNベース） |
| SQLite | 3.35以上（WALモード対応） |
| OS | macOS / Linux / Windows |

### 3.2 推奨開発ツール

| ツール | 用途 |
|-------|-----|
| VSCode | IDE |
| Python extension | Python開発支援 |
| SQLite Viewer | DBブラウジング |
| Thunder Client / Postman | API テスト |

### 3.3 環境セットアップ手順

```bash
# 1. Python仮想環境作成
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 依存関係インストール
pip install -r requirements.txt

# 3. 起動
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

---

## 4. アーキテクチャ決定記録（ADR）

### ADR-001: Webフレームワーク選定

**ステータス**: 採用

**コンテキスト**:
研修コンテンツの進捗をリアルタイムで表示するダッシュボードアプリケーションを開発する。WebSocketによるリアルタイム更新、非同期ファイルスキャン、高速なAPI応答が必要。

**検討した選択肢**:

| 選択肢 | 長所 | 短所 |
|-------|-----|-----|
| **FastAPI** | 非同期ネイティブ、WebSocket対応、自動ドキュメント、型ヒント活用 | 比較的新しい |
| Flask | シンプル、豊富なエコシステム | 非同期サポートが弱い、WebSocket追加ライブラリ必要 |
| Django | フルスタック、管理画面 | オーバースペック、非同期サポート限定的 |

**決定**: FastAPI

**理由**:
1. **非同期ネイティブ**: asyncio を標準サポート、I/O バウンドな処理に最適
2. **WebSocket対応**: 追加ライブラリなしでWebSocket実装可能
3. **自動ドキュメント**: OpenAPI/Swagger UI を自動生成
4. **高パフォーマンス**: Starlette ベースで高スループット
5. **型安全性**: Pydantic との統合で堅牢なバリデーション

---

### ADR-002: データベース選定

**ステータス**: 採用

**コンテキスト**:
プロジェクト情報、トピック情報、スキャン履歴を永続化する必要がある。ローカル実行を前提とし、外部サービス依存を排除したい。

**検討した選択肢**:

| 選択肢 | 長所 | 短所 |
|-------|-----|-----|
| **SQLite** | 軽量、単一ファイル、設定不要、WALモード | 大規模データに不向き |
| PostgreSQL | 高機能、スケーラブル | 外部サービス依存、オーバースペック |
| JSON ファイル | 最もシンプル | クエリ困難、並行アクセス問題 |

**決定**: SQLite + aiosqlite

**理由**:
1. **軽量**: 外部プロセス不要、組み込み可能
2. **単一ファイル**: バックアップ・移行が容易
3. **WALモード**: 読み書き並行アクセス対応
4. **非同期対応**: aiosqlite で asyncio 完全統合
5. **$0ポリシー準拠**: 外部サービス費用なし

**WALモード設定**:
```python
# database.py
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA cache_size=10000")
```

---

### ADR-003: フロントエンド構成

**ステータス**: 採用

**コンテキスト**:
ダッシュボードUIを構築する。リアクティブな更新、コンポーネント管理、状態管理が必要。ただし、ビルドプロセスは避けたい。

**検討した選択肢**:

| 選択肢 | 長所 | 短所 |
|-------|-----|-----|
| **Vue.js 3 (CDN)** | 軽量、ビルド不要、Composition API | 大規模アプリには不向き |
| React (CDN) | 人気、エコシステム | JSX変換必要、CDN版は制限あり |
| Vanilla JS | 依存なし | 状態管理・コンポーネント化が困難 |
| Svelte | コンパイル時最適化 | ビルド必須 |

**決定**: Vue.js 3 (CDN) + Tailwind CSS (CDN)

**理由**:
1. **ビルド不要**: Node.js 環境不要、即座に開発可能
2. **Composition API**: 再利用可能なロジック抽出
3. **リアクティブ**: `ref`, `reactive` で自動UI更新
4. **Tailwind CSS**: ユーティリティクラスで高速スタイリング
5. **学習コスト**: 比較的低い

**CDN構成の制約と対策**:
| 制約 | 対策 |
|-----|-----|
| 単一ファイルコンポーネント(.vue)使用不可 | オブジェクト形式でコンポーネント定義 |
| ビルド時最適化なし | CDNキャッシュ活用、本番用min版使用 |
| TypeScript使用不可 | JSDoc による型ヒント |

---

### ADR-004: ファイル監視ライブラリ選定

**ステータス**: 採用

**コンテキスト**:
Learning-Curricula フォルダのファイル変更をリアルタイムで検出し、ダッシュボードに反映する必要がある。

**検討した選択肢**:

| 選択肢 | 長所 | 短所 |
|-------|-----|-----|
| **watchdog** | クロスプラットフォーム、低リソース、Python標準 | 一部OSでポーリング |
| inotify (Linux) | 高効率 | Linux専用 |
| FSEvents (macOS) | 高効率 | macOS専用 |
| polling | シンプル | リソース消費大 |

**決定**: watchdog

**理由**:
1. **クロスプラットフォーム**: macOS/Linux/Windows対応
2. **低リソース**: OS ネイティブイベント活用
3. **Python統合**: asyncio と組み合わせ可能
4. **実績**: 広く使われている

**実装パターン**:
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ContentHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(('.html', '.txt', '.mp3')):
            asyncio.create_task(scan_file(event.src_path))
```

---

### ADR-005: ハッシュアルゴリズム選定

**ステータス**: 採用

**コンテキスト**:
ファイル変更検出のためにハッシュ計算を行う。大量ファイルの高速処理が必要。

**検討した選択肢**:

| 選択肢 | 速度 | セキュリティ | 用途 |
|-------|-----|------------|-----|
| **xxHash** | 最速（10GB/s） | 非暗号化 | チェックサム、差分検出 |
| MD5 | 中（1GB/s） | 脆弱 | レガシー |
| SHA-256 | 遅（500MB/s） | 高 | 暗号用途 |

**決定**: xxHash (xxh64)

**理由**:
1. **高速**: MD5の10倍、SHA-256の20倍の速度
2. **十分な品質**: 衝突率は非常に低い
3. **目的に適合**: 暗号化目的ではなく差分検出用
4. **メモリ効率**: ストリーミング処理対応

---

## 5. 外部API

### 5.1 使用する外部API

**なし（$0ポリシー準拠）**

### 5.2 ローカルリソースのみ使用

| リソース | 用途 |
|---------|-----|
| ローカルファイルシステム | Learning-Curricula フォルダのスキャン |
| SQLite | データ永続化 |
| ブラウザ | UIレンダリング |

### 5.3 将来の拡張可能性

| 機能 | 必要API | コスト見積もり |
|-----|---------|--------------|
| 進捗通知 | Web Push API | $0（ブラウザAPI） |
| AI推奨 | OpenAI / Claude | $0.01/リクエスト |
| クラウド同期 | Firebase | $0（無料枠内） |

**注**: 上記は将来の拡張案であり、現バージョンでは実装しない

---

## 6. セキュリティ考慮

### 6.1 実行環境の制限

| 項目 | 設定 |
|-----|-----|
| バインドアドレス | `127.0.0.1`（localhost のみ） |
| ポート | `8000`（変更可能） |
| 認証 | 不要（シングルユーザー前提） |

### 6.2 ファイルシステムアクセス

| 対策 | 実装 |
|-----|-----|
| 読み取り専用 | ファイル変更操作なし |
| パス制限 | 設定で指定したフォルダのみアクセス |
| パストラバーサル対策 | パス正規化、許可リスト方式 |

```python
# config.py
ALLOWED_BASE_PATH = Path("/Users/sohei/Desktop/Learning-Curricula")

def validate_path(path: Path) -> bool:
    """パスが許可された範囲内か検証"""
    try:
        resolved = path.resolve()
        return resolved.is_relative_to(ALLOWED_BASE_PATH)
    except ValueError:
        return False
```

### 6.3 データベースセキュリティ

| 対策 | 実装 |
|-----|-----|
| SQLインジェクション対策 | パラメータバインディング使用 |
| アクセス制御 | ローカルファイル、OSレベル権限 |

```python
# 安全なクエリ例
async def get_project(project_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,)  # パラメータバインディング
        )
        return await cursor.fetchone()
```

---

## 7. パフォーマンス最適化戦略

### 7.1 バックエンド最適化

| 最適化 | 効果 | 実装 |
|-------|-----|-----|
| 非同期I/O | I/O待ちをブロックしない | aiofiles, aiosqlite |
| xxHash | ハッシュ計算10倍高速 | xxhash.xxh64() |
| WALモード | 読み書き並行 | PRAGMA journal_mode=WAL |
| デバウンス | 連続イベント集約 | 100ms待機 |
| メモリキャッシュ | 差分検出高速化 | LRUCache |

### 7.2 フロントエンド最適化

| 最適化 | 効果 | 実装 |
|-------|-----|-----|
| CDN | ビルド不要、キャッシュ活用 | unpkg, jsdelivr |
| 仮想スクロール | 大量DOM回避 | 表示範囲のみレンダリング |
| computed | 不要な再計算回避 | Vue computed |
| WebSocket | ポーリング不要 | リアルタイム更新 |

### 7.3 目標パフォーマンス指標

| 指標 | 目標値 | 許容値 |
|-----|-------|-------|
| 初回スキャン（13プロジェクト） | < 3秒 | < 5秒 |
| 差分スキャン | < 100ms | < 200ms |
| API応答（一覧） | < 50ms | < 100ms |
| WebSocket遅延 | < 50ms | < 100ms |
| フロントエンドFCP | < 1.0秒 | < 1.5秒 |
| メモリ使用量 | < 256MB | < 512MB |

---

## 8. テスト戦略

### 8.1 テストツール

| ツール | 用途 |
|-------|-----|
| pytest | ユニットテスト、統合テスト |
| pytest-asyncio | 非同期テスト |
| pytest-cov | カバレッジ計測 |
| httpx | 非同期HTTPクライアント（APIテスト） |

### 8.2 テスト構成

```
tests/
├── unit/
│   ├── test_wbs_parser.py      # WBSパーサーのユニットテスト
│   ├── test_scanner.py         # スキャナーのユニットテスト
│   ├── test_database.py        # DBアクセスのユニットテスト
│   └── test_models.py          # Pydanticモデルのテスト
├── integration/
│   ├── test_api.py             # APIエンドポイントの統合テスト
│   └── test_websocket.py       # WebSocket通信のテスト
└── e2e/
    └── test_full_flow.py       # E2Eシナリオテスト
```

### 8.3 カバレッジ目標

| モジュール | 目標カバレッジ |
|----------|--------------|
| wbs_parser.py | 90% |
| scanner.py | 85% |
| database.py | 80% |
| routers/ | 85% |
| 全体 | 80% |

---

## 9. 依存関係図

```
                    ┌──────────────────┐
                    │    クライアント    │
                    │  (ブラウザ)       │
                    └────────┬─────────┘
                             │
                    HTTP / WebSocket
                             │
                    ┌────────▼─────────┐
                    │     FastAPI      │
                    │    (uvicorn)     │
                    └────────┬─────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│   aiosqlite    │  │    watchdog    │  │    xxhash      │
│   (SQLite)     │  │ (File Watch)   │  │   (Hashing)    │
└────────────────┘  └────────────────┘  └────────────────┘
         │                   │
         ▼                   ▼
┌────────────────┐  ┌────────────────┐
│  SQLite DB     │  │  File System   │
│ (WAL mode)     │  │ (Learning-     │
│                │  │  Curricula)    │
└────────────────┘  └────────────────┘
```

---

## 10. まとめ

### 10.1 技術選定の原則

1. **$0ポリシー**: 外部サービス費用なし
2. **シンプル優先**: オーバーエンジニアリング回避
3. **ローカル実行**: 外部依存最小化
4. **非同期優先**: I/O待ちを効率化
5. **ビルドレス**: CDN活用で即時開発

### 10.2 主要技術スタック

| レイヤー | 技術 |
|---------|-----|
| バックエンド | Python 3.11 + FastAPI + uvicorn |
| データベース | SQLite + aiosqlite (WALモード) |
| フロントエンド | Vue.js 3 + Tailwind CSS (CDN) |
| リアルタイム | WebSocket (Native API) |
| ファイル監視 | watchdog |
| ハッシュ | xxhash |

### 10.3 非採用技術（将来の検討候補）

| 技術 | 不採用理由 | 将来の検討条件 |
|-----|----------|--------------|
| PostgreSQL | オーバースペック | 複数ユーザー対応時 |
| Redis | 不要な複雑性 | キャッシュ要件増加時 |
| React | ビルド必要 | 大規模化時 |
| TypeScript | ビルド必要 | 型安全性優先時 |

---

*この技術スタック決定書は REQUIREMENTS.md、ARCHITECTURE.md、SPEC.md に基づいて作成されました。*
