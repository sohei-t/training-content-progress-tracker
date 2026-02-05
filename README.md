# 研修コンテンツ進捗トラッカー

研修コンテンツの制作進捗をリアルタイムで可視化するダッシュボードアプリケーションです。
ファイルシステムを監視し、HTML/TXT/MP3ファイルの作成状況を自動で追跡します。

## 主な機能

- **リアルタイム進捗表示** - WebSocketでファイル変更を即座に反映
- **プロジェクト管理** - 複数の研修プロジェクトを一元管理
- **トピック追跡** - 各トピックのHTML/TXT/MP3/SSMLファイル完成状況を可視化
- **ダッシュボード** - 全体進捗、完了トピック数、成果物数を一覧表示
- **自動スキャン** - ファイルシステムの変更を自動検出して更新
- **マスター管理** - 納品先、音声変換エンジン、公開状態をカスタマイズ可能

## 技術スタック

### バックエンド
- **Python 3.12+**
- **FastAPI** - 高性能Webフレームワーク
- **uvicorn** - ASGIサーバー
- **aiosqlite** - 非同期SQLiteデータベース
- **watchdog** - ファイルシステム監視

### フロントエンド
- **Vue.js 3** - リアクティブUI
- **Tailwind CSS** - ユーティリティファーストCSS
- **WebSocket** - リアルタイム通信

## セットアップ

### 前提条件
- Python 3.12以上

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/sohei-t/training-content-progress-tracker.git
cd training-content-progress-tracker/project

# 仮想環境を作成
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt
```

### 起動

```bash
# 簡易起動（macOS）
./launch_app.command

# または手動起動
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

ブラウザで http://localhost:8000 を開きます。

## 使用方法

1. **ダッシュボード** - 全プロジェクトの進捗サマリーを確認
2. **プロジェクト選択** - カードをクリックして詳細を表示
3. **手動スキャン** - 右上のボタンでファイルを再スキャン
4. **設定** - 納品先・音声変換エンジン・公開状態のマスター管理

## ディレクトリ構成

```
project/
├── backend/
│   ├── main.py          # FastAPIアプリケーション
│   ├── api.py           # APIルーター
│   ├── database.py      # データベース操作
│   ├── scanner.py       # ファイルスキャナー
│   ├── watcher.py       # ファイル監視
│   └── websocket.py     # WebSocket管理
├── frontend/
│   ├── index.html       # メインページ
│   └── js/
│       ├── app.js       # Vueアプリケーション
│       ├── api.js       # API通信
│       └── websocket.js # WebSocket管理
├── requirements.txt
└── launch_app.command
```

## API エンドポイント

| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/projects` | プロジェクト一覧 |
| GET | `/api/projects/{id}` | プロジェクト詳細 |
| GET | `/api/projects/{id}/topics` | トピック一覧 |
| PUT | `/api/projects/{id}/settings` | プロジェクト設定更新 |
| POST | `/api/scan` | 手動スキャン |
| GET | `/api/destinations` | 納品先一覧 |
| GET | `/api/tts-engines` | 音声変換エンジン一覧 |
| GET | `/api/publication-statuses` | 公開状態一覧 |
| WS | `/ws` | WebSocket接続 |

## ライセンス

MIT License
