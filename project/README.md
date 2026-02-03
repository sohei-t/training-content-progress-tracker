# 研修コンテンツ進捗トラッカー

リアルタイムで研修コンテンツの制作進捗を可視化するダッシュボードアプリケーション。
ファイルシステムを監視し、HTML/TXT/MP3ファイルの作成状況を自動で追跡します。

## 主な機能

- **リアルタイム進捗表示**: WebSocketでファイル変更を即座に反映
- **プロジェクト管理**: 複数の研修プロジェクトを一元管理
- **トピック追跡**: 各トピックのHTML/TXT/MP3ファイル完成状況を可視化
- **ダッシュボード**: 全体進捗、完了トピック数、成果物数を一覧表示
- **自動スキャン**: ファイルシステムの変更を自動検出して更新

## 技術スタック

### バックエンド
- **Python 3.12+**: メイン開発言語
- **FastAPI**: 高性能Webフレームワーク
- **uvicorn**: ASGIサーバー
- **aiosqlite**: 非同期SQLiteデータベース
- **watchdog**: ファイルシステム監視
- **xxhash**: 高速ハッシュ計算

### フロントエンド
- **Vue.js 3**: リアクティブUI
- **Tailwind CSS**: ユーティリティファーストCSS
- **WebSocket**: リアルタイム通信

### テスト
- **pytest**: テストフレームワーク
- **pytest-asyncio**: 非同期テスト
- **pytest-cov**: カバレッジ計測
- **httpx**: HTTPクライアント（テスト用）

## セットアップ手順

### 前提条件
- Python 3.12以上
- pip（パッケージマネージャー）

### インストール

```bash
# リポジトリをクローン
git clone <repository-url>
cd training-content-progress-tracker

# 仮想環境を作成
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt
```

### 起動

```bash
# 簡易起動（推奨）
./launch_app.command

# または手動起動
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

アプリケーションは http://localhost:8000 で起動します。

## 使用方法

1. **初期表示**: ダッシュボードに全プロジェクトの進捗サマリーが表示されます
2. **プロジェクト選択**: カードをクリックしてプロジェクト詳細を表示
3. **手動スキャン**: 右上の「手動スキャン」ボタンでファイルを再スキャン
4. **リアルタイム更新**: ファイルが追加/変更されると自動で画面が更新されます

### 画面構成

```
┌─────────────────────────────────────────────────────┐
│ 研修コンテンツ進捗トラッカー    [Live] [手動スキャン]│
├─────────────────────────────────────────────────────┤
│ [全プロジェクト] [全体進捗] [完了トピック] [成果物数]│
│       12           78.5%        45/60       120    │
├─────────────────────────────────────────────────────┤
│ プロジェクト一覧                                    │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│ │Project A │ │Project B │ │Project C │           │
│ │ ████████ │ │ ██████   │ │ ████     │           │
│ │  95%     │ │  75%     │ │  50%     │           │
│ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────┘
```

## テスト実行方法

```bash
# 全テスト実行
pytest

# カバレッジ付きで実行
pytest --cov=backend --cov-report=html

# 特定のテストファイルを実行
pytest tests/test_api.py -v
```

### テストカバレッジ
- 全体カバレッジ: 80%以上
- クリティカルパス: 100%カバー

## API エンドポイント

| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/` | インデックスページ |
| GET | `/api/projects` | プロジェクト一覧取得 |
| GET | `/api/projects/{id}` | プロジェクト詳細取得 |
| GET | `/api/projects/{id}/topics` | トピック一覧取得 |
| POST | `/api/scan` | 手動スキャン実行 |
| POST | `/api/force-scan` | 強制フルスキャン |
| WS | `/ws` | WebSocket接続 |

## ディレクトリ構造

```
project/
├── backend/
│   ├── __init__.py
│   ├── main.py          # FastAPIアプリケーション
│   ├── api.py           # APIルーター
│   ├── database.py      # データベース操作
│   ├── models.py        # Pydanticモデル
│   ├── scanner.py       # ファイルスキャナー
│   ├── watcher.py       # ファイル監視
│   ├── wbs_parser.py    # WBSファイルパーサー
│   └── websocket.py     # WebSocket管理
├── frontend/
│   ├── index.html       # メインページ
│   ├── css/
│   │   └── styles.css   # カスタムスタイル
│   └── js/
│       ├── app.js       # Vueアプリケーション
│       ├── api.js       # API通信モジュール
│       └── websocket.js # WebSocket管理
├── tests/
│   ├── conftest.py      # テスト共通設定
│   ├── test_api.py      # APIテスト
│   ├── test_database.py # データベーステスト
│   └── ...
├── requirements.txt     # Python依存関係
├── pytest.ini          # pytest設定
└── launch_app.command  # 起動スクリプト
```

## 開発情報

### 設計思想
- **パフォーマンス最優先**: 非同期処理を全面採用
- **リアルタイム性**: WebSocketによる即座の更新
- **スケーラビリティ**: 大規模プロジェクトにも対応

### 今後の拡張予定
- グラフによる進捗可視化
- エクスポート機能（CSV/PDF）
- 通知機能（Slack連携等）

## ライセンス

MIT License

---

Generated with Claude Code and AI Agent Workflow
